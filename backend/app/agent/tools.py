"""Tools the agent can call. Each opens its own DB session and returns plain dicts."""
from datetime import date

from ..db import SessionLocal
from ..services import bookings as bk
from ..services import offers


def search_flights_tool(origin: str, destination: str, depart: str, ret: str | None = None,
                        passengers: int = 1, cabin: str = "economy") -> dict:
    try:
        d1 = date.fromisoformat(str(depart))
        d2 = date.fromisoformat(str(ret)) if ret else None
    except ValueError:
        return {"error": "Please give dates as YYYY-MM-DD (e.g. 2026-12-20)."}
    with SessionLocal() as db:
        try:
            return offers.search(db, origin, destination, d1, d2, passengers, cabin, limit=40)
        except offers.OfferError as e:
            return {"error": str(e)}


def get_booking_tool(user_id: int, reference: str) -> dict:
    with SessionLocal() as db:
        b = bk.get_booking(db, reference, user_id)
        return bk.booking_to_dict(b) if b else {"error": f"No booking found with reference {reference}."}


def cancel_booking_tool(user_id: int, reference: str) -> dict:
    with SessionLocal() as db:
        try:
            return bk.booking_to_dict(bk.cancel_booking(db, reference, user_id))
        except bk.BookingError as e:
            return {"error": str(e)}
