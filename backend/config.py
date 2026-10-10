"""FreightGuard Configuration Module
Manages application mode, paths, and sandbox configuration.
Guarantees strict isolation of external credentials.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "freightguard.db"

# Mode configuration:
# 'LOCAL_DEMO': Deterministic local simulation of AI and PayPal sandbox (default, 100% offline)
# 'LIVE_SANDBOX': Live external PayPal Sandbox API (requires explicit user authorization)
APP_MODE = os.getenv("FREIGHTGUARD_MODE", "LOCAL_DEMO")

# PayPal Sandbox Configuration (Server-side only, never exposed to browser)
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

# AI Engine Provider Configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "LOCAL_DETERMINISTIC") # LOCAL_DETERMINISTIC | OPENAI | GEMINI

# Financial Invariant Settings
REQUIRE_DUAL_AUTHORIZATION_THRESHOLD = 500000 # in cents: $5,000.00
ALLOWED_CURRENCIES = ["USD", "EUR", "CAD"]
