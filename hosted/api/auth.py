"""API key authentication."""

import secrets
from dataclasses import dataclass
from uuid import UUID

import bcrypt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..db import get_db

security = HTTPBearer()


@dataclass
class AuthContext:
    customer_id: UUID
    api_key_id: UUID


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, hash)."""
    random_part = secrets.token_urlsafe(32)
    full_key = f"cg_live_{random_part}"
    key_prefix = full_key[:12]
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
    return full_key, key_prefix, key_hash


def verify_api_key(full_key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(full_key.encode(), key_hash.encode())


async def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> AuthContext:
    token = credentials.credentials

    if not token.startswith("cg_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    key_prefix = token[:12]

    db = get_db()
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ak.id, ak.key_hash, ak.customer_id
            FROM api_keys ak
            WHERE ak.key_prefix = $1 AND ak.revoked_at IS NULL
            """,
            key_prefix,
        )

        if not row:
            raise HTTPException(status_code=401, detail="Invalid API key")

        if not verify_api_key(token, row["key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        await conn.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE id = $1",
            row["id"],
        )

        return AuthContext(
            customer_id=row["customer_id"],
            api_key_id=row["id"],
        )
