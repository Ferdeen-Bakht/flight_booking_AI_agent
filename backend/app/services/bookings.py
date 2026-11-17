import json
import re
import secrets
import string
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Booking
from . import duffel, offers
from .mailer import send_confirmation


class BookingError(Exception):
    pass


class PriceChanged(BookingError):
    def __init__(self, new_total: float, currency: str, new_pkr: int):
        super().__init__(f"The fare price changed to {currency} {new_total:,.2f} (PKR {new_pkr:,}). Please review and confirm again.")
        self.new_total, self.currency, self.new_pkr = new_total, currency, new_pkr


NAME = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,49}$")
PHONE = re.compile(r"^\+\d{8,15}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TITLES = {"mr", "ms", "mrs", "miss", "dr"}


def _ref() -> str:
    return "FB" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))


def validate_passengers(raw: list[dict], offer: dict) -> list[dict]:
    """Server-side passenger validation (the UI validates too, but never trust the client)."""
    out = []
    last_dep = date.fromisoformat(offer["slices"][-1]["departure"][:10])
    for i, p in enumerate(raw, 1):
        who = f"Passenger {i}"
        if p.get("title") not in TITLES:
            raise BookingError(f"{who}: choose a title.")
        if p.get("gender") not in ("m", "f"):
            raise BookingError(f"{who}: choose a gender.")
        for k, label in (("given_name", "first name"), ("family_name", "last name")):
            if not NAME.match(str(p.get(k, "")).strip()):
                raise BookingError(f"{who}: {label} must use letters only (as on the passport).")
        try:
            born = date.fromisoformat(str(p.get("born_on")))
        except ValueError:
            raise BookingError(f"{who}: enter a valid date of birth.")
        age = (date.today() - born).days / 365.25
        if born >= date.today() or age > 120:
            raise BookingError(f"{who}: date of birth looks wrong.")
        if age < 12:
            raise BookingError(f"{who}: only adult/12+ passengers can be booked here.")
        item = {"title": p["title"], "gender": p["gender"], "given_name": p["given_name"].strip(),
                "family_name": p["family_name"].strip(), "born_on": born.isoformat()}
        if offer.get("passport_required") or p.get("passport_number"):
            num = str(p.get("passport_number") or "").strip().upper()
            ctry = str(p.get("passport_country") or "").strip().upper()
            try:
                exp = date.fromisoformat(str(p.get("passport_expiry")))
            except ValueError:
                raise BookingError(f"{who}: enter the passport expiry date.")
            if not re.fullmatch(r"[A-Z0-9]{6,12}", num):
                raise BookingError(f"{who}: passport number must be 6-12 letters/digits.")
            if not re.fullmatch(r"[A-Z]{2}", ctry):
                raise BookingError(f"{who}: passport country must be a 2-letter code (e.g. PK).")
            if exp <= last_dep:
                raise BookingError(f"{who}: passport expires before the trip ends.")
            item.update(passport_number=num, passport_country=ctry, passport_expiry=exp.isoformat())
        out.append(item)
    return out


def create_booking(db: Session, user, offer_id: str, passengers: list[dict], email: str, phone: str,
                   expected_total: float | None) -> Booking:
    try:
        offer = offers.get_offer(db, offer_id, refresh=True)  # final price check with the provider
    except offers.OfferError as e:
        raise BookingError(str(e))
    if expected_total is not None and abs(offer["total_amount"] - float(expected_total)) > 0.005:
        raise PriceChanged(offer["total_amount"], offer["currency"], offer["total_pkr"])
    if len(passengers) != len(offer["passengers"]):
        raise BookingError(f"This fare is for {len(offer['passengers'])} passenger(s); you entered {len(passengers)}.")
    if not EMAIL.match(email or ""):
        raise BookingError("Enter a valid contact email.")
    if not PHONE.match(phone or ""):
        raise BookingError("Phone must be in international format, e.g. +923001234567.")
    paxs = validate_passengers(passengers, offer)

    b = Booking(
        reference=_ref(), user_id=user.id, provider=offer["provider"], offer_json=json.dumps(offer),
        passengers_json=json.dumps(paxs), contact_email=email.strip().lower(), contact_phone=phone,
        currency=offer["currency"], total_amount=f'{offer["total_amount"]:.2f}', amount_pkr=offer["total_pkr"],
    )
    db.add(b)
    db.commit()
    return b


def get_booking(db: Session, reference: str, user_id: int | None = None) -> Booking | None:
    """Fetch by reference. Pass user_id to enforce ownership (None for other users' bookings)."""
    q = select(Booking).where(Booking.reference == reference.strip().upper())
    if user_id is not None:
        q = q.where(Booking.user_id == user_id)
    return db.scalar(q)


def list_bookings(db: Session, user_id: int) -> list[Booking]:
    return list(db.scalars(select(Booking).where(Booking.user_id == user_id).order_by(Booking.created_at.desc())))


def fulfill(db: Session, b: Booking) -> None:
    """After successful payment: issue the ticket (Duffel order or local PNR) and email the customer."""
    if b.ticket_status == "issued":
        return
    offer = json.loads(b.offer_json)
    pax = json.loads(b.passengers_json)
    try:
        if b.provider == "duffel":
            res = duffel.create_order(offer, pax, b.contact_email, b.contact_phone)
            b.provider_order_id, b.pnr = res["order_id"], res["pnr"]
            b.documents_json = json.dumps(res["documents"])
        else:
            b.pnr = "".join(secrets.choice(string.ascii_uppercase) for _ in range(6))
            b.provider_order_id = "loc_order_" + secrets.token_hex(5)
            b.documents_json = json.dumps([
                {"type": "electronic_ticket", "number": "176" + "".join(secrets.choice(string.digits) for _ in range(10))}
                for _ in pax])
        b.ticket_status = "issued"
        b.note = ""
    except duffel.DuffelError as e:
        b.ticket_status = "failed"
        b.note = f"Payment received but ticket issuance failed: {e}. Contact support with reference {b.reference}."
    db.commit()
    if b.ticket_status == "issued":
        send_confirmation(b)


def cancel_booking(db: Session, reference: str, user_id: int) -> Booking:
    b = get_booking(db, reference, user_id)
    if not b:
        raise BookingError("Booking not found.")
    if b.status == "cancelled":
        raise BookingError("Booking is already cancelled.")
    if b.status in ("pending_payment", "payment_failed"):
        b.status, b.ticket_status = "cancelled", "cancelled"
        db.commit()
        return b

    offer = json.loads(b.offer_json)
    departs = datetime.fromisoformat(offer["slices"][0]["departure"])
    if departs < datetime.now():
        raise BookingError("This trip has already departed and can't be cancelled.")
    refund = offer["conditions"]["refund"]
    if b.provider == "local" and not refund.get("allowed"):
        raise BookingError(f"The {offer['fare_name']} fare is non-refundable, so it can't be cancelled.")
    if b.provider == "duffel" and b.provider_order_id:
        try:
            res = duffel.cancel_order(b.provider_order_id)
            b.note = f"Airline refund: {res['refund_currency']} {res['refund_amount']}. "
        except duffel.DuffelError as e:
            raise BookingError(f"The airline could not cancel this order: {e}")
    else:
        pen = refund.get("penalty") or 0
        b.note = f"Refund amount: total minus {offer['currency']} {pen:.2f} cancellation fee. "
    b.note += "JazzCash refunds are not automated in this demo - the refund must be processed manually."
    b.status, b.ticket_status = "cancelled", "cancelled"
    db.commit()
    return b


def booking_to_dict(b: Booking) -> dict:
    offer = json.loads(b.offer_json)
    return {
        "reference": b.reference, "status": b.status, "ticket_status": b.ticket_status, "pnr": b.pnr,
        "provider": b.provider, "currency": b.currency, "total_amount": b.total_amount,
        "amount_pkr": b.amount_pkr, "contact_email": b.contact_email, "contact_phone": b.contact_phone,
        "passengers": json.loads(b.passengers_json), "documents": json.loads(b.documents_json),
        "offer": offer, "note": b.note, "created_at": b.created_at.isoformat(timespec="minutes"),
        "departure": offer["slices"][0]["departure"],
        "email_notice": f"A confirmation email was sent to {b.contact_email}." if b.ticket_status == "issued" else "",
        "mock_mailbox": not settings.smtp_host,
    }
