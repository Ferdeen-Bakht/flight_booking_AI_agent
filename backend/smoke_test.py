r"""End-to-end smoke test (no LLM): search -> verify -> book -> mock JazzCash pay -> ticket -> cancel rules.
Run:  .venv\Scripts\python smoke_test.py   (uses the local demo provider unless DUFFEL_API_KEY is set)
"""
import datetime as dt
import os
import re

os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"
for k in ("JAZZCASH_MERCHANT_ID", "SMTP_HOST"):
    os.environ.pop(k, None)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

today = dt.date.today()
PAX = {"title": "mr", "gender": "m", "given_name": "Ali", "family_name": "Khan", "born_on": "1990-05-01",
       "passport_number": "AB1234567", "passport_country": "PK", "passport_expiry": "2035-01-01"}

with TestClient(app) as c:
    print(c.get("/api/meta").json()["provider"])
    r = c.post("/api/flights/search", json={"origin": "Karachi", "destination": "DXB",
                                            "departure_date": str(today + dt.timedelta(days=5)),
                                            "return_date": str(today + dt.timedelta(days=12)),
                                            "passengers": 1, "cabin_class": "economy"})
    assert r.status_code == 200, r.text
    res = r.json()
    its = res["itineraries"]
    print("itineraries:", len(its), "| fares on first:", [f["fare_name"] for f in its[0]["fares"]],
          "| stops:", [i["stops"] for i in its], "| slices:", len(its[0]["slices"]))
    assert any(i["stops"] == 1 for i in its) and len(its[0]["slices"]) == 2
    bad = c.post("/api/flights/search", json={"origin": "KHI", "destination": "KHI", "departure_date": str(today)})
    assert bad.status_code == 400

    basic = its[0]["fares"][0]
    flex = its[0]["fares"][-1]
    assert c.get(f"/api/offers/{basic['id']}").json()["total_pkr"] == basic["total_pkr"]

    body = {"offer_id": basic["id"], "passengers": [PAX], "contact_email": "ali@x.com",
            "contact_phone": "+923001234567", "expected_total": basic["total_amount"], "approved": True}
    assert c.post("/api/bookings", json=body).status_code == 401
    tok = c.post("/api/auth/signup", json={"name": "Ali Khan", "email": "ali@x.com", "password": "password123"}).json()["token"]
    H = {"Authorization": f"Bearer {tok}"}
    assert c.post("/api/bookings", json={**body, "approved": False}, headers=H).status_code == 400
    assert c.post("/api/bookings", json={**body, "expected_total": 1.0}, headers=H).status_code == 409  # price changed
    assert c.post("/api/bookings", json={**body, "passengers": [{**PAX, "passport_number": ""}]}, headers=H).status_code == 400
    assert c.post("/api/bookings", json={**body, "contact_phone": "0300"}, headers=H).status_code == 400
    b = c.post("/api/bookings", json=body, headers=H)
    assert b.status_code == 200, b.text
    b = b.json()
    print("booking:", b["reference"], b["status"], b["ticket_status"], "PKR", b["amount_pkr"])

    init = c.post("/api/payments/jazzcash/initiate", json={"reference": b["reference"]}, headers=H).json()
    mk = c.post(init["post_url"].replace("http://localhost:8000", ""), data=init["fields"])
    fields = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', mk.text.split("<form")[1]))
    r = c.post("/api/payments/jazzcash/return", data=fields, follow_redirects=False)
    print("return ->", r.headers["location"])
    got = c.get(f"/api/bookings/{b['reference']}", headers=H).json()
    print("after payment:", got["status"], got["ticket_status"], "PNR", got["pnr"], "|", got["email_notice"])
    assert got["status"] == "paid" and got["ticket_status"] == "issued" and len(got["pnr"]) >= 5
    assert os.path.exists(f"outbox/{b['reference']}.txt")
    t = c.get(f"/api/bookings/{b['reference']}/ticket", headers=H)
    assert t.status_code == 200 and got["pnr"] in t.text

    tok2 = c.post("/api/auth/signup", json={"name": "Eve", "email": "eve@x.com", "password": "password123"}).json()["token"]
    assert c.get(f"/api/bookings/{b['reference']}", headers={"Authorization": f"Bearer {tok2}"}).status_code == 404
    fields["pp_Amount"] = "1"
    assert "tampered" in c.post("/api/payments/jazzcash/return", data=fields, follow_redirects=False).headers["location"]

    print("cancel basic ->", c.post(f"/api/bookings/{b['reference']}/cancel", headers=H).json()["detail"])

    b2 = c.post("/api/bookings", json={**body, "offer_id": flex["id"], "expected_total": flex["total_amount"]}, headers=H).json()
    print("cancel unpaid ->", c.post(f"/api/bookings/{b2['reference']}/cancel", headers=H).json()["status"])
    p = c.post("/api/profiles", json={"given_name": "Ali", "family_name": "Khan", "born_on": "1990-05-01"}, headers=H).json()
    assert len(c.get("/api/profiles", headers=H).json()) == 1
    c.delete(f"/api/profiles/{p['id']}", headers=H)
    print("ALL OK")

from app.db import engine  # noqa: E402

engine.dispose()
os.remove("smoke_test.db")
