"""Sign-in through an OpenID Connect provider (authorization code flow with PKCE).

The provider is reached through an adapter. The ID token is received directly
from the token endpoint over TLS; as the specification allows in that case, the
TLS connection stands in for checking the signature of the token. Issuer,
audience, expiry and nonce are checked.
"""

import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol
from urllib.parse import urlencode

import httpx2
from fastapi import Depends

from app import __version__
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class OidcError(Exception):
    """The provider could not be reached or its answer cannot be trusted."""


@dataclass(frozen=True)
class OidcIdentity:
    issuer: str
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


class OidcProvider(Protocol):
    def authorization_url(
        self, *, state: str, nonce: str, challenge: str, redirect_uri: str
    ) -> str: ...

    def exchange(
        self, *, code: str, verifier: str, nonce: str, redirect_uri: str
    ) -> OidcIdentity: ...


def new_verifier() -> str:
    return secrets.token_urlsafe(48)


def challenge_of(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise OidcError("unreadable ID token") from exc


class HttpOidcProvider:
    def __init__(
        self,
        issuer: str,
        client_id: str,
        client_secret: str,
        scopes: str,
        *,
        timeout: float = 10.0,
        transport: httpx2.BaseTransport | None = None,
    ):
        self._issuer = issuer.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._scopes = scopes
        self._client = httpx2.Client(
            headers={"User-Agent": f"hiker/{__version__}"}, timeout=timeout, transport=transport
        )
        self._metadata: dict | None = None

    def _discover(self) -> dict:
        if self._metadata is None:
            try:
                response = self._client.get(f"{self._issuer}/.well-known/openid-configuration")
                response.raise_for_status()
                metadata = response.json()
            except (httpx2.HTTPError, ValueError) as exc:
                raise OidcError(f"discovery failed: {exc}") from exc
            if str(metadata.get("issuer", "")).rstrip("/") != self._issuer:
                raise OidcError("the provider reports another issuer")
            for endpoint in ("authorization_endpoint", "token_endpoint"):
                if not str(metadata.get(endpoint, "")).startswith(("https://", "http://")):
                    raise OidcError(f"the provider has no {endpoint}")
            self._metadata = metadata
        return self._metadata

    def authorization_url(
        self, *, state: str, nonce: str, challenge: str, redirect_uri: str
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "scope": self._scopes,
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self._discover()['authorization_endpoint']}?{query}"

    def exchange(self, *, code: str, verifier: str, nonce: str, redirect_uri: str) -> OidcIdentity:
        metadata = self._discover()
        try:
            response = self._client.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": verifier,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            tokens = response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            raise OidcError(f"token request failed: {exc}") from exc
        claims = _claims(str(tokens.get("id_token", "")))
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if str(claims.get("iss", "")).rstrip("/") != self._issuer:
            raise OidcError("ID token from another issuer")
        if self._client_id not in audiences:
            raise OidcError("ID token for another client")
        if not isinstance(claims.get("exp"), int | float) or claims["exp"] < time.time():
            raise OidcError("ID token expired")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OidcError("ID token does not belong to this sign-in")
        if not claims.get("sub"):
            raise OidcError("ID token without subject")
        if claims.get("email") is None and metadata.get("userinfo_endpoint"):
            claims = {**self._userinfo(metadata["userinfo_endpoint"], tokens), **claims}
        return OidcIdentity(
            issuer=self._issuer,
            subject=str(claims["sub"]),
            email=str(claims["email"]).strip().lower() if claims.get("email") else None,
            email_verified=claims.get("email_verified") is True,
            name=claims.get("name") or claims.get("preferred_username"),
        )

    def _userinfo(self, endpoint: str, tokens: dict) -> dict:
        try:
            response = self._client.get(
                endpoint, headers={"Authorization": f"Bearer {tokens.get('access_token', '')}"}
            )
            response.raise_for_status()
            return response.json()
        except (httpx2.HTTPError, ValueError) as exc:
            logger.warning("OIDC userinfo request failed: %s", exc)
            return {}


@lru_cache
def _provider(issuer: str, client_id: str, client_secret: str, scopes: str) -> HttpOidcProvider:
    return HttpOidcProvider(issuer, client_id, client_secret, scopes)


def get_oidc_provider() -> OidcProvider | None:
    """The configured provider, or None if single sign-on is switched off."""
    settings = get_settings()
    if not (settings.oidc_issuer and settings.oidc_client_id):
        return None
    return _provider(
        settings.oidc_issuer,
        settings.oidc_client_id,
        settings.oidc_client_secret,
        settings.oidc_scopes,
    )


Oidc = Annotated[OidcProvider | None, Depends(get_oidc_provider)]
