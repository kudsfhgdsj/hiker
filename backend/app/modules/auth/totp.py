"""Time-based one-time passwords (RFC 6238), as shown by authenticator apps.

Six digits, 30 seconds, HMAC-SHA1: the variant every authenticator app supports.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

PERIOD_SECONDS = 30
DIGITS = 6
# Accept the code of the previous and the next period: clocks are never exact.
WINDOW = 1


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(secret: str, counter: int) -> str:
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def current_counter(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // PERIOD_SECONDS)


def verify(
    secret: str, code: str, last_counter: int | None, now: float | None = None
) -> int | None:
    """The counter the code belongs to, or None if it is wrong or was used before."""
    code = "".join(code.split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    counter = current_counter(now)
    for candidate in range(counter - WINDOW, counter + WINDOW + 1):
        if last_counter is not None and candidate <= last_counter:
            continue
        if hmac.compare_digest(code_at(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    """The `otpauth://` address an authenticator app reads from a QR code."""
    label = quote(f"{issuer}:{account}")
    query = urlencode(
        {"secret": secret, "issuer": issuer, "digits": DIGITS, "period": PERIOD_SECONDS}
    )
    return f"otpauth://totp/{label}?{query}"
