import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,30}[a-z0-9])?$")
TOKEN_TYPE_ACCESS = "access"
TOKEN_ISSUER = "planix-api"


class SecurityError(ValueError):
    pass


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.fullmatch(normalized):
        raise SecurityError("Invalid email format.")
    return normalized


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not USERNAME_RE.fullmatch(normalized):
        raise SecurityError(
            "Username must be 3-32 characters and contain only lowercase letters, digits, dots, underscores, or hyphens."
        )
    return normalized


def validate_password_strength(
    password: str,
    email: str | None = None,
    username: str | None = None,
) -> None:
    if len(password) < 12:
        raise SecurityError("Password must be at least 12 characters long.")
    if len(password) > 128:
        raise SecurityError("Password must be at most 128 characters long.")
    if password.strip() != password:
        raise SecurityError("Password must not start or end with whitespace.")
    if not re.search(r"[a-z]", password):
        raise SecurityError("Password must contain a lowercase letter.")
    if not re.search(r"[A-Z]", password):
        raise SecurityError("Password must contain an uppercase letter.")
    if not re.search(r"\d", password):
        raise SecurityError("Password must contain a digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise SecurityError("Password must contain a special character.")
    local_part = (email or "").split("@", 1)[0]
    if len(local_part) >= 4 and local_part in password.lower():
        raise SecurityError("Password is too similar to the email.")
    if username and len(username) >= 4 and username in password.lower():
        raise SecurityError("Password is too similar to the username.")


def hash_password(password: str, iterations: int) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return "pbkdf2_sha256${iterations}${salt}${digest}".format(
        iterations=iterations,
        salt=_b64encode(salt),
        digest=_b64encode(digest),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iterations = int(raw_iterations)
        salt = _b64decode(raw_salt)
        expected_digest = _b64decode(raw_digest)
    except (ValueError, TypeError):
        return False

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return secrets.compare_digest(candidate_digest, expected_digest)


def create_access_token(
    *,
    user_id: str,
    username: str,
    session_id: str,
    secret_key: str,
    expires_in_minutes: int,
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_in_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "sid": session_id,
        "iss": TOKEN_ISSUER,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    header = {
        "alg": "HS256",
        "typ": "JWT",
    }
    token = _encode_token(header=header, payload=payload, secret_key=secret_key)
    return token, int((expires_at - now).total_seconds())


def decode_access_token(token: str, secret_key: str) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".", 2)
    except ValueError as exc:
        raise SecurityError("Malformed access token.") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64decode(encoded_signature)
    except (binascii.Error, ValueError) as exc:
        raise SecurityError("Invalid token signature.") from exc
    if not secrets.compare_digest(expected_signature, actual_signature):
        raise SecurityError("Invalid token signature.")

    try:
        payload = json.loads(_b64decode(encoded_payload))
    except (binascii.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SecurityError("Invalid token payload.") from exc

    token_type = payload.get("type")
    if token_type != TOKEN_TYPE_ACCESS:
        raise SecurityError("Unsupported token type.")

    if payload.get("iss") != TOKEN_ISSUER:
        raise SecurityError("Invalid token issuer.")

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise SecurityError("Token expiration is invalid.")

    if datetime.now(timezone.utc).timestamp() >= exp:
        raise SecurityError("Access token has expired.")

    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise SecurityError("Token subject is invalid.")
    if not isinstance(payload.get("sid"), str) or not payload["sid"]:
        raise SecurityError("Token session is invalid.")

    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str, secret_key: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _encode_token(*, header: dict, payload: dict, secret_key: str) -> str:
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(
        secret_key.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()
    encoded_signature = _b64encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
