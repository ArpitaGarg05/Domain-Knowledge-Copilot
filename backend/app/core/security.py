import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000,
    )
    return f"pbkdf2_sha256${_b64encode(salt)}${_b64encode(password_hash)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_hash = stored_hash.split("$", 2)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    salt = _b64decode(encoded_salt)
    expected_hash = _b64decode(encoded_hash)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000,
    )
    return hmac.compare_digest(password_hash, expected_hash)


def create_access_token(subject: str) -> str:
    expires_at = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }
    header = {
        "alg": settings.jwt_algorithm,
        "typ": "JWT",
    }
    signing_input = (
        f"{_b64encode_json(header)}.{_b64encode_json(payload)}"
    )
    signature = _sign(signing_input)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
    except ValueError as error:
        raise TokenError("Invalid token format.") from error

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("Invalid token signature.")

    header = json.loads(_b64decode(encoded_header))
    if header.get("alg") != settings.jwt_algorithm:
        raise TokenError("Invalid token algorithm.")

    payload = json.loads(_b64decode(encoded_payload))
    expires_at = int(payload.get("exp", 0))
    if expires_at < int(datetime.utcnow().timestamp()):
        raise TokenError("Token has expired.")

    return payload


def _sign(signing_input: str) -> str:
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _b64encode_json(data: dict[str, Any]) -> str:
    return _b64encode(
        json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))
