"""FreightGuard PayPal Developer Platform Integration Adapter
Implements the official PayPal Payouts API specification (POST /v1/payments/payouts)
with robust idempotency handling, batch and item tracking, and state reconciliation.

Supports two operational modes:
1. LOCAL_DEMO (Default): High-fidelity, deterministic local simulator (100% offline).
   Clearly labeled as simulated.
2. LIVE_SANDBOX: Connects to https://api-m.sandbox.paypal.com using server-side OAuth.
   Activated ONLY when authorized by the user.
"""
from typing import Dict, Any, Optional
import uuid
import json
import base64
import time
from datetime import datetime, timezone
import decimal
from backend.config import (
    APP_MODE,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_SANDBOX_BASE_URL
)
from backend.policy_engine import cents_to_dollars

class PayPalAdapterException(Exception):
    """Raised for PayPal communication, validation, or policy errors."""
    pass

class PayPalPayoutsAdapter:
    """Server-side client for PayPal Payouts API."""

    def __init__(self, mode: str = APP_MODE):
        self.mode = mode
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    def is_live_mode_ready(self) -> bool:
        """Returns True only if live mode is selected and credentials exist."""
        return (
            self.mode == "LIVE_SANDBOX" 
            and bool(PAYPAL_CLIENT_ID) 
            and bool(PAYPAL_CLIENT_SECRET)
        )

    def get_mode_diagnostics(self) -> Dict[str, Any]:
        """Returns safe, unredacted diagnostic state without leaking secrets."""
        return {
            "mode": self.mode,
            "is_simulated": self.mode != "LIVE_SANDBOX",
            "endpoint": PAYPAL_SANDBOX_BASE_URL if self.mode == "LIVE_SANDBOX" else "LOCAL_OFFLINE_SIMULATOR",
            "client_id_configured": bool(PAYPAL_CLIENT_ID),
            "client_id_masked": f"{PAYPAL_CLIENT_ID[:6]}...{PAYPAL_CLIENT_ID[-4:]}" if len(PAYPAL_CLIENT_ID) > 10 else ("NOT_SET" if not PAYPAL_CLIENT_ID else "MASKED"),
            "client_secret_configured": bool(PAYPAL_CLIENT_SECRET),
            "oauth_token_active": self._access_token is not None and time.time() < self._token_expiry,
            "status_label": "Local Sandbox Simulator (Offline Demo Mode)" if self.mode != "LIVE_SANDBOX" else "Live PayPal Sandbox Gateway"
        }

    def _acquire_oauth_token(self) -> str:
        """Acquires OAuth2 Bearer token from PayPal Sandbox endpoint.
        NOTE: Never executed in LOCAL_DEMO mode.
        """
        if self.mode != "LIVE_SANDBOX":
            return "SIMULATED_LOCAL_BEARER_TOKEN"

        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
            raise PayPalAdapterException("Missing PayPal sandbox client credentials in environment.")

        import urllib.request
        import urllib.parse
        
        token_url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/oauth2/token"
        auth_header = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        
        req = urllib.request.Request(token_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                self._access_token = result["access_token"]
                self._token_expiry = time.time() + result.get("expires_in", 3600) - 60
                return self._access_token
        except Exception as e:
            raise PayPalAdapterException(f"Failed to acquire PayPal OAuth token: {str(e)}")

    def create_payout(
        self,
        idempotency_key: str,
        sender_batch_id: str,
        receiver_email: str,
        amount_cents: int,
        currency: str = "USD",
        note: str = "Freight settlement payout"
    ) -> Dict[str, Any]:
        """Creates a PayPal Payout following POST /v1/payments/payouts specification.
        Enforces idempotency and tracks batch + item identifiers.
        """
        amount_str = cents_to_dollars(amount_cents).replace(",", "")
        
        payout_payload = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": f"Freight Settlement: {sender_batch_id}",
                "email_message": note
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {
                        "value": amount_str,
                        "currency": currency
                    },
                    "note": note,
                    "sender_item_id": f"ITEM-{idempotency_key[:16]}",
                    "receiver": receiver_email
                }
            ]
        }

        # 1. Local Offline Sandbox Simulation Mode
        if self.mode != "LIVE_SANDBOX":
            # Generate deterministic simulation response resembling PayPal response
            sim_batch_id = f"PAYPAL-SBX-BATCH-{uuid.uuid5(uuid.NAMESPACE_DNS, sender_batch_id).hex[:12].upper()}"
            sim_item_id = f"PAYPAL-SBX-ITEM-{uuid.uuid5(uuid.NAMESPACE_DNS, idempotency_key).hex[:12].upper()}"
            now_str = datetime.now(timezone.utc).isoformat()
            
            simulated_response = {
                "batch_header": {
                    "payout_batch_id": sim_batch_id,
                    "batch_status": "SUCCESS",
                    "time_created": now_str,
                    "time_completed": now_str,
                    "sender_batch_header": payout_payload["sender_batch_header"],
                    "amount": {
                        "currency": currency,
                        "value": amount_str
                    },
                    "fees": {
                        "currency": currency,
                        "value": "0.25"
                    }
                },
                "items": [
                    {
                        "payout_item_id": sim_item_id,
                        "transaction_status": "SUCCESS",
                        "payout_item_fee": {
                            "currency": currency,
                            "value": "0.25"
                        },
                        "payout_batch_id": sim_batch_id,
                        "payout_item": payout_payload["items"][0],
                        "time_processed": now_str
                    }
                ],
                "links": [
                    {
                        "href": f"https://api-m.sandbox.paypal.com/v1/payments/payouts/{sim_batch_id}",
                        "rel": "self",
                        "method": "GET"
                    }
                ]
            }

            return {
                "is_simulated": 1,
                "mode_label": "Local Sandbox Adapter (Simulation - No External Network)",
                "batch_id": sim_batch_id,
                "item_id": sim_item_id,
                "batch_status": "SUCCESS",
                "item_status": "SUCCESS",
                "amount_cents": amount_cents,
                "currency": currency,
                "receiver_email": receiver_email,
                "paypal_fee_cents": 25,
                "raw_response": simulated_response
            }

        # 2. Live PayPal Sandbox Mode (Only if explicitly enabled with credentials)
        token = self._acquire_oauth_token()
        import urllib.request
        
        url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts"
        req_body = json.dumps(payout_payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idempotency_key
        }

        req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res_data = json.loads(resp.read().decode())
                batch_header = res_data.get("batch_header", {})
                batch_id = batch_header.get("payout_batch_id")
                batch_status = batch_header.get("batch_status", "PROCESSING")
                
                return {
                    "is_simulated": 0,
                    "mode_label": "Live PayPal Sandbox Gateway",
                    "batch_id": batch_id,
                    "item_id": None, # Async retrieved in status endpoint
                    "batch_status": batch_status,
                    "item_status": "PENDING",
                    "amount_cents": amount_cents,
                    "currency": currency,
                    "receiver_email": receiver_email,
                    "paypal_fee_cents": 25,
                    "raw_response": res_data
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            raise PayPalAdapterException(f"PayPal Sandbox Payouts API Error ({e.code}): {err_body}")
        except Exception as e:
            raise PayPalAdapterException(f"Network error contacting PayPal Sandbox: {str(e)}")

    def get_payout_batch_status(self, payout_batch_id: str) -> Dict[str, Any]:
        """Retrieves authoritative payout batch status from PayPal."""
        if self.mode != "LIVE_SANDBOX" or payout_batch_id.startswith("PAYPAL-SBX-"):
            return {
                "is_simulated": 1,
                "batch_id": payout_batch_id,
                "batch_status": "SUCCESS",
                "message": "Deterministic local simulation authoritative status"
            }

        token = self._acquire_oauth_token()
        import urllib.request
        url = f"{PAYPAL_SANDBOX_BASE_URL}/v1/payments/payouts/{payout_batch_id}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
