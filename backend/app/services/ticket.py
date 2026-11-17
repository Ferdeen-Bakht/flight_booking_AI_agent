"""Printable e-ticket (HTML). Use the browser's Print -> Save as PDF."""
import html
import json

from ..models import Booking


def _t(iso: str) -> str:
    return iso.replace("T", " ")


def render_html(b: Booking) -> str:
    offer = json.loads(b.offer_json)
    pax = json.loads(b.passengers_json)
    docs = json.loads(b.documents_json)
    e = html.escape
    slices = ""
    for sl in offer["slices"]:
        segs = "".join(
            f"<tr><td>{e(s['flight_number'])}</td><td>{e(s['airline'])}</td>"
            f"<td>{e(s['origin'])} {_t(s['departing_at'])}</td><td>{e(s['destination'])} {_t(s['arriving_at'])}</td></tr>"
            for s in sl["segments"])
        slices += (f"<h3>{e(sl['origin_city'] or sl['origin'])} → {e(sl['destination_city'] or sl['destination'])}</h3>"
                   f"<table><tr><th>Flight</th><th>Airline</th><th>Departs</th><th>Arrives</th></tr>{segs}</table>")
    rows = "".join(
        f"<tr><td>{e(p['title'].title())} {e(p['given_name'])} {e(p['family_name'])}</td>"
        f"<td>{e(docs[i]['number'] if i < len(docs) and docs[i].get('number') else 'pending')}</td></tr>"
        for i, p in enumerate(pax))
    bag = offer["baggage"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>E-ticket {e(b.pnr)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;color:#111}}
table{{width:100%;border-collapse:collapse;margin:6px 0 14px}}td,th{{border:1px solid #ccc;padding:6px;text-align:left;font-size:14px}}
.pnr{{font-size:30px;letter-spacing:4px;font-weight:700}}</style></head><body>
<h1>✈ SkyAgent e-ticket</h1>
<p>Booking PNR<br><span class="pnr">{e(b.pnr)}</span><br>Our ref: {e(b.reference)} · Fare: {e(offer['fare_name'])} ({e(offer['cabin'])})</p>
{slices}
<h3>Passengers</h3><table><tr><th>Name</th><th>Ticket number</th></tr>{rows}</table>
<p>Baggage: {bag['checked']} checked bag(s), {bag['carry_on']} carry-on. Total paid: PKR {b.amount_pkr:,} ({e(b.currency)} {e(b.total_amount)}).</p>
<p style="color:#666;font-size:12px">Demo ticket from a learning project. Not valid for travel unless issued by a live airline order.</p>
<button onclick="print()">Print / Save as PDF</button></body></html>"""
