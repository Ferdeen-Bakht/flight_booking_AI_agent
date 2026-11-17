"""Small bundled airport table (IATA, ICAO, city, country, lat, lon)."""

AIRPORTS = [
    ("KHI", "OPKC", "Karachi", "PK", 24.9065, 67.1608),
    ("LHE", "OPLA", "Lahore", "PK", 31.5216, 74.4036),
    ("ISB", "OPIS", "Islamabad", "PK", 33.5605, 72.8495),
    ("PEW", "OPPS", "Peshawar", "PK", 33.9939, 71.5146),
    ("MUX", "OPMT", "Multan", "PK", 30.2032, 71.4191),
    ("DXB", "OMDB", "Dubai", "AE", 25.2532, 55.3657),
    ("AUH", "OMAA", "Abu Dhabi", "AE", 24.4330, 54.6511),
    ("DOH", "OTHH", "Doha", "QA", 25.2731, 51.6081),
    ("JED", "OEJN", "Jeddah", "SA", 21.6796, 39.1565),
    ("RUH", "OERK", "Riyadh", "SA", 24.9576, 46.6988),
    ("IST", "LTFM", "Istanbul", "TR", 41.2753, 28.7519),
    ("LHR", "EGLL", "London", "GB", 51.4700, -0.4543),
    ("JFK", "KJFK", "New York", "US", 40.6413, -73.7781),
    ("SIN", "WSSS", "Singapore", "SG", 1.3644, 103.9915),
    ("KUL", "WMKK", "Kuala Lumpur", "MY", 2.7456, 101.7099),
]

BY_IATA = {a[0]: a for a in AIRPORTS}

# extra aliases a user might type
ALIASES = {
    "isloo": "ISB", "pindi": "ISB", "rawalpindi": "ISB", "nyc": "JFK", "newyork": "JFK",
    "kl": "KUL", "abudhabi": "AUH", "kuala": "KUL", "london": "LHR", "karachi": "KHI",
}


def resolve_airport(text: str | None) -> str | None:
    """Turn 'karachi', 'KHI', 'Karachi (KHI)' into an IATA code, or None."""
    if not text:
        return None
    t = str(text).strip()
    up = t.upper()
    if up in BY_IATA:
        return up
    low = "".join(c for c in t.lower() if c.isalnum())
    if low in ALIASES:
        return ALIASES[low]
    for iata, icao, city, *_ in AIRPORTS:
        c = "".join(ch for ch in city.lower() if ch.isalnum())
        if low == c or c in low or iata.lower() in t.lower().split() or icao.lower() == low:
            return iata
    return None


def city_of(iata: str) -> str:
    return BY_IATA[iata][2] if iata in BY_IATA else iata
