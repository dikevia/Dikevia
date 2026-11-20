import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from jwt import exceptions as jwt_exc
from fastapi import HTTPException

from .config import settings

MAX_BEARER_TOKEN_LENGTH = 16_384
MAX_ACCESS_TOKEN_LIFETIME_SECONDS = 900
ALLOWED_OIDC_ALGORITHMS = {"RS256", "ES256"}

# Authentication diagnostics: fixed, non-sensitive reason codes only.
# Never log bearer tokens, claims, user identifiers, or provider exception text.
auth_log = logging.getLogger("dikevia.auth")


@dataclass(frozen=True)
class Principal:
    subject: str
    issuer: str
    email: str | None = None
    email_verified: bool = False


@lru_cache(maxsize=1)
def jwks_client(url: str):
    # Bound network waits so an unavailable identity provider cannot tie up
    # an API worker for the HTTP client's default timeout.
    return PyJWKClient(url, cache_keys=True, lifespan=300, timeout=5)


def reject(
    reason: str,
    status: int = 401,
    detail: str = "Jeton invalide ou expiré.",
) -> HTTPException:
    """Log a non-sensitive reason code and return a neutral HTTP error."""
    auth_log.warning("auth_rejected reason=%s status=%s", reason, status)
    return HTTPException(status, detail)


def _reason_from_exception(exc: Exception) -> tuple[str, int]:
    """Map PyJWT/JWKS exceptions to stable reason codes and HTTP statuses."""
    if isinstance(exc, jwt_exc.PyJWKClientConnectionError):
        return "jwks_unavailable", 503
    if isinstance(exc, jwt_exc.PyJWKClientError):
        return "jwks_key_not_found", 401
    if isinstance(exc, jwt_exc.ExpiredSignatureError):
        return "expired", 401
    if isinstance(exc, jwt_exc.InvalidAudienceError):
        return "aud_mismatch", 401
    if isinstance(exc, jwt_exc.InvalidIssuerError):
        return "iss_mismatch", 401
    if isinstance(exc, jwt_exc.MissingRequiredClaimError):
        claim = getattr(exc, "claim", "")
        if claim in {"exp", "iat", "iss", "sub", "aud"}:
            return f"missing_claim_{claim}", 401
        return "missing_claim", 401
    if isinstance(exc, jwt_exc.InvalidSignatureError):
        return "bad_signature", 401
    if isinstance(exc, jwt_exc.InvalidAlgorithmError):
        return "alg_not_allowed", 401
    if isinstance(exc, (jwt_exc.ImmatureSignatureError, jwt_exc.InvalidIssuedAtError)):
        return "not_yet_valid", 401
    if isinstance(exc, jwt_exc.DecodeError):
        return "malformed_token", 401
    if isinstance(exc, jwt_exc.PyJWTError):
        return "invalid_token", 401
    # Internal failures are identified by class only; never log str(exc).
    return f"internal_{type(exc).__name__}", 401


def verify_access_token(token: str) -> Principal:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise reject("oidc_not_configured", 503, "Authentification OIDC non configurée.")
    if not token or len(token) > MAX_BEARER_TOKEN_LENGTH:
        raise reject("token_empty_or_too_long")
    algorithms = [a.strip() for a in settings.oidc_algorithms.split(",") if a.strip()]
    if not algorithms or any(a not in ALLOWED_OIDC_ALGORITHMS for a in algorithms):
        raise reject("oidc_algorithms_unsafe", 503, "Configuration des algorithmes OIDC non sûre.")

    try:
        key = jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
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
        subject, issuer = claims.get("sub"), claims.get("iss")
        issued_at, expires_at = claims.get("iat"), claims.get("exp")

        if not isinstance(subject, str) or not subject.strip():
            raise reject("sub_invalid")
        if issuer != settings.oidc_issuer:
            raise reject("iss_mismatch")
        if not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float)):
            raise reject("time_claims_invalid")
        if expires_at <= issued_at:
            raise reject("lifetime_invalid")
        if expires_at - issued_at > MAX_ACCESS_TOKEN_LIFETIME_SECONDS:
            raise reject("lifetime_excessive")

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
    except HTTPException:
        raise
    except Exception as exc:
        reason, status = _reason_from_exception(exc)
        if status == 503:
            raise reject(
                reason,
                503,
                "Service d'identité momentanément indisponible. Réessayez.",
            )
        raise reject(reason)
