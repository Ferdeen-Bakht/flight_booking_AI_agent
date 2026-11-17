from ..config import settings


def to_pkr(amount: float, currency: str) -> int:
    rate = settings.fx.get(currency.upper())
    if rate is None:
        raise ValueError(f"No FX rate for {currency}; set FX_{currency.upper()}_PKR in .env")
    return int(round(float(amount) * rate))
