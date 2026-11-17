"""Duffel API (https://duffel.com/docs/api) – use a *test mode* token (duffel_test_...).

Search -> offers; create order (instant, paid from Duffel balance) -> PNR; cancel order.
In test mode nothing real is ticketed or charged.
"""
import re
from datetime import date

import httpx

from ..airports import BY_IATA
from ..config import settings
from .fx import to_pkr

BASE = "https://api.duffel.com"


class DuffelError(Exception):
    pass


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.duffel_api_key}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _call(method: str, path: str, *, json=None, params=None, timeout=60) -> dict:
    try:
        r = httpx.request(method, BASE + path, headers=_headers(), json=json, params=params, timeout=timeout)
    except httpx.HTTPError as e:
        raise DuffelError(f"Could not reach Duffel: {e}")
    if r.status_code >= 400:
        try:
            errs = r.json().get("errors") or []
            msg = "; ".join(e.get("message", "") for e in errs) or r.text[:200]
        except ValueError:
            msg = r.text[:200]
        raise DuffelError(msg)
    return r.json().get("data")


def _minutes(iso_dur: str | None) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", iso_dur or "")
    if not m:
        return 0
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 1440 + h * 60 + mi


def _cond(c: dict | None) -> dict:
    if not c:
        return {"allowed": None, "penalty": None, "currency": None}
    pen = c.get("penalty_amount")
    return {"allowed": c.get("allowed"), "penalty": float(pen) if pen is not None else None,
            "currency": c.get("penalty_currency")}


def normalize(o: dict) -> dict:
    slices = []
    bag = {"checked": 0, "carry_on": 0}
    for si, s in enumerate(o["slices"]):
        segs = []
        for seg in s["segments"]:
            car = seg.get("marketing_carrier") or {}
            segs.append({
                "airline": car.get("name", ""), "carrier_iata": car.get("iata_code", ""),
                "flight_number": f'{car.get("iata_code", "")}{seg.get("marketing_carrier_flight_number", "")}',
                "origin": seg["origin"]["iata_code"], "destination": seg["destination"]["iata_code"],
                "origin_city": seg["origin"].get("city_name") or seg["origin"].get("name"),
                "destination_city": seg["destination"].get("city_name") or seg["destination"].get("name"),
                "departing_at": seg["departing_at"][:16], "arriving_at": seg["arriving_at"][:16],
                "duration_min": _minutes(seg.get("duration")),
                "aircraft": (seg.get("aircraft") or {}).get("name", ""),
            })
            if si == 0 and seg is s["segments"][0]:
                pax = (seg.get("passengers") or [{}])[0]
                for b in pax.get("baggages") or []:
                    if b["type"] in bag:
                        bag[b["type"]] += b.get("quantity", 0)
        slices.append({
            "origin": s["origin"]["iata_code"], "destination": s["destination"]["iata_code"],
            "origin_city": s["origin"].get("city_name") or s["origin"].get("name"),
            "destination_city": s["destination"].get("city_name") or s["destination"].get("name"),
            "departure": segs[0]["departing_at"], "arrival": segs[-1]["arriving_at"],
            "duration_min": _minutes(s.get("duration")), "stops": len(segs) - 1, "segments": segs,
        })
    cond = o.get("conditions") or {}
    owner = o.get("owner") or {}
    countries = {BY_IATA[x][3] for sl in slices for x in (sl["origin"], sl["destination"]) if x in BY_IATA}
    known = all(sl[k] in BY_IATA for sl in slices for k in ("origin", "destination"))
    first_seg = o["slices"][0]["segments"][0]["passengers"][0] if o["slices"][0]["segments"][0].get("passengers") else {}
    return {
        "id": o["id"], "provider": "duffel",
        "fare_name": o["slices"][0].get("fare_brand_name") or first_seg.get("cabin_class_marketing_name") or "Standard",
        "cabin": first_seg.get("cabin_class", ""),
        "expires_at": (o.get("expires_at") or "")[:19],
        "owner": {"name": owner.get("name", ""), "iata": owner.get("iata_code", "")},
        "currency": o["total_currency"], "base_amount": float(o["base_amount"]),
        "tax_amount": float(o.get("tax_amount") or 0), "total_amount": float(o["total_amount"]),
        "slices": slices, "baggage": bag,
        "conditions": {"refund": _cond(cond.get("refund_before_departure")),
                       "change": _cond(cond.get("change_before_departure"))},
        "passengers": [{"id": p["id"], "type": p.get("type", "adult")} for p in o["passengers"]],
        # without airport country info assume international -> collect passport (safe default)
        "passport_required": (len(countries) > 1) if known else True,
    }


def search(origin: str, destination: str, depart: date, ret: date | None, pax: int, cabin: str) -> list[dict]:
    slices = [{"origin": origin, "destination": destination, "departure_date": depart.isoformat()}]
    if ret:
        slices.append({"origin": destination, "destination": origin, "departure_date": ret.isoformat()})
    data = _call("POST", "/air/offer_requests", params={"return_offers": "true", "supplier_timeout": 15000},
                 json={"data": {"slices": slices, "passengers": [{"type": "adult"}] * pax, "cabin_class": cabin}})
    offers = [normalize(o) for o in (data.get("offers") or [])]
    offers.sort(key=lambda o: to_pkr(o["total_amount"], o["currency"]))
    return offers[:150]


def get_offer(offer_id: str) -> dict:
    return normalize(_call("GET", f"/air/offers/{offer_id}", params={"return_available_services": "false"}))


def suggest(query: str) -> list[dict]:
    data = _call("GET", "/places/suggestions", params={"query": query}, timeout=15)
    return [{"iata": p["iata_code"], "city": p.get("city_name") or p.get("name"), "name": p.get("name"),
             "country": p.get("iata_country_code", "")}
            for p in data if p.get("type") == "airport" and p.get("iata_code")][:10]


def create_order(offer: dict, passengers: list[dict], email: str, phone: str) -> dict:
    """Instant order paid from the Duffel balance (test mode has unlimited test balance)."""
    pax_payload = []
    for op, p in zip(offer["passengers"], passengers):
        item = {
            "id": op["id"], "title": p["title"], "gender": p["gender"],
            "given_name": p["given_name"], "family_name": p["family_name"],
            "born_on": p["born_on"], "email": email, "phone_number": phone,
        }
        if p.get("passport_number"):
            item["identity_documents"] = [{
                "type": "passport", "unique_identifier": p["passport_number"],
                "issuing_country_code": p["passport_country"], "expires_on": p["passport_expiry"],
            }]
        pax_payload.append(item)
    data = _call("POST", "/air/orders", json={"data": {
        "type": "instant", "selected_offers": [offer["id"]], "passengers": pax_payload,
        "payments": [{"type": "balance", "currency": offer["currency"], "amount": f'{offer["total_amount"]:.2f}'}],
    }})
    docs = [{"type": d.get("type"), "number": d.get("unique_identifier")} for d in data.get("documents") or []]
    return {"order_id": data["id"], "pnr": data.get("booking_reference", ""), "documents": docs}


def cancel_order(order_id: str) -> dict:
    q = _call("POST", "/air/order_cancellations", json={"data": {"order_id": order_id}})
    done = _call("POST", f"/air/order_cancellations/{q['id']}/actions/confirm")
    return {"refund_amount": done.get("refund_amount"), "refund_currency": done.get("refund_currency")}
