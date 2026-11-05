"""FreightGuard Authentication & Role-Based Access Control
Provides signed session tokens using itsdangerous, demo user profiles,
and role authorization dependencies for financial settlement endpoints.
"""
from typing import Dict, Any, Optional, List
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from backend.config import SESSION_SECRET

serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="freightguard_auth_salt")
security_bearer = HTTPBearer(auto_error=False)

DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "clerk@freightguard.internal": {
        "email": "clerk@freightguard.internal",
        "name": "Alex Mercer",
        "role": "CLERK",
        "title": "AP Accounts Payable Specialist",
        "can_approve": False,
    },
    "sarah.chen@shipper.internal": {
        "email": "sarah.chen@shipper.internal",
        "name": "Sarah Chen",
        "role": "APPROVER_1",
        "title": "Finance Operations Lead (Approver 1)",
        "can_approve": True,
    },
    "david.ross@shipper.internal": {
        "email": "david.ross@shipper.internal",
        "name": "David Ross",
        "role": "APPROVER_2",
        "title": "Corporate Controller (Approver 2)",
        "can_approve": True,
    },
}


def create_token_for_user(email: str, role: str, name: str) -> str:
    """Generates a cryptographically signed timed session token."""
    return serializer.dumps({"email": email, "role": role, "name": name})


def decode_token(token: str, max_age: int = 86400 * 7) -> Optional[Dict[str, Any]]:
    """Decodes and validates signed token. Returns None on signature failure or expiration."""
    try:
        data = serializer.loads(token, max_age=max_age)
        return data
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Dict[str, Any]:
    """Strict authentication dependency.
    Validates token from Authorization: Bearer <token> or X-Auth-Token header.
    Raises HTTP 401 if missing or invalid.
    """
    token = None
    if bearer and bearer.credentials:
        token = bearer.credentials
    if not token:
        token = request.headers.get("X-Auth-Token") or request.headers.get("x-auth-token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token in Authorization or X-Auth-Token header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_data = decode_token(token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach permission info
    email = user_data.get("email")
    if email in DEMO_USERS:
        return DEMO_USERS[email]

    user_data["can_approve"] = user_data.get("role") in ("APPROVER_1", "APPROVER_2", "ADMIN")
    return user_data


def get_optional_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Optional[Dict[str, Any]]:
    """Optional authentication dependency for endpoints that accept both anonymous and authenticated calls."""
    token = None
    if bearer and bearer.credentials:
        token = bearer.credentials
    if not token:
        token = request.headers.get("X-Auth-Token") or request.headers.get("x-auth-token")
    if not token:
        return None
    user_data = decode_token(token)
    if not user_data:
        return None

    email = user_data.get("email")
    if email in DEMO_USERS:
        return DEMO_USERS[email]

    user_data["can_approve"] = user_data.get("role") in ("APPROVER_1", "APPROVER_2", "ADMIN")
    return user_data
