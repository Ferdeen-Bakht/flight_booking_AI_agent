"""Live flight data from the free OpenSky Network REST API (no key needed)."""
import httpx

from ..airports import BY_IATA
from ..config import settings

OPENSKY_URL = "https://opensky-network.org/api/states/all"

ICAO_AIRLINES = {
    "PIA": "PIA", "ABQ": "Airblue", "SEE": "SereneAir", "UAE": "Emirates", "QTR": "Qatar Airways",
    "SVA": "Saudia", "THY": "Turkish Airlines", "ETD": "Etihad", "BAW": "British Airways",
    "FDB": "flydubai", "ABY": "Air Arabia", "SIA": "Singapore Airlines",
}


def live_flights_near(iata: str, radius_deg: float = 1.5) -> dict:
    ap = BY_IATA.get(iata.upper())
    if not ap:
        return {"ok": False, "error": f"unknown airport {iata}", "flights": []}
    lat, lon = ap[4], ap[5]
    auth = (settings.opensky_username, settings.opensky_password) if settings.opensky_username else None
    try:
        r = httpx.get(
            OPENSKY_URL,
            params={"lamin": lat - radius_deg, "lamax": lat + radius_deg,
                    "lomin": lon - radius_deg, "lomax": lon + radius_deg},
            auth=auth, timeout=12,
        )
        r.raise_for_status()
        states = r.json().get("states") or []
    except Exception as e:  # network down, rate-limited, etc.
        return {"ok": False, "error": f"OpenSky unavailable: {e}", "flights": []}

    flights = []
    for s in states:
        callsign = (s[1] or "").strip()
        flights.append({
            "callsign": callsign,
            "airline": ICAO_AIRLINES.get(callsign[:3], ""),
            "country": s[2],
            "longitude": s[5], "latitude": s[6],
            "altitude_m": s[7], "on_ground": s[8],
            "speed_ms": s[9], "heading": s[10],
        })
    return {"ok": True, "airport": iata.upper(), "count": len(flights), "flights": flights[:60]}
