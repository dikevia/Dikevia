from dataclasses import dataclass
from functools import lru_cache
import logging

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException

from .config import settings

logger = logging.getLogger("dikevia.security")

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


def _reject_token(reason: str, error_type: str = "-") -> None:
    """Log a non-sensitive internal reason while keeping the public response opaque."""
    logger.warning(
        "OIDC_AUTH_REJECTED reason=%s error_type=%s",
        reason,
        error_type,
    )
    raise HTTPException(401, "Jeton invalide ou expiré.")


def verify_access_token(token: str) -> Principal:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(503, "Authentification OIDC non configurée.")
    if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
        _reject_token("token_missing_or_oversized")
    algorithms = [a.strip() for a in settings.oidc_algorithms.split(",") if a.strip()]
    if not algorithms or any(a not in ALLOWED_OIDC_ALGORITHMS for a in algorithms):
        raise HTTPException(503, "Configuration des algorithmes OIDC non sûre.")

    # Keep JWKS/network failures separate from JWT validation failures. Never log
    # the bearer token, claims, subject, email, or exception message.
    try:
        key = jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
    except Exception as exc:
        _reject_token("jwks_unavailable", type(exc).__name__)

    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=algorithms,
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={
                "require": ["exp", "iat", "iss", "sub", "aud"],
                "verify_signature": True,
            },
            leeway=30,
        )
    except jwt.ExpiredSignatureError as exc:
        _reject_token("token_expired", type(exc).__name__)
    except jwt.InvalidAudienceError as exc:
        _reject_token("audience_mismatch", type(exc).__name__)
    except jwt.InvalidIssuerError as exc:
        _reject_token("issuer_mismatch", type(exc).__name__)
    except jwt.InvalidSignatureError as exc:
        _reject_token("signature_invalid", type(exc).__name__)
    except jwt.MissingRequiredClaimError as exc:
        _reject_token("required_claim_missing", type(exc).__name__)
    except jwt.InvalidTokenError as exc:
        _reject_token("token_invalid", type(exc).__name__)
    except Exception as exc:
        _reject_token("token_validation_error", type(exc).__name__)

    subject, issuer = claims.get("sub"), claims.get("iss")
    issued_at, expires_at = claims.get("iat"), claims.get("exp")
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or issuer != settings.oidc_issuer
        or not isinstance(issued_at, (int, float))
        or not isinstance(expires_at, (int, float))
        or expires_at <= issued_at
    ):
        _reject_token("claims_invalid")
    if expires_at - issued_at > MAX_ACCESS_TOKEN_LIFETIME_SECONDS:
        _reject_token("token_lifetime_exceeded")

    email = claims.get("email")
    if email is not None and (not isinstance(email, str) or len(email) > 320):
        email = None
    verified = claims.get("email_verified") is True
    return Principal(
        subject=subject,
        issuer=issuer,
        email=email,
        email_verified=verified,
    )
