"""Offline demo provider: deterministic fake flights in the same shape as Duffel offers.

Used when DUFFEL_API_KEY is not set. Prices are generated in USD so the FX -> PKR
path is exercised exactly like it is with Duffel. Times are naive "local" times.
"""
import math
import random
import uuid
from datetime import date, datetime, time, timedelta

from ..airports import BY_IATA, city_of

AIRLINES = {
    "PK": "Pakistan International Airlines", "PA": "Airblue", "ER": "SereneAir",
    "EK": "Emirates", "QR": "Qatar Airways", "SV": "Saudia", "TK": "Turkish Airlines",
    "EY": "Etihad Airways", "BA": "British Airways",
}
CARRIERS_BY_COUNTRY = {
    "PK": ["PK", "PA", "ER"], "AE": ["EK", "EY", "PK"], "QA": ["QR", "PK"], "SA": ["SV", "PK"],
    "TR": ["TK"], "GB": ["BA", "PK"], "US": ["PK", "QR"], "SG": ["PK", "QR"], "MY": ["PK", "QR"],
}
HUBS = ["DXB", "DOH", "IST", "AUH", "JED"]
# name, price multiplier, checked bags, refund rule, change rule  (penalties in USD)
FARES = [
    ("Basic", 1.00, 0, {"allowed": False, "penalty": None}, {"allowed": True, "penalty": 40.0}),
    ("Standard", 1.18, 1, {"allowed": True, "penalty": 60.0}, {"allowed": True, "penalty": 25.0}),
    ("Flex", 1.45, 2, {"allowed": True, "penalty": 0.0}, {"allowed": True, "penalty": 0.0}),
]
CABIN_MULT = {"economy": 1.0, "premium_economy": 1.6, "business": 3.2, "first": 5.0}
AIRCRAFT = ["Boeing 737-800", "Airbus A320", "Airbus A321neo", "Boeing 777-300ER", "Airbus A330-300"]


def _km(a: str, b: str) -> float:
    A, B = BY_IATA[a], BY_IATA[b]
    la1, lo1, la2, lo2 = map(math.radians, (A[4], A[5], B[4], B[5]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _fly_min(km: float) -> int:
    return int(35 + km / 780 * 60)


def _carrier(rng, o: str, d: str) -> str:
    ctry = BY_IATA[d][3] if BY_IATA[o][3] == "PK" else BY_IATA[o][3]
    return rng.choice(CARRIERS_BY_COUNTRY.get(ctry, ["PK"]))


def _segment(rng, code: str, o: str, d: str, dep: datetime) -> dict:
    dur = _fly_min(_km(o, d))
    return {
        "airline": AIRLINES[code], "carrier_iata": code, "flight_number": f"{code}{rng.randint(100, 989)}",
        "origin": o, "destination": d, "origin_city": city_of(o), "destination_city": city_of(d),
        "departing_at": dep.isoformat(timespec="minutes"),
        "arriving_at": (dep + timedelta(minutes=dur)).isoformat(timespec="minutes"),
        "duration_min": dur, "aircraft": rng.choice(AIRCRAFT),
    }


def _direction(o: str, d: str, day: date, n: int = 6) -> list[dict]:
    rng = random.Random(f"{o}{d}{day}")
    direct_km = _km(o, d)
    base_usd = 35 + 0.055 * direct_km
    out = []
    hours = [1, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
    if day == date.today():  # don't offer flights that have already left (or leave within 2h)
        hours = [h for h in hours if h > datetime.now().hour + 2]
    if not hours:
        return []
    for i in range(n):
        dep = datetime.combine(day, time(rng.choice(hours), rng.choice([0, 10, 25, 40, 55])))
        if i < 4:  # non-stop
            segs = [_segment(rng, _carrier(rng, o, d), o, d, dep)]
            price = base_usd * rng.uniform(0.92, 1.25)
        else:  # one stop via a hub
            hub = rng.choice([h for h in HUBS if h not in (o, d)])
            s1 = _segment(rng, _carrier(rng, o, hub), o, hub, dep)
            lay = rng.randint(80, 240)
            dep2 = datetime.fromisoformat(s1["arriving_at"]) + timedelta(minutes=lay)
            s2 = _segment(rng, _carrier(rng, hub, d), hub, d, dep2)
            segs = [s1, s2]
            price = base_usd * rng.uniform(0.7, 0.9)
        dur = int((datetime.fromisoformat(segs[-1]["arriving_at"]) - datetime.fromisoformat(segs[0]["departing_at"])).total_seconds() // 60)
        out.append({
            "origin": o, "destination": d, "origin_city": city_of(o), "destination_city": city_of(d),
            "departure": segs[0]["departing_at"], "arrival": segs[-1]["arriving_at"],
            "duration_min": dur, "stops": len(segs) - 1, "segments": segs, "_price": price,
        })
    return out


def search(origin: str, destination: str, depart: date, ret: date | None, pax: int, cabin: str) -> list[dict]:
    outbound = _direction(origin, destination, depart)
    inbound = _direction(destination, origin, ret) if ret else None
    expires = (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
    intl = BY_IATA[origin][3] != BY_IATA[destination][3]
    offers = []
    if inbound is not None:
        outbound = outbound[: len(inbound)]
    for i, out in enumerate(outbound):
        parts = [out] + ([inbound[i]] if inbound else [])
        slices = [{k: v for k, v in p.items() if k != "_price"} for p in parts]
        base = sum(p["_price"] for p in parts) * CABIN_MULT.get(cabin, 1.0)
        for name, mult, bags, refund, change in FARES:
            b = round(base * mult * pax, 2)
            tax = round(b * 0.18, 2)
            offers.append({
                "id": "loc_" + uuid.uuid4().hex[:20], "provider": "local", "fare_name": name, "cabin": cabin,
                "expires_at": expires,
                "owner": {"name": slices[0]["segments"][0]["airline"], "iata": slices[0]["segments"][0]["carrier_iata"]},
                "currency": "USD", "base_amount": b, "tax_amount": tax, "total_amount": round(b + tax, 2),
                "slices": slices,
                "baggage": {"checked": bags, "carry_on": 1},
                "conditions": {
                    "refund": {**refund, "currency": "USD"},
                    "change": {**change, "currency": "USD"},
                },
                "passengers": [{"id": f"pas_{k}", "type": "adult"} for k in range(pax)],
                "passport_required": intl,
            })
    return offers
