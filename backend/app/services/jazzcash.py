"""JazzCash Hosted Checkout (Page Redirection) – sandbox integration.

Flow:
  1. build_checkout()  -> dict of pp_* fields + pp_SecureHash; the browser POSTs them
                          to JazzCash's sandbox merchant form.
  2. User pays on JazzCash's page; JazzCash POSTs the result to pp_ReturnURL.
  3. verify_response() recomputes the hash to make sure the callback is genuine.

pp_SecureHash = HMAC-SHA256( key = IntegritySalt,
                             msg = IntegritySalt + '&' + non-empty pp_* values sorted by field name, joined by '&' )
                hex, upper-case.

If no sandbox credentials are configured we run in MOCK mode: same hash logic,
but the "JazzCash page" is served by our own backend (see routers/payments.py).
"""
import hashlib
import hmac
from datetime import datetime, timedelta

from ..config import settings
from ..models import Booking

MOCK_SALT = "mock-integrity-salt"
SUCCESS_CODE = "000"


def secure_hash(fields: dict, salt: str) -> str:
    items = sorted((k, str(v)) for k, v in fields.items() if k != "pp_SecureHash" and v not in (None, ""))
    message = salt + "".join("&" + v for _, v in items)
    return hmac.new(salt.encode(), message.encode(), hashlib.sha256).hexdigest().upper()


def current_mode() -> str:
    return "sandbox" if settings.jazzcash_configured else "mock"


def _salt() -> str:
    return settings.jazzcash_salt if settings.jazzcash_configured else MOCK_SALT


def build_checkout(booking: Booking, txn_ref: str) -> dict:
    now = datetime.now()
    fields = {
        "pp_Version": "1.1",
        "pp_TxnType": "",
        "pp_Language": "EN",
        "pp_MerchantID": settings.jazzcash_merchant_id or "MOCK",
        "pp_SubMerchantID": "",
        "pp_Password": settings.jazzcash_password or "mock",
        "pp_BankID": "TBANK",
        "pp_ProductID": "RETL",
        "pp_TxnRefNo": txn_ref,
        "pp_Amount": str(booking.amount_pkr * 100),  # paisa
        "pp_TxnCurrency": "PKR",
        "pp_TxnDateTime": now.strftime("%Y%m%d%H%M%S"),
        "pp_BillReference": booking.reference,
        "pp_Description": f"Flight booking {booking.reference}",
        "pp_TxnExpiryDateTime": (now + timedelta(hours=1)).strftime("%Y%m%d%H%M%S"),
        "pp_ReturnURL": f"{settings.backend_url}/api/payments/jazzcash/return",
        "ppmpf_1": "", "ppmpf_2": "", "ppmpf_3": "", "ppmpf_4": "", "ppmpf_5": "",
    }
    fields["pp_SecureHash"] = secure_hash(fields, _salt())
    return fields


def verify_response(fields: dict) -> bool:
    given = str(fields.get("pp_SecureHash", "")).upper()
    return bool(given) and hmac.compare_digest(given, secure_hash(fields, _salt()))


def sign_mock_response(fields: dict) -> dict:
    """Used by the mock checkout page to emulate a signed JazzCash callback."""
    fields = dict(fields)
    fields["pp_SecureHash"] = secure_hash(fields, MOCK_SALT)
    return fields
