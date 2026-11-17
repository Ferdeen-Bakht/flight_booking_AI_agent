from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.graph import run_agent
from ..airports import AIRPORTS
from ..auth import current_user, optional_user
from ..config import settings
from ..db import get_db
from ..models import PassengerProfile, User
from ..services import bookings as bk
from ..services import duffel, offers, opensky, ticket

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/meta")
def meta():
    return {"provider": settings.provider, "fx": settings.fx}


@router.get("/airports")
def airports(q: str = ""):
    ql = q.strip().lower()
    if ql and settings.provider == "duffel" and len(ql) >= 2:
        try:
            return duffel.suggest(ql)
        except duffel.DuffelError:
            pass
    return [{"iata": a[0], "city": a[2], "name": a[2], "country": a[3]} for a in AIRPORTS
            if not ql or ql in a[2].lower() or ql in a[0].lower()]


# ------------------------------------------------------------------ search
class SearchIn(BaseModel):
    origin: str = Field(min_length=2, max_length=40)
    destination: str = Field(min_length=2, max_length=40)
    departure_date: date
    return_date: date | None = None
    passengers: int = Field(default=1, ge=1, le=9)
    cabin_class: str = "economy"


@router.post("/flights/search")
def search(body: SearchIn, db: Session = Depends(get_db)):
    try:
        return offers.search(db, body.origin, body.destination, body.departure_date, body.return_date,
                             body.passengers, body.cabin_class)
    except offers.OfferError as e:
        raise HTTPException(400, str(e))


@router.get("/offers/{offer_id}")
def get_offer(offer_id: str, db: Session = Depends(get_db)):
    """Live offer (final price verification)."""
    try:
        return offers.get_offer(db, offer_id, refresh=True)
    except offers.OfferError as e:
        raise HTTPException(409, str(e))


@router.get("/flights/live")
def live(airport: str = "KHI"):
    """Real aircraft currently flying near an airport (OpenSky)."""
    return opensky.live_flights_near(airport)


# ---------------------------------------------------------------- bookings
class PassengerIn(BaseModel):
    title: str
    gender: str
    given_name: str
    family_name: str
    born_on: str
    passport_number: str | None = None
    passport_country: str | None = None
    passport_expiry: str | None = None


class BookingIn(BaseModel):
    offer_id: str
    passengers: list[PassengerIn] = Field(min_length=1, max_length=9)
    contact_email: str
    contact_phone: str
    expected_total: float | None = None
    approved: bool = False  # explicit user approval of the booking + payment


@router.post("/bookings")
def create_booking(body: BookingIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not body.approved:
        raise HTTPException(400, "You must explicitly approve the booking and payment.")
    try:
        b = bk.create_booking(db, user, body.offer_id, [p.model_dump() for p in body.passengers],
                              body.contact_email, body.contact_phone, body.expected_total)
    except bk.PriceChanged as e:
        raise HTTPException(409, {"message": str(e), "new_total": e.new_total, "currency": e.currency,
                                  "new_pkr": e.new_pkr})
    except bk.BookingError as e:
        raise HTTPException(400, str(e))
    return bk.booking_to_dict(b)


@router.get("/bookings")
def list_bookings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [bk.booking_to_dict(b) for b in bk.list_bookings(db, user.id)]


@router.get("/bookings/{reference}")
def get_booking(reference: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = bk.get_booking(db, reference, user.id)
    if not b:
        raise HTTPException(404, "Booking not found")
    return bk.booking_to_dict(b)


@router.post("/bookings/{reference}/cancel")
def cancel(reference: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        return bk.booking_to_dict(bk.cancel_booking(db, reference, user.id))
    except bk.BookingError as e:
        raise HTTPException(400, str(e))


@router.get("/bookings/{reference}/ticket", response_class=HTMLResponse)
def get_ticket(reference: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    b = bk.get_booking(db, reference, user.id)
    if not b:
        raise HTTPException(404, "Booking not found")
    if b.ticket_status != "issued":
        raise HTTPException(409, "Ticket has not been issued yet.")
    return ticket.render_html(b)


# ---------------------------------------------------------------- profiles
class ProfileIn(BaseModel):
    title: str = "mr"
    gender: str = "m"
    given_name: str = Field(min_length=1, max_length=50)
    family_name: str = Field(min_length=1, max_length=50)
    born_on: str
    passport_number: str = ""
    passport_country: str = ""
    passport_expiry: str = ""


def _prof(p: PassengerProfile) -> dict:
    return {c: getattr(p, c) for c in ("id", "title", "gender", "given_name", "family_name", "born_on",
                                       "passport_number", "passport_country", "passport_expiry")}


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [_prof(p) for p in db.scalars(select(PassengerProfile).where(PassengerProfile.user_id == user.id))]


@router.post("/profiles")
def add_profile(body: ProfileIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        date.fromisoformat(body.born_on)
    except ValueError:
        raise HTTPException(400, "Enter a valid date of birth.")
    p = PassengerProfile(user_id=user.id, **body.model_dump())
    db.add(p)
    db.commit()
    return _prof(p)


@router.delete("/profiles/{pid}")
def delete_profile(pid: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    p = db.get(PassengerProfile, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# -------------------------------------------------------------------- chat
class ChatIn(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=2000)


@router.post("/chat")
def chat(body: ChatIn, user: User | None = Depends(optional_user)):
    # sync def -> FastAPI runs it in a worker thread, so the blocking LLM call doesn't stall the loop
    return run_agent(body.session_id, body.message, user.id if user else None)
