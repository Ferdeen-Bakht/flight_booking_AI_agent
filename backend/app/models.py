from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PassengerProfile(Base):
    """Saved traveller details the user can re-use when booking."""
    __tablename__ = "passenger_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(5), default="mr")
    gender: Mapped[str] = mapped_column(String(1), default="m")
    given_name: Mapped[str] = mapped_column(String(50))
    family_name: Mapped[str] = mapped_column(String(50))
    born_on: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    passport_number: Mapped[str] = mapped_column(String(20), default="")
    passport_country: Mapped[str] = mapped_column(String(2), default="")
    passport_expiry: Mapped[str] = mapped_column(String(10), default="")


class OfferCache(Base):
    """Offers we've shown the user (Duffel offers expire; local ones are generated)."""
    __tablename__ = "offer_cache"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # our own ref
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(10))  # duffel | local
    offer_json: Mapped[str] = mapped_column(Text)      # snapshot of the offer at booking time
    passengers_json: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str] = mapped_column(String(120))
    contact_phone: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3))
    total_amount: Mapped[str] = mapped_column(String(20))  # in offer currency, as string
    amount_pkr: Mapped[int] = mapped_column(Integer)
    # pending_payment | paid | payment_failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending_payment")
    # not_issued | issued | failed | cancelled
    ticket_status: Mapped[str] = mapped_column(String(15), default="not_issued")
    pnr: Mapped[str] = mapped_column(String(12), default="")
    provider_order_id: Mapped[str] = mapped_column(String(60), default="")
    documents_json: Mapped[str] = mapped_column(Text, default="[]")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    payments: Mapped[list["Payment"]] = relationship(back_populates="booking")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"))
    txn_ref: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), default="jazzcash")
    mode: Mapped[str] = mapped_column(String(10), default="sandbox")  # sandbox | mock
    status: Mapped[str] = mapped_column(String(15), default="initiated")  # initiated|success|failed
    response_code: Mapped[str] = mapped_column(String(10), default="")
    response_message: Mapped[str] = mapped_column(Text, default="")
    raw_response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    booking: Mapped[Booking] = relationship(back_populates="payments")
