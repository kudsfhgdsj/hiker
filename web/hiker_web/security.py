"""Login check, CSRF protection and keeping secrets out of the log."""

import functools
import hmac
import logging
import re
import secrets

from flask import abort, redirect, request, session, url_for

from hiker_web.api import api

_TOKEN_PATH = re.compile(r"(/p/)[^/?\s\"]+")


def csrf_token() -> str:
    """One token per browser session; every form sends it back."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf() -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not hmac.compare_digest(sent, session.get("csrf", "")) or not sent:
        abort(400, "csrf")


def signed_in(view):
    """For the pages that finish a sign-in: a session is enough."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if api().data is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def pending_step(data: dict) -> str | None:
    """The page a session has to visit before it can be used, if any."""
    if data.get("password_change_required"):
        return "auth.password"
    if data.get("mfa_setup_required"):
        return "auth.mfa_setup"
    return None


def login_required(view):
    @functools.wraps(view)
    @signed_in
    def wrapped(*args, **kwargs):
        step = pending_step(api().data)
        if step:
            return redirect(url_for(step))
        return view(*args, **kwargs)

    return wrapped


def module_required(name: str):
    """The pages of a module exist only if the server has it enabled."""

    def decorator(view):
        @functools.wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if name not in (api().data or {}).get("modules", []):
                abort(404)
            return view(*args, **kwargs)

        return wrapped

    return decorator


class TokenRedactionFilter(logging.Filter):
    """Tokens of public links are secrets: `/p/<token>` never reaches the log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _TOKEN_PATH.sub(r"\1[redacted]", record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(
                _TOKEN_PATH.sub(r"\1[redacted]", a) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def install_log_redaction() -> None:
    for name in ("werkzeug", "gunicorn.access", "gunicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, TokenRedactionFilter) for f in logger.filters):
            logger.addFilter(TokenRedactionFilter())
