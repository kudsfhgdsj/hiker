"""Password rules, following the recommendations of the German BSI
("Sichere Passwörter erstellen").

The BSI describes two ways to a strong password and a third one for accounts
with a second factor:

- long and less complex: at least 20 characters with two kinds of characters;
- short and complex: at least 8 characters with all four kinds of characters
  (upper case, lower case, digits, special characters);
- with multi-factor authentication: at least 8 characters with three kinds.

The third way only counts while the second factor is mandatory (`MFA_REQUIRED`).
On top of that a password must not contain the e-mail address or the name and
must not be one of the passwords everybody tries first.
"""

from app.core.config import get_settings
from app.core.errors import UnprocessableError

MAX_LENGTH = 128
LONG_LENGTH = 20
SHORT_LENGTH = 8

_COMMON = {
    "passwort",
    "password",
    "qwertz",
    "qwerty",
    "hallo",
    "willkommen",
    "welcome",
    "sommer",
    "winter",
    "berge",
    "wandern",
    "hiker",
    "123456",
    "abc123",
    "letmein",
    "iloveyou",
    "schatz",
    "admin",
}


def character_kinds(password: str) -> int:
    return sum(
        (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
    )


def _weak(reason: str, message: str) -> UnprocessableError:
    error = UnprocessableError(message, code="weak_password")
    error.extra = {"reason": reason}
    return error


def check_password(password: str, *, email: str = "", display_name: str = "") -> None:
    """Raise `weak_password` (with a `reason`) unless the password follows the rules."""
    if len(password) > MAX_LENGTH:
        raise _weak("too_long", f"The password must not be longer than {MAX_LENGTH} characters")
    kinds = character_kinds(password)
    kinds_for_short = 3 if get_settings().mfa_required else 4
    long_enough = len(password) >= LONG_LENGTH and kinds >= 2
    complex_enough = len(password) >= SHORT_LENGTH and kinds >= kinds_for_short
    if len(password) < SHORT_LENGTH:
        raise _weak("too_short", f"The password needs at least {SHORT_LENGTH} characters")
    if not (long_enough or complex_enough):
        raise _weak(
            "too_simple",
            f"Use {kinds_for_short} kinds of characters (upper case, lower case, digits, special "
            f"characters), or at least {LONG_LENGTH} characters with two kinds",
        )
    lowered = password.lower()
    personal = [email.split("@")[0].lower(), *display_name.lower().split()]
    if any(len(part) >= 3 and part in lowered for part in personal):
        raise _weak("contains_personal_data", "The password must not contain your name or e-mail")
    letters = "".join(c for c in lowered if c.isalpha())
    if lowered in _COMMON or letters in _COMMON or len(set(password)) < 5:
        raise _weak("too_common", "This password is too easy to guess")
