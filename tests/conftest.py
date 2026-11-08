"""Global Pytest Fixtures for FreightGuard
Ensures standard unit tests run deterministically with zero credentials by default,
while allowing integration tests to supply runtime keys and test live logic.
"""
import pytest
from backend.paypal_adapter import reset_runtime_paypal_credentials
from backend.ai_service import set_runtime_keys


@pytest.fixture(autouse=True)
def clean_env_for_tests(monkeypatch):
    """Resets credentials to default clean state for deterministic unit testing."""
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    reset_runtime_paypal_credentials()
    set_runtime_keys(provider=None)
    yield
    reset_runtime_paypal_credentials()
    set_runtime_keys(provider=None)

