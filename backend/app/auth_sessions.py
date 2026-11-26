"""Opt-in BFF for OIDC: opaque HttpOnly cookie, encrypted server-side tokens."""
import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from .auth_session_crypto import decrypt_session_value, encrypt_session_value, hash_session_cookie
from .config import settings
from .db import get_pool
from .security import Principal, verify_access_token, verify_identity_token

router = APIRouter(prefix="/api/v1/auth/oidc", tags=["authentication"])
log = logging.getLogger("dikevia.auth.sessions")
SESSION_COOKIE, FLOW_COOKIE = "dikevia_session", "dikevia_oidc_flow"
SESSION_AGE, FLOW_AGE = 30 * 86400, 600
_metadata_cache = None


def _enabled():
    if not settings.oidc_server_sessions_enabled:
        raise HTTPException(404, "Authentification par session serveur non activée.")


def _b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _redirect_uri():
    uri = settings.oidc_redirect_uri
    parsed = urlparse(uri)
    allowed = {x.strip().rstrip("/") for x in settings.cors_origins.split(",") if x.strip()}
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or (parsed.scheme + "://" + parsed.netloc).rstrip("/") not in allowed:
        raise HTTPException(503, "Configuration de retour OIDC invalide.")
    return uri


def require_same_origin(request):
    origin = request.headers.get("origin", "").rstrip("/")
    allowed = {x.strip().rstrip("/") for x in settings.cors_origins.split(",") if x.strip()}
    if not origin or origin not in allowed:
        raise HTTPException(403, "Origine de requête non autorisée.")


async def _metadata():
    global _metadata_cache
    if _metadata_cache:
        return _metadata_cache
    issuer = settings.oidc_issuer
    if not issuer.startswith("https://"):
        raise HTTPException(503, "Émetteur OIDC HTTPS requis.")
    try:
        async with httpx.AsyncClient(timeout=6, follow_redirects=False) as client:
            response = await client.get(issuer.rstrip("/") + "/.well-known/openid-configuration")
        response.raise_for_status()
        data = response.json()
    except Exception:
        log.warning("oidc_metadata_unavailable")
        raise HTTPException(503, "Fournisseur d’identité momentanément indisponible.")
    if data.get("issuer") != issuer:
        raise HTTPException(503, "Métadonnées OIDC incohérentes.")
    host = urlparse(issuer).hostname
    for key in ("authorization_endpoint", "token_endpoint", "revocation_endpoint", "end_session_endpoint"):
        value = data.get(key)
        if value and (urlparse(value).scheme != "https" or urlparse(value).hostname != host):
            raise HTTPException(503, "Endpoint OIDC hors de l’émetteur configuré.")
    if not data.get("authorization_endpoint") or not data.get("token_endpoint"):
        raise HTTPException(503, "Métadonnées OIDC incomplètes.")
    _metadata_cache = data
    return data


def _flow(value):
    try:
        data = json.loads(decrypt_session_value(_unb64(value), "login-flow"))
        if not isinstance(data, dict) or data.get("expires", 0) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError()
        return data
    except Exception:
        raise HTTPException(401, "Flux de connexion expiré. Recommencez.")


def _claims(token):
    try:
        return json.loads(_unb64(token.split(".")[1]))
    except Exception:
        raise HTTPException(401, "Jeton d’identité invalide.")


def _cookies(response):
    response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/oidc", httponly=True,
                           secure=settings.app_env == "production", samesite="lax")


@router.get("/login")
async def login():
    _enabled()
    from .auth_session_crypto import decode_encryption_key
    decode_encryption_key(settings.oidc_session_encryption_key)
    metadata, redirect_uri = await _metadata(), _redirect_uri()
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    flow = {"state": state, "nonce": nonce, "verifier": verifier,
            "expires": int(datetime.now(timezone.utc).timestamp()) + FLOW_AGE}
    encrypted = encrypt_session_value(json.dumps(flow, separators=(",", ":")), "login-flow")
    params = {"client_id": settings.oidc_client_id, "response_type": "code",
              "redirect_uri": redirect_uri, "scope": settings.oidc_scopes,
              "state": state, "nonce": nonce, "code_challenge": challenge,
              "code_challenge_method": "S256"}
    audience = settings.oidc_authorization_audience or settings.oidc_audience
    if audience and settings.oidc_provider == "auth0":
        params["audience"] = audience
    response = RedirectResponse(metadata["authorization_endpoint"] + "?" + urlencode(params), 302)
    response.set_cookie(FLOW_COOKIE, _b64(encrypted), max_age=FLOW_AGE, httponly=True,
                        secure=settings.app_env == "production", samesite="lax",
                        path="/api/v1/auth/oidc")
    return response


@router.post("/callback")
async def callback(request: Request):
    _enabled()
    require_same_origin(request)
    flow_cookie = request.cookies.get(FLOW_COOKIE)
    if not flow_cookie:
        raise HTTPException(401, "Flux de connexion absent ou expiré.")
    flow = _flow(flow_cookie)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Retour OIDC invalide.")
    code, state = body.get("code"), body.get("state")
    if not isinstance(code, str) or not code or len(code) > 4096 or state != flow["state"]:
        raise HTTPException(401, "État OIDC invalide.")
    metadata = await _metadata()
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False) as client:
            response = await client.post(metadata["token_endpoint"], data={
                "grant_type": "authorization_code", "client_id": settings.oidc_client_id,
                "code": code, "redirect_uri": _redirect_uri(), "code_verifier": flow["verifier"]})
        if response.status_code != 200:
            raise ValueError()
        tokens = response.json()
    except Exception:
        log.warning("oidc_code_exchange_failed")
        raise HTTPException(401, "Connexion refusée par le fournisseur d’identité.")
    access, identity, refresh, expires = (tokens.get("access_token"), tokens.get("id_token"),
                                           tokens.get("refresh_token"), tokens.get("expires_in"))
    if not all(isinstance(x, str) and x for x in (access, identity, refresh)) or not isinstance(expires, int) or not 1 <= expires <= 86400:
        raise HTTPException(401, "Réponse OIDC incomplète.")
    principal = verify_access_token(access)
    identity_principal = verify_identity_token(identity, principal)
    if _claims(identity).get("nonce") != flow["nonce"]:
        raise HTTPException(401, "Nonce OIDC invalide.")
    if settings.oidc_provider == "auth0" and (not identity_principal.email or not identity_principal.email_verified):
        raise HTTPException(403, "Adresse e-mail Auth0 non vérifiée.")
    cookie = secrets.token_urlsafe(48)
    await get_pool().execute(
        """INSERT INTO oidc_sessions(session_token_hash,oidc_issuer,oidc_subject,
        access_token_ciphertext,id_token_ciphertext,refresh_token_ciphertext,
        access_expires_at,email,email_verified)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
        hash_session_cookie(cookie), principal.issuer, principal.subject,
        encrypt_session_value(access,"access"), encrypt_session_value(identity,"identity"),
        encrypt_session_value(refresh,"refresh"),
        datetime.now(timezone.utc)+timedelta(seconds=expires),
        identity_principal.email, identity_principal.email_verified)
    result = JSONResponse({"authenticated": True})
    result.set_cookie(SESSION_COOKIE,cookie,max_age=SESSION_AGE,httponly=True,
                      secure=settings.app_env=="production",samesite="lax",path="/")
    _cookies(result)
    return result


async def _refresh(pool, digest):
    invalid, result = False, None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM oidc_sessions WHERE session_token_hash=$1 AND revoked_at IS NULL FOR UPDATE",digest)
            if not row:
                invalid = True
            elif row["access_expires_at"] > datetime.now(timezone.utc)+timedelta(seconds=60):
                result = row
            else:
                try:
                    refresh = decrypt_session_value(row["refresh_token_ciphertext"],"refresh")
                    metadata = await _metadata()
                    async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:
                        response = await client.post(metadata["token_endpoint"],data={
                            "grant_type":"refresh_token","client_id":settings.oidc_client_id,"refresh_token":refresh})
                    if response.status_code != 200:
                        raise ValueError()
                    tokens = response.json()
                    access = tokens.get("access_token")
                    expires = tokens.get("expires_in")
                    if not isinstance(access,str) or not access or not isinstance(expires,int) or not 1<=expires<=86400:
                        raise ValueError()
                    principal=verify_access_token(access)
                    if principal.issuer!=row["oidc_issuer"] or principal.subject!=row["oidc_subject"]:
                        raise ValueError()
                    new_refresh=tokens.get("refresh_token") or refresh
                    identity=tokens.get("id_token")
                    if identity:
                        ident=verify_identity_token(identity,principal)
                        if settings.oidc_provider == "auth0" and not ident.email_verified:
                            raise ValueError()
                        id_cipher = encrypt_session_value(identity, "identity")
                        email = ident.email or row["email"]
                        verified = ident.email_verified
                    else:
                        id_cipher = row["id_token_ciphertext"]
                        email = row["email"]
                        verified = row["email_verified"]
                    result=await conn.fetchrow("""UPDATE oidc_sessions SET access_token_ciphertext=$2,
                    id_token_ciphertext=$3,refresh_token_ciphertext=$4,access_expires_at=$5,
                    email=$6,email_verified=$7,last_seen_at=now()
                    WHERE session_token_hash=$1 AND revoked_at IS NULL RETURNING *""",
                    digest,encrypt_session_value(access,"access"),id_cipher,
                    encrypt_session_value(new_refresh,"refresh"),
                    datetime.now(timezone.utc)+timedelta(seconds=expires),email,verified)
                except Exception:
                    await conn.execute("UPDATE oidc_sessions SET revoked_at=now() WHERE session_token_hash=$1",digest)
                    invalid=True
    if invalid or result is None:
        raise HTTPException(401,"Session expirée. Reconnectez-vous.")
    return result


async def get_session_principal(request: Request) -> Principal:
    _enabled()
    cookie=request.cookies.get(SESSION_COOKIE)
    if not cookie:
        raise HTTPException(401,"Session absente. Connectez-vous.")
    try:
        digest = hash_session_cookie(cookie)
    except ValueError:
        raise HTTPException(401, "Session invalide.")
    pool=get_pool()
    row=await pool.fetchrow("SELECT * FROM oidc_sessions WHERE session_token_hash=$1 AND revoked_at IS NULL",digest)
    if not row:
        raise HTTPException(401, "Session expirée ou révoquée.")
    if row["access_expires_at"]<=datetime.now(timezone.utc)+timedelta(seconds=60):
        row=await _refresh(pool,digest)
    try:
        principal = verify_access_token(decrypt_session_value(row["access_token_ciphertext"], "access"))
    except Exception:
        raise HTTPException(401, "Session invalide. Reconnectez-vous.")
    if principal.issuer!=row["oidc_issuer"] or principal.subject!=row["oidc_subject"]:
        raise HTTPException(401,"Identité de session incohérente.")
    await pool.execute("""UPDATE oidc_sessions SET last_seen_at=now() WHERE session_token_hash=$1
    AND revoked_at IS NULL AND last_seen_at<now()-interval '5 minutes'""",digest)
    return Principal(principal.subject,principal.issuer,row["email"] or principal.email,
                     bool(row["email_verified"]) or principal.email_verified)


@router.get("/session")
async def session(request: Request):
    principal=await get_session_principal(request)
    return {"authenticated":True,"email":principal.email}


@router.post("/logout")
async def logout(request: Request):
    _enabled()
    require_same_origin(request)
    cookie = request.cookies.get(SESSION_COOKIE)
    logout_url = None
    if cookie:
        try:
            digest = hash_session_cookie(cookie)
            pool = get_pool()
            row=await pool.fetchrow("SELECT refresh_token_ciphertext FROM oidc_sessions WHERE session_token_hash=$1 AND revoked_at IS NULL",digest)
            await pool.execute("UPDATE oidc_sessions SET revoked_at=now() WHERE session_token_hash=$1 AND revoked_at IS NULL",digest)
            if row:
                metadata=await _metadata()
                try:
                    if metadata.get("revocation_endpoint"):
                        refresh=decrypt_session_value(row["refresh_token_ciphertext"],"refresh")
                        async with httpx.AsyncClient(timeout=5,follow_redirects=False) as client:
                            await client.post(metadata["revocation_endpoint"],data={"token":refresh,"token_type_hint":"refresh_token","client_id":settings.oidc_client_id})
                except Exception:
                    log.warning("oidc_provider_revocation_failed")
                if metadata.get("end_session_endpoint"):
                    logout_url=metadata["end_session_endpoint"]+"?"+urlencode({"client_id":settings.oidc_client_id,"post_logout_redirect_uri":_redirect_uri()})
        except ValueError:
            pass
    result=JSONResponse({"logged_out":True,"logout_url":logout_url})
    result.delete_cookie(SESSION_COOKIE,path="/",httponly=True,secure=settings.app_env=="production",samesite="lax")
    _cookies(result)
    return result
