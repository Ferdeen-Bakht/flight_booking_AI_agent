import html
import json
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..auth import current_user
from ..db import get_db
from ..models import Payment
from ..services import bookings as bk
from ..services import jazzcash as jc

router = APIRouter(prefix="/api/payments", tags=["payments"])


class InitiateIn(BaseModel):
    reference: str


@router.get("/config")
def config():
    return {"mode": jc.current_mode()}


@router.post("/jazzcash/initiate")
def initiate(body: InitiateIn, db: Session = Depends(get_db), user=Depends(current_user)):
    b = bk.get_booking(db, body.reference, user.id)
    if not b:
        raise HTTPException(404, "Booking not found")
    if b.status == "paid":
        raise HTTPException(400, "Booking is already paid")
    if b.status == "pending_payment" or b.status == "payment_failed":
        pass
    if b.status == "cancelled":
        raise HTTPException(400, "Booking is cancelled")

    txn_ref = f"T{int(time.time() * 1000)}"  # JazzCash wants a unique ref per attempt (<=20 chars)
    mode = jc.current_mode()
    db.add(Payment(booking_id=b.id, txn_ref=txn_ref, mode=mode))
    db.commit()

    fields = jc.build_checkout(b, txn_ref)
    post_url = settings.jazzcash_post_url if mode == "sandbox" else f"{settings.backend_url}/api/payments/mock/checkout"
    return {"mode": mode, "post_url": post_url, "fields": fields}


@router.post("/jazzcash/return")
async def jazzcash_return(request: Request, db: Session = Depends(get_db)):
    """JazzCash (or our mock) POSTs the transaction result here via the user's browser."""
    form = dict((await request.form()).items())
    txn_ref = form.get("pp_TxnRefNo", "")
    payment = db.scalar(select(Payment).where(Payment.txn_ref == txn_ref))
    if not payment:
        return RedirectResponse(f"{settings.frontend_url}/?payment=unknown", status_code=303)

    booking = bk.get_booking(db, payment.booking.reference)  # same session; no ownership check on the gateway callback
    verified = jc.verify_response(form)
    code = form.get("pp_ResponseCode", "")
    payment.response_code = code
    payment.response_message = form.get("pp_ResponseMessage", "")
    payment.raw_response = json.dumps({k: v for k, v in form.items() if k != "pp_Password"})

    if not verified:
        payment.status = "failed"
        payment.response_message = "Invalid secure hash - response rejected. " + payment.response_message
        result = "tampered"
    elif code == jc.SUCCESS_CODE:
        payment.status = "success"
        if booking.status != "cancelled":
            booking.status = "paid"
            db.commit()
            bk.fulfill(db, booking)  # issue the ticket + send confirmation email
        result = "success"
    else:
        payment.status = "failed"
        if booking.status == "pending_payment":
            booking.status = "payment_failed"
        result = "failed"
    db.commit()
    ref = booking.reference
    return RedirectResponse(f"{settings.frontend_url}/?payment={result}&ref={ref}#/confirmation/{ref}", status_code=303)


# ------------------------------------------------------------------ MOCK
@router.post("/mock/checkout", response_class=HTMLResponse)
async def mock_checkout(request: Request):
    """Stand-in for JazzCash's hosted page so you can learn the flow without credentials."""
    form = dict((await request.form()).items())
    if not jc.verify_response(form):
        return HTMLResponse("Invalid request hash", status_code=400)

    def signed(code: str, msg: str) -> dict:
        return jc.sign_mock_response({
            "pp_TxnRefNo": form["pp_TxnRefNo"], "pp_Amount": form["pp_Amount"],
            "pp_TxnCurrency": form["pp_TxnCurrency"], "pp_BillReference": form["pp_BillReference"],
            "pp_TxnDateTime": form["pp_TxnDateTime"], "pp_MerchantID": form["pp_MerchantID"],
            "pp_ResponseCode": code, "pp_ResponseMessage": msg,
            "pp_RetreivalReferenceNo": form["pp_TxnRefNo"][-12:],
        })

    def button(label: str, color: str, fields: dict) -> str:
        inputs = "".join(f'<input type="hidden" name="{k}" value="{html.escape(str(v))}">' for k, v in fields.items())
        return (f'<form method="post" action="{settings.backend_url}/api/payments/jazzcash/return">{inputs}'
                f'<button style="background:{color}">{label}</button></form>')

    amount = int(form["pp_Amount"]) / 100
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>JazzCash (MOCK)</title>
<style>body{{font-family:system-ui;background:#f5f5f5;display:grid;place-items:center;height:100vh;margin:0}}
.c{{background:#fff;padding:32px;border-radius:12px;box-shadow:0 4px 24px #0002;width:360px;text-align:center}}
.t{{color:#d71920;font-weight:700;font-size:22px}}.m{{background:#fff3cd;padding:6px;border-radius:6px;font-size:12px}}
button{{color:#fff;border:0;padding:12px;width:100%;border-radius:8px;font-size:15px;margin-top:10px;cursor:pointer}}</style></head>
<body><div class="c"><div class="t">JazzCash</div><div class="m">MOCK sandbox - no real money, no credentials</div>
<p>{html.escape(form['pp_Description'])}</p><h2>PKR {amount:,.0f}</h2>
{button('Pay (simulate success)', '#28a745', signed('000', 'Thank you for Using JazzCash, your transaction was successful.'))}
{button('Decline (simulate failure)', '#dc3545', signed('124', 'Transaction declined (simulated).'))}
</div></body></html>"""
    return HTMLResponse(page)
