from dataclasses import dataclass
from functools import lru_cache
import logging
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException
from .config import settings

logger = logging.getLogger(__name__)

MAX_BEARER_TOKEN_LENGTH = 16_384
MAX_ACCESS_TOKEN_LIFETIME_SECONDS = 900
ALLOWED_OIDC_ALGORITHMS = {"RS256", "ES256"}

@dataclass(frozen=True)
class Principal:
    subject: str
    issuer: str
    email: str | None = None
    email_verified: bool = False

@lru_cache(maxsize=1)
def jwks_client(url: str):
    # Short network timeout prevents a slow/unavailable identity provider from
    # tying up an API worker for the HTTP client's default timeout.
    return PyJWKClient(url, cache_keys=True, lifespan=300, timeout=5)

def verify_access_token(token: str) -> Principal:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(503, "Authentification OIDC non configurée.")
    if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
        raise HTTPException(401, "Jeton invalide ou expiré.")
    algorithms = [a.strip() for a in settings.oidc_algorithms.split(",") if a.strip()]
    if not algorithms or any(a not in ALLOWED_OIDC_ALGORITHMS for a in algorithms):
        raise HTTPException(503, "Configuration des algorithmes OIDC non sûre.")
    try:
        key = jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=algorithms,
            audience=settings.oidc_audience, issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "iss", "sub", "aud"], "verify_signature": True},
            leeway=30,
        )
        subject, issuer = claims.get("sub"), claims.get("iss")
        issued_at, expires_at = claims.get("iat"), claims.get("exp")
        if (not isinstance(subject, str) or not subject.strip() or issuer != settings.oidc_issuer
                or not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float))
                or expires_at <= issued_at or expires_at - issued_at > MAX_ACCESS_TOKEN_LIFETIME_SECONDS):
            raise ValueError("Claims OIDC invalides ou durée de jeton excessive")
        email = claims.get("email")
        if email is not None and (not isinstance(email, str) or len(email) > 320):
            email = None
        verified = claims.get("email_verified") is True
        return Principal(subject=subject, issuer=issuer, email=email, email_verified=verified)
    except HTTPException:
        raise
    except Exception as exc:
        # Log only the exception class: never log a bearer token, claims or
        # provider response body. Keep the public 401 deliberately generic.
        logger.warning("OIDC access-token validation failed (%s)", type(exc).__name__)
        raise HTTPException(401, "Jeton invalide ou expiré.")
