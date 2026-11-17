"""Confirmation email. Sends via SMTP when configured, otherwise saves to backend/outbox/."""
import json
import smtplib
from email.message import EmailMessage

from ..config import BASE_DIR, settings


def send_confirmation(b) -> str:
    offer = json.loads(b.offer_json)
    lines = [f"Hi {json.loads(b.passengers_json)[0]['given_name']},", "",
             f"Your booking is confirmed. PNR: {b.pnr}  (ref {b.reference})", ""]
    for sl in offer["slices"]:
        for s in sl["segments"]:
            lines.append(f"  {s['flight_number']}  {s['origin']} {s['departing_at'].replace('T', ' ')} -> "
                         f"{s['destination']} {s['arriving_at'].replace('T', ' ')}")
    lines += ["", f"Total paid: PKR {b.amount_pkr:,}", "", "You can download your e-ticket from My trips.", "- SkyAgent"]
    msg = EmailMessage()
    msg["Subject"] = f"Booking confirmed - {b.pnr}"
    msg["From"], msg["To"] = settings.smtp_from, b.contact_email
    msg.set_content("\n".join(lines))
    if settings.smtp_host:
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                s.starttls()
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
            return "sent"
        except Exception as e:  # don't fail the booking because email failed
            return f"smtp failed: {e}"
    out = BASE_DIR / "outbox"
    out.mkdir(exist_ok=True)
    (out / f"{b.reference}.txt").write_text(str(msg), encoding="utf-8")
    return "saved to outbox"
