"""Wallet-based ed25519 authentication endpoints and dependencies."""

from datetime import datetime, timedelta, timezone
import base64
import secrets
from typing import Annotated, Optional

import base58
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
import nacl.exceptions
import nacl.signing
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.config import settings
from backend.core.errors import AuthError
from backend.db.models import Nonce, Workspace
from backend.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class NonceRequest(BaseModel):
    wallet: str = Field(..., description="Solana wallet public key (base58)")


class NonceResponse(BaseModel):
    nonce: str
    message: str


class VerifyRequest(BaseModel):
    wallet: str = Field(..., description="Solana wallet public key (base58)")
    signature: str = Field(..., description="ed25519 signature (base58 or base64)")
    message: str = Field(..., description="Exact challenge message signed by the wallet")


class VerifyResponse(BaseModel):
    token: str
    workspace_id: str


def decode_signature(sig_str: str) -> bytes:
    """Decode a signature string from either base58 or base64."""
    sig_str = sig_str.strip()
    # Try base58 first
    try:
        raw = base58.b58decode(sig_str)
        if len(raw) == 64:
            return raw
    except Exception:
        pass

    # Try base64
    try:
        raw = base64.b64decode(sig_str)
        if len(raw) == 64:
            return raw
    except Exception:
        pass

    raise AuthError("Invalid signature format (must be 64-byte base58 or base64)")


def decode_wallet_pubkey(wallet_str: str) -> bytes:
    """Decode and validate a 32-byte Solana base58 wallet address."""
    wallet_str = wallet_str.strip()
    try:
        raw = base58.b58decode(wallet_str)
        if len(raw) == 32:
            return raw
    except Exception:
        pass
    raise AuthError("Invalid Solana wallet address (must be 32-byte base58)")


@router.post("/nonce", response_model=NonceResponse)
def create_nonce(
    req: NonceRequest,
    session: Annotated[Session, Depends(get_session)],
) -> NonceResponse:
    """Generate a single-use 5-minute challenge nonce for wallet authentication."""
    decode_wallet_pubkey(req.wallet)

    nonce_val = secrets.token_hex(16)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=5)

    challenge_message = (
        f"Analyx sign-in\n"
        f"Wallet: {req.wallet}\n"
        f"Nonce: {nonce_val}\n"
        f"Issued: {issued_at.isoformat()}"
    )

    nonce_record = Nonce(
        wallet_address=req.wallet,
        nonce=nonce_val,
        issued_at=issued_at,
        expires_at=expires_at,
        used=False,
    )
    session.add(nonce_record)
    session.commit()

    return NonceResponse(nonce=nonce_val, message=challenge_message)


@router.post("/verify", response_model=VerifyResponse)
def verify_signature(
    req: VerifyRequest,
    session: Annotated[Session, Depends(get_session)],
) -> VerifyResponse:
    """Verify wallet ed25519 signature over challenge message and issue JWT."""
    pubkey_bytes = decode_wallet_pubkey(req.wallet)
    sig_bytes = decode_signature(req.signature)

    # 1. Verify ed25519 signature over the exact message bytes
    try:
        verify_key = nacl.signing.VerifyKey(pubkey_bytes)
        verify_key.verify(req.message.encode("utf-8"), sig_bytes)
    except (nacl.exceptions.BadSignatureError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Invalid wallet signature",
                    "details": {"error": str(exc)},
                }
            },
        ) from exc

    # 2. Extract nonce from challenge message and verify single-use validity
    now = datetime.now(timezone.utc)
    # Parse Nonce: <val> from message
    lines = [line.strip() for line in req.message.split("\n")]
    nonce_val: Optional[str] = None
    for line in lines:
        if line.startswith("Nonce:"):
            nonce_val = line.split(":", 1)[1].strip()
            break

    if not nonce_val:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Challenge message missing nonce field",
                }
            },
        )

    statement = select(Nonce).where(
        Nonce.wallet_address == req.wallet,
        Nonce.nonce == nonce_val,
        Nonce.used == False,  # noqa: E712
    )
    nonce_record = session.exec(statement).first()

    if not nonce_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Nonce not found or already used",
                }
            },
        )

    # Convert stored naive UTC or timezone-aware expires_at
    expires_at = nonce_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Nonce expired",
                }
            },
        )

    # Mark nonce as used
    nonce_record.used = True
    session.add(nonce_record)

    # 3. Get or create Workspace for this wallet
    wk_stmt = select(Workspace).where(Workspace.wallet_address == req.wallet)
    workspace = session.exec(wk_stmt).first()
    if not workspace:
        workspace = Workspace(
            wallet_address=req.wallet,
            name=f"Workspace ({req.wallet[:4]}...{req.wallet[-4:]})",
        )
        session.add(workspace)

    session.commit()
    session.refresh(workspace)

    # 4. Issue JWT
    token_exp = now + timedelta(days=7)
    jwt_payload = {
        "sub": req.wallet,
        "workspace_id": workspace.id,
        "iat": int(now.timestamp()),
        "exp": int(token_exp.timestamp()),
    }
    token = jwt.encode(jwt_payload, settings.jwt_secret, algorithm="HS256")

    return VerifyResponse(token=token, workspace_id=workspace.id)


def get_current_workspace(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Annotated[Session, Depends(get_session)],
) -> Workspace:
    """Dependency: decode JWT and return current authenticated Workspace."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Bearer authentication required",
                }
            },
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Token expired",
                }
            },
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Invalid token",
                }
            },
        )

    workspace_id = payload.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Invalid token payload (missing workspace_id)",
                }
            },
        )

    workspace = session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_ERROR",
                    "message": "Workspace not found",
                }
            },
        )

    return workspace
