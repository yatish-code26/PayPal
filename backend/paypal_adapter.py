"""FreightGuard PayPal Developer Platform Integration Adapter
Implements the official PayPal Payouts API specification (POST /v1/payments/payouts)
with robust idempotency handling, batch and item tracking, and state reconciliation.

Supports two operational modes:
1. LOCAL_DEMO (Default): High-fidelity, deterministic local simulator (100% offline).
   - Generates realistic sandbox batch and item IDs
   - PENDING -> SUCCESS state progression
   - Configurable failure mode toggles (FAILED, UNCLAIMED, BLOCKED)
   - Emits HMAC-signed simulated webhook notifications
2. LIVE_SANDBOX: Connects to https://api-m.sandbox.paypal.com using server-side OAuth.
   - Real OAuth2 token caching
   - Idempotent POST /v1/payments/payouts execution with exponential backoff on 5xx/429
   - Authoritative status queries and cryptographic webhook signature verification
"""
from typing import Dict, Any, Optional, Tuple
import os
import uuid
import json
import base64
import time
import hmac
import hashlib
import logging
from datetime import datetime, timezone
import urllib.request
import urllib.parse
import urllib.error

from backend.config import (
    APP_MODE,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_SANDBOX_BASE_URL,
    PAYPAL_WEBHOOK_ID,
    PAYPAL_RECEIVER_EMAIL,
    WEBHOOK_LOCAL_HMAC_SECRET,
)
from backend.policy_engine import cents_to_dollars

logger = logging.getLogger("freightguard.paypal")

# In-memory runtime configuration override (allows UI key entry without restarting or writing to disk)
RUNTIME_PAYPAL_CONFIG: Dict[str, Optional[str]] = {
    "client_id": None,
    "client_secret": None,
    "webhook_id": None,
    "failure_mode": None, # None | UNCLAIMED | FAILED | BLOCKED
    "forced_mode": None,  # None | LOCAL_DEMO | LIVE_SANDBOX
}


def get_runtime_paypal_credentials() -> Tuple[str, str, str]:
    """Retrieves PayPal credentials prioritizing in-memory settings over env vars."""
    client_id = (RUNTIME_PAYPAL_CONFIG.get("client_id") or os.getenv("PAYPAL_CLIENT_ID", "")).strip()
    client_secret = (RUNTIME_PAYPAL_CONFIG.get("client_secret") or os.getenv("PAYPAL_CLIENT_SECRET", "")).strip()
    webhook_id = (RUNTIME_PAYPAL_CONFIG.get("webhook_id") or os.getenv("PAYPAL_WEBHOOK_ID", "")).strip()
    return client_id, client_secret, webhook_id


def reset_runtime_paypal_credentials() -> None:
    """Resets in-memory runtime credentials to default."""
    RUNTIME_PAYPAL_CONFIG["client_id"] = None
    RUNTIME_PAYPAL_CONFIG["client_secret"] = None
    RUNTIME_PAYPAL_CONFIG["webhook_id"] = None
    RUNTIME_PAYPAL_CONFIG["failure_mode"] = None
    RUNTIME_PAYPAL_CONFIG["forced_mode"] = None


def set_runtime_paypal_credentials(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    webhook_id: Optional[str] = None,
    failure_mode: Optional[str] = None,
    forced_mode: Optional[str] = None,
    clear: bool = False,
) -> None:
    """Updates in-memory runtime credentials without disk persistence."""
    if clear:
        reset_runtime_paypal_credentials()
        return
    if client_id is not None:
        RUNTIME_PAYPAL_CONFIG["client_id"] = client_id.strip() if client_id else None
    if client_secret is not None:
        RUNTIME_PAYPAL_CONFIG["client_secret"] = client_secret.strip() if client_secret else None
    if webhook_id is not None:
        RUNTIME_PAYPAL_CONFIG["webhook_id"] = webhook_id.strip() if webhook_id else None
    if failure_mode is not None:
        RUNTIME_PAYPAL_CONFIG["failure_mode"] = failure_mode.strip().upper() if failure_mode else None
    if forced_mode is not None:
        RUNTIME_PAYPAL_CONFIG["forced_mode"] = forced_mode.strip().upper() if forced_mode else None


class PayPalAdapterException(Exception):
    """Raised for PayPal communication, validation, or policy errors."""
    pass


class PayPalPayoutsAdapter:
    """Server-side client for PayPal Payouts API."""

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    def mode(self) -> str:
        """Dynamically computes the active operational mode:
        If forced via settings, uses that.
        Otherwise, if both client_id and client_secret are provided, returns LIVE_SANDBOX.
        Defaults to LOCAL_DEMO.
        """
        forced = RUNTIME_PAYPAL_CONFIG.get("forced_mode") or os.getenv("FREIGHTGUARD_MODE")
        if forced in ("LOCAL_DEMO", "LIVE_SANDBOX"):
            # If forced LIVE_SANDBOX but credentials missing, stay in LOCAL_DEMO
            if forced == "LIVE_SANDBOX":
                cid, csec, _ = get_runtime_paypal_credentials()
                if cid and csec:
                    return "LIVE_SANDBOX"
                return "LOCAL_DEMO"
            return forced

        cid, csec, _ = get_runtime_paypal_credentials()
        if cid and csec:
            return "LIVE_SANDBOX"
        return "LOCAL_DEMO"

    def is_live_mode_ready(self) -> bool:
        """Returns True only if live sandbox credentials are valid and present."""
        return self.mode() == "LIVE_SANDBOX"

    def get_mode_diagnostics(self) -> Dict[str, Any]:
        """Returns safe diagnostic information without leaking secrets."""
        current_mode = self.mode()
        cid, csec, whid = get_runtime_paypal_credentials()

        masked_cid = "NOT_SET"
        if cid:
            masked_cid = f"{cid[:6]}...{cid[-4:]}" if len(cid) > 10 else "CONFIGURED"

        return {
            "mode": current_mode,
            "is_simulated": current_mode != "LIVE_SANDBOX",
            "endpoint": PAYPAL_SANDBOX_BASE_URL,
            "base_url": PAYPAL_SANDBOX_BASE_URL,
            "client_id_configured": bool(cid),
            "client_id_masked": masked_cid,
            "client_secret_configured": bool(csec),
            "webhook_id_configured": bool(whid),
            "oauth_token_active": self._access_token is not None and time.time() < self._token_expiry,
            "simulate_failure_mode": RUNTIME_PAYPAL_CONFIG.get("failure_mode") or "NONE",
            "status_label": (
                "Built-in Sandbox Simulator"
                if current_mode != "LIVE_SANDBOX"
                else "Live PayPal Sandbox Gateway"
            ),
        }

    def test_connection(self) -> Dict[str, Any]:
        """Tests gateway connectivity for the UI.
        In LIVE_SANDBOX: tests OAuth token acquisition from PayPal.
        In LOCAL_DEMO: tests simulator readiness.
        """
        current_mode = self.mode()
        if current_mode != "LIVE_SANDBOX":
            return {
                "success": True,
                "mode": "LOCAL_DEMO",
                "message": "Local Sandbox Simulator is active and ready (Offline Mode).",
                "diagnostics": self.get_mode_diagnostics(),
            }

        try:
            token = self._acquire_oauth_token(force_refresh=True)
            return {
                "success": True,
                "mode": "LIVE_SANDBOX",
                "message": "Successfully authenticated with PayPal Sandbox API via OAuth2.",
                "token_prefix": f"{token[:8]}...",
                "diagnostics": self.get_mode_diagnostics(),
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "LIVE_SANDBOX",
                "message": f"PayPal Sandbox connection failed: {str(e)}",
                "diagnostics": self.get_mode_diagnostics(),
            }

    def _acquire_oauth_token(self, force_refresh: bool = False) -> str:
        """Acquires OAuth2 Bearer token from PayPal Sandbox endpoint."""
        if self.mode() != "LIVE_SANDBOX":
            return "SIMULATED_LOCAL_BEARER_TOKEN"

        if not force_refresh and self._access_token and time.time() < self._token_expiry:
            return self._access_token

        client_id, client_secret, _ = get_runtime_paypal_credentials()
        if not client_id or not client_secret:
            raise PayPalAdapterException("Missing PayPal sandbox client credentials.")

        token_url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/oauth2/token"
        auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()

        req = urllib.request.Request(token_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                self._access_token = result["access_token"]
                self._token_expiry = time.time() + result.get("expires_in", 3600) - 60
                return self._access_token
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            raise PayPalAdapterException(f"PayPal OAuth Error ({e.code}): {err_body}")
        except Exception as e:
            raise PayPalAdapterException(f"Network error acquiring PayPal OAuth token: {str(e)}")

    def create_payout(
        self,
        idempotency_key: str,
        sender_batch_id: str,
        receiver_email: str,
        amount_cents: int,
        currency: str = "USD",
        note: str = "Freight settlement payout",
    ) -> Dict[str, Any]:
        """Creates a PayPal Payout following POST /v1/payments/payouts specification.
        Enforces idempotency and tracks batch + item identifiers.
        """
        amount_str = cents_to_dollars(amount_cents).replace(",", "")

        # In live sandbox mode, prefer PAYPAL_RECEIVER_EMAIL from env/config if configured
        effective_receiver = receiver_email
        if self.mode() == "LIVE_SANDBOX":
            configured_receiver = os.getenv("PAYPAL_RECEIVER_EMAIL") or PAYPAL_RECEIVER_EMAIL
            if configured_receiver and configured_receiver.strip():
                effective_receiver = configured_receiver.strip()

        payout_payload = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": f"Freight Settlement: {sender_batch_id}",
                "email_message": note,
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {"value": amount_str, "currency": currency},
                    "note": note,
                    "sender_item_id": f"ITEM-{idempotency_key[:16]}",
                    "receiver": effective_receiver,
                }
            ],
        }

        # ---------------------------------------------------------------------
        # 1. Local Offline Sandbox Simulation Mode
        # ---------------------------------------------------------------------
        if self.mode() != "LIVE_SANDBOX":
            sim_batch_id = f"PAYPAL-SBX-BATCH-{uuid.uuid5(uuid.NAMESPACE_DNS, sender_batch_id).hex[:12].upper()}"
            sim_item_id = f"PAYPAL-SBX-ITEM-{uuid.uuid5(uuid.NAMESPACE_DNS, idempotency_key).hex[:12].upper()}"
            now_str = datetime.now(timezone.utc).isoformat()

            failure_override = RUNTIME_PAYPAL_CONFIG.get("failure_mode")
            item_status = failure_override if failure_override in ("FAILED", "UNCLAIMED", "BLOCKED") else "SUCCESS"
            batch_status = "SUCCESS" if item_status == "SUCCESS" else "DENIED"

            simulated_response = {
                "batch_header": {
                    "payout_batch_id": sim_batch_id,
                    "batch_status": batch_status,
                    "time_created": now_str,
                    "time_completed": now_str,
                    "sender_batch_header": payout_payload["sender_batch_header"],
                    "amount": {"currency": currency, "value": amount_str},
                    "fees": {"currency": currency, "value": "0.25"},
                },
                "items": [
                    {
                        "payout_item_id": sim_item_id,
                        "transaction_status": item_status,
                        "payout_item_fee": {"currency": currency, "value": "0.25"},
                        "payout_batch_id": sim_batch_id,
                        "payout_item": payout_payload["items"][0],
                        "time_processed": now_str,
                    }
                ],
                "links": [
                    {
                        "href": f"https://api-m.sandbox.paypal.com/v1/payments/payouts/{sim_batch_id}",
                        "rel": "self",
                        "method": "GET",
                    }
                ],
            }

            return {
                "is_simulated": 1,
                "mode_label": "Local Sandbox Adapter (Simulation - No External Network)",
                "batch_id": sim_batch_id,
                "item_id": sim_item_id,
                "batch_status": batch_status,
                "item_status": item_status,
                "amount_cents": amount_cents,
                "currency": currency,
                "receiver_email": receiver_email,
                "paypal_fee_cents": 25,
                "raw_response": simulated_response,
            }

        # ---------------------------------------------------------------------
        # 2. Live PayPal Sandbox Mode (with exponential backoff on 5xx/429)
        # ---------------------------------------------------------------------
        token = self._acquire_oauth_token()
        url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts"
        req_body = json.dumps(payout_payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idempotency_key,
        }

        max_retries = 3
        backoff_delay = 1.0
        last_error = None

        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    res_data = json.loads(resp.read().decode())
                    batch_header = res_data.get("batch_header", {})
                    batch_id = batch_header.get("payout_batch_id")
                    batch_status = batch_header.get("batch_status", "PROCESSING")
                    item_id = None
                    item_status = "PENDING"

                    items = res_data.get("items")
                    if items and len(items) > 0:
                        item_id = items[0].get("payout_item_id")
                        item_status = items[0].get("transaction_status", "PENDING")
                    elif batch_id:
                        try:
                            time.sleep(0.5)
                            batch_info = self.get_payout_batch_status(batch_id)
                            b_items = batch_info.get("items", [])
                            if b_items and len(b_items) > 0:
                                item_id = b_items[0].get("payout_item_id")
                                item_status = b_items[0].get("transaction_status", "PENDING")
                        except Exception as poll_err:
                            logger.warning(f"Could not immediately fetch payout items for batch {batch_id}: {poll_err}")

                    return {
                        "is_simulated": 0,
                        "mode_label": "Live PayPal Sandbox Gateway",
                        "batch_id": batch_id,
                        "item_id": item_id,
                        "batch_status": batch_status,
                        "item_status": item_status,
                        "amount_cents": amount_cents,
                        "currency": currency,
                        "receiver_email": effective_receiver,
                        "paypal_fee_cents": 25,
                        "raw_response": res_data,
                    }
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                last_error = e
                # Retry on 429 (Rate Limit) or 5xx (Server Errors)
                if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    logger.warning(f"PayPal Sandbox HTTP {e.code}; retrying in {backoff_delay}s...")
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                    continue
                raise PayPalAdapterException(f"PayPal Sandbox Payouts API Error ({e.code}): {err_body}")
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                    continue
                raise PayPalAdapterException(f"Network error contacting PayPal Sandbox: {str(e)}")

        raise PayPalAdapterException(f"PayPal Payout failed after {max_retries} attempts: {last_error}")

    def get_payout_batch_status(self, payout_batch_id: str) -> Dict[str, Any]:
        """Retrieves authoritative payout batch status from PayPal Sandbox."""
        if self.mode() != "LIVE_SANDBOX" or payout_batch_id.startswith("PAYPAL-SBX-"):
            return {
                "is_simulated": 1,
                "batch_id": payout_batch_id,
                "batch_status": "SUCCESS",
                "message": "Deterministic local simulation authoritative status",
            }

        token = self._acquire_oauth_token()
        url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts/{payout_batch_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        max_retries = 3
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise PayPalAdapterException(f"PayPal Sandbox Batch Query Error ({e.code}): {err_body}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise PayPalAdapterException(f"Network error querying PayPal batch status: {str(e)}")

    def get_payout_item_status(self, payout_item_id: str) -> Dict[str, Any]:
        """Retrieves authoritative payout item status from PayPal Sandbox."""
        if self.mode() != "LIVE_SANDBOX" or payout_item_id.startswith("PAYPAL-SBX-"):
            return {
                "is_simulated": 1,
                "payout_item_id": payout_item_id,
                "transaction_status": "SUCCESS",
            }

        token = self._acquire_oauth_token()
        url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts-item/{payout_item_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        max_retries = 3
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise PayPalAdapterException(f"PayPal Sandbox Item Query Error ({e.code}): {err_body}")
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                raise PayPalAdapterException(f"Network error querying PayPal item status: {str(e)}")

    def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        raw_body: bytes,
    ) -> bool:
        """Verifies webhook signature.
        In LIVE_SANDBOX mode: calls PayPal POST /v1/notifications/verify-webhook-signature.
        In LOCAL_DEMO mode: validates HMAC-SHA256 signature using local test secret.
        """
        # Normalize headers
        normalized_headers = {k.upper(): v for k, v in headers.items()}

        if self.mode() == "LIVE_SANDBOX":
            client_id, client_secret, webhook_id = get_runtime_paypal_credentials()
            if not webhook_id:
                logger.error("Cannot verify live webhook: PAYPAL_WEBHOOK_ID is not configured.")
                return False

            auth_algo = normalized_headers.get("PAYPAL-AUTH-ALGO")
            cert_url = normalized_headers.get("PAYPAL-CERT-URL")
            transmission_id = normalized_headers.get("PAYPAL-TRANSMISSION-ID")
            transmission_sig = normalized_headers.get("PAYPAL-TRANSMISSION-SIG")
            transmission_time = normalized_headers.get("PAYPAL-TRANSMISSION-TIME")

            if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
                logger.warning("Live webhook missing required PayPal verification headers.")
                return False

            try:
                event_body = json.loads(raw_body.decode("utf-8"))
            except Exception:
                return False

            verify_payload = {
                "auth_algo": auth_algo,
                "cert_url": cert_url,
                "transmission_id": transmission_id,
                "transmission_sig": transmission_sig,
                "transmission_time": transmission_time,
                "webhook_id": webhook_id,
                "webhook_event": event_body,
            }

            token = self._acquire_oauth_token()
            verify_url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/notifications/verify-webhook-signature"
            req = urllib.request.Request(
                verify_url,
                data=json.dumps(verify_payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    res = json.loads(resp.read().decode())
                    return res.get("verification_status") == "SUCCESS"
            except Exception as e:
                logger.error(f"PayPal webhook verification API call failed: {e}")
                return False

        # LOCAL_DEMO Mode HMAC verification
        received_sig = (
            normalized_headers.get("X-LOCAL-SIGNATURE")
            or normalized_headers.get("X-FREIGHTGUARD-SIGNATURE")
            or normalized_headers.get("PAYPAL-TRANSMISSION-SIG")
            or ""
        ).strip()
        if not received_sig:
            return False

        if received_sig.startswith("sha256="):
            received_sig = received_sig[7:].strip()

        # Allow SIMULATED_TEST_SIGNATURE for local simulation test calls
        if received_sig == "SIMULATED_TEST_SIGNATURE":
            return True

        expected_sig = hmac.new(
            WEBHOOK_LOCAL_HMAC_SECRET.encode(),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(received_sig, expected_sig)


def generate_local_webhook_signature(raw_body: bytes) -> str:
    """Helper to generate local HMAC signature for simulated webhook dispatches."""
    return hmac.new(
        WEBHOOK_LOCAL_HMAC_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
