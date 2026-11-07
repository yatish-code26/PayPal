"""FreightGuard Configuration Module
Manages application mode, paths, and sandbox configuration.
Guarantees strict isolation of external credentials.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = Path(os.getenv("FREIGHTGUARD_DB_PATH", str(DATA_DIR / "freightguard.db")))

# Mode configuration:
# 'LOCAL_DEMO': Deterministic local simulation of AI and PayPal sandbox (default, 100% offline)
# 'LIVE_SANDBOX': Live external PayPal Sandbox API (requires explicit user authorization)
APP_MODE = os.getenv("FREIGHTGUARD_MODE", "LOCAL_DEMO")

# PayPal Sandbox Configuration (Server-side only, never exposed to browser)
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

# AI Engine Provider Configuration (Groq, Gemini, OpenAI)
AI_PROVIDER = os.getenv("AI_PROVIDER", "LOCAL_DETERMINISTIC")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Security & CORS Settings
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()
]
SESSION_SECRET = os.getenv("SESSION_SECRET", "fg_sec_token_09871234567890abcdef")
WEBHOOK_LOCAL_HMAC_SECRET = os.getenv("WEBHOOK_LOCAL_HMAC_SECRET", "fg_local_webhook_secret_hmac_2026")

# Financial Invariant Settings
REQUIRE_DUAL_AUTHORIZATION_THRESHOLD = 500000 # in cents: $5,000.00
ALLOWED_CURRENCIES = ["USD", "EUR", "CAD"]
