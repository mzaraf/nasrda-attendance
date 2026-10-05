"""Small standards-compatible TOTP helper for authenticator apps (RFC 6238)."""
import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote


ISSUER = "NASRDA Staff Attendance"


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def provisioning_uri(secret, account):
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits=6&period=30"


def _code(secret, counter):
    padded = secret.upper() + "=" * (-len(secret) % 8)
    digest = hmac.new(base64.b32decode(padded), counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = int.from_bytes(digest[offset:offset + 4], "big") & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def verify(secret, code, now=None):
    if not secret or not str(code).isdigit() or len(str(code)) != 6:
        return False
    counter = int((now or time.time()) // 30)
    return any(hmac.compare_digest(_code(secret, counter + drift), str(code)) for drift in (-1, 0, 1))
