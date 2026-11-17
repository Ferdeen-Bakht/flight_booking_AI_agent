import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'flights.db'}")

    secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me-please-0123456789")
    token_hours = int(os.getenv("TOKEN_HOURS", "72"))

    duffel_api_key = os.getenv("DUFFEL_API_KEY", "")
    # currency -> PKR (JazzCash charges PKR). Override per env, e.g. FX_USD_PKR=285
    fx = {c: float(os.getenv(f"FX_{c}_PKR", d)) for c, d in
          {"PKR": 1, "USD": 280, "GBP": 355, "EUR": 305, "AED": 76, "SAR": 75, "CAD": 205, "AUD": 185}.items()}

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", "SkyAgent <no-reply@skyagent.local>")

    jazzcash_merchant_id = os.getenv("JAZZCASH_MERCHANT_ID", "")
    jazzcash_password = os.getenv("JAZZCASH_PASSWORD", "")
    jazzcash_salt = os.getenv("JAZZCASH_INTEGRITY_SALT", "")
    jazzcash_post_url = os.getenv(
        "JAZZCASH_POST_URL",
        "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/",
    )

    opensky_username = os.getenv("OPENSKY_USERNAME", "")
    opensky_password = os.getenv("OPENSKY_PASSWORD", "")

    @property
    def provider(self) -> str:
        return "duffel" if self.duffel_api_key else "local"

    @property
    def jazzcash_configured(self) -> bool:
        return bool(self.jazzcash_merchant_id and self.jazzcash_password and self.jazzcash_salt)


settings = Settings()
