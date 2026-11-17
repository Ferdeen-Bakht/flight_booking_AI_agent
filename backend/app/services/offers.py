"""Provider-agnostic flight search + offer cache.

Search returns *itineraries* (same flights) each carrying several *fares* (offers).
"""
import json
from datetime import date, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..airports import resolve_airport
from ..config import settings
from ..models import OfferCache
from . import duffel, local
from .fx import to_pkr

CABINS = ("economy", "premium_economy", "business", "first")


class OfferError(Exception):
    """Search/offer problem the user should see (bad input, expired offer, provider down)."""


def _price(o: dict) -> dict:
    o["total_pkr"] = to_pkr(o["total_amount"], o["currency"])
    return o


def _key(o: dict) -> str:
    return "|".join(f'{s["flight_number"]}@{s["departing_at"]}' for sl in o["slices"] for s in sl["segments"])


def search(db: Session, origin: str, destination: str, depart: date, ret: date | None,
           passengers: int, cabin: str, limit: int = 40) -> dict:
    o, d = resolve_airport(origin), resolve_airport(destination)
    if not o or not d:
        # Duffel accepts any IATA code, so trust a 3-letter code when using Duffel
        o = o or (origin.upper() if settings.provider == "duffel" and len(origin) == 3 else None)
        d = d or (destination.upper() if settings.provider == "duffel" and len(destination) == 3 else None)
    if not o:
        raise OfferError(f"I don't know the airport '{origin}'.")
    if not d:
        raise OfferError(f"I don't know the airport '{destination}'.")
    if o == d:
        raise OfferError("Origin and destination must be different.")
    if depart < date.today():
        raise OfferError("Departure date can't be in the past.")
    if ret and ret < depart:
        raise OfferError("Return date can't be before the departure date.")
    if not 1 <= passengers <= 9:
        raise OfferError("Passengers must be between 1 and 9.")
    if cabin not in CABINS:
        raise OfferError("Unknown cabin class.")

    try:
        raw = (duffel.search if settings.provider == "duffel" else local.search)(o, d, depart, ret, passengers, cabin)
    except duffel.DuffelError as e:
        raise OfferError(f"Flight provider error: {e}")
    offers = [_price(x) for x in raw]
    _cache(db, offers)

    groups: dict[str, list[dict]] = {}
    for x in offers:
        groups.setdefault(_key(x), []).append(x)
    its = []
    for key, fares in groups.items():
        fares.sort(key=lambda f: f["total_pkr"])
        head = fares[0]
        its.append({
            "key": key, "owner": head["owner"], "slices": head["slices"],
            "stops": max(s["stops"] for s in head["slices"]),
            "duration_min": sum(s["duration_min"] for s in head["slices"]),
            "min_total_pkr": head["total_pkr"], "passport_required": head["passport_required"],
            "fares": [{k: v for k, v in f.items() if k != "slices"} for f in fares],
        })
    its.sort(key=lambda i: i["min_total_pkr"])
    return {
        "provider": settings.provider,
        "query": {"origin": o, "destination": d, "departure_date": depart.isoformat(),
                  "return_date": ret.isoformat() if ret else None, "passengers": passengers,
                  "cabin_class": cabin, "trip_type": "round_trip" if ret else "one_way"},
        "itineraries": its[:limit],
    }


def _cache(db: Session, offers: list[dict]) -> None:
    db.execute(delete(OfferCache).where(OfferCache.expires_at < datetime.now()))
    for o in offers:
        exp = datetime.fromisoformat(o["expires_at"]) if o.get("expires_at") else datetime.now()
        db.merge(OfferCache(id=o["id"], payload=json.dumps(o), expires_at=exp))
    db.commit()


def get_offer(db: Session, offer_id: str, refresh: bool = False) -> dict:
    """Return the offer. With refresh=True, ask the provider for the live price (final price check)."""
    row = db.get(OfferCache, offer_id)
    if not row:
        raise OfferError("This fare is no longer available. Please search again.")
    if row.expires_at < datetime.now():
        raise OfferError("This fare has expired. Please search again.")
    offer = json.loads(row.payload)
    if refresh and offer["provider"] == "duffel":
        try:
            offer = _price(duffel.get_offer(offer_id))
        except duffel.DuffelError as e:
            raise OfferError(f"This fare is no longer available ({e}). Please search again.")
        db.merge(OfferCache(id=offer_id, payload=json.dumps(offer),
                            expires_at=datetime.fromisoformat(offer["expires_at"]) if offer["expires_at"] else row.expires_at))
        db.commit()
    return offer
