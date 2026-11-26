from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_access_token, verify_identity_token, Principal, auth_log
from .db import get_pool
from .config import settings
from .auth_sessions import get_session_principal, SESSION_COOKIE, require_same_origin

bearer = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    principal: Principal
    organization_id: str
    user_id: str
    role: str
    conn: object | None


def _require_verified_auth0_email(principal: Principal) -> Principal:
    if not principal.email or not principal.email_verified:
        auth_log.warning("auth_rejected reason=email_not_verified status=403")
        raise HTTPException(
            403,
            "Adresse e-mail non vérifiée. Ouvrez le lien de vérification reçu par e-mail puis reconnectez-vous.",
        )
    return principal


async def _resolve_auth0_legacy_identity(principal: Principal) -> Principal:
    """Map only Auth0 DB users whose exact legacy identity still exists in Dikévia."""
    if settings.oidc_provider != "auth0" or not settings.oidc_identity_compat_issuer:
        return principal
    prefix = settings.oidc_identity_subject_prefix
    if not prefix or not principal.subject.startswith(prefix):
        return principal
    legacy_subject = principal.subject[len(prefix):]
    if not legacy_subject:
        return principal
    # The lookup is constrained by PostgreSQL RLS to this exact candidate
    # identity. No email matching or user-supplied legacy claim is trusted.
    try:
        async with get_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.oidc_issuer',$1,true)",
                    settings.oidc_identity_compat_issuer,
                )
                await conn.execute(
                    "SELECT set_config('app.oidc_subject',$1,true)",
                    legacy_subject,
                )
                row = await conn.fetchrow(
                    "SELECT id FROM users WHERE oidc_issuer=$1 AND oidc_subject=$2 AND status='ACTIVE'",
                    settings.oidc_identity_compat_issuer, legacy_subject,
                )
    except Exception:
        auth_log.error("auth_rejected reason=legacy_identity_lookup_unavailable status=503")
        raise HTTPException(503, "Vérification de l'identité historique momentanément indisponible.")
    if not row:
        return principal
    return Principal(
        subject=legacy_subject,
        issuer=settings.oidc_identity_compat_issuer,
        email=principal.email,
        email_verified=principal.email_verified,
    )


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_oidc_id_token: str | None = Header(default=None, alias="X-OIDC-ID-Token"),
    request: Request = None,
):
    if request is not None and settings.oidc_server_sessions_enabled and request.cookies.get(SESSION_COOKIE):
        if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            require_same_origin(request)
        principal = await get_session_principal(request)
        if settings.oidc_provider == "auth0":
            principal = _require_verified_auth0_email(principal)
            principal = await _resolve_auth0_legacy_identity(principal)
        return principal
    if credentials is None or credentials.scheme.lower() != "bearer":
        auth_log.warning("auth_rejected reason=bearer_missing status=401")
        raise HTTPException(401, "Authentification requise.")
    principal = verify_access_token(credentials.credentials)
    if settings.oidc_provider == "auth0":
        if not x_oidc_id_token:
            raise HTTPException(401, "Jeton d'identité OIDC manquant. Reconnectez-vous.")
        principal = verify_identity_token(x_oidc_id_token, principal)
        principal = _require_verified_auth0_email(principal)
        principal = await _resolve_auth0_legacy_identity(principal)
    return principal


async def get_tenant_context(
    principal: Principal = Depends(get_principal),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
):
    if not x_organization_id:
        raise HTTPException(400, "Sélectionnez une organisation.")
    try:
        org_id = str(UUID(x_organization_id))
    except ValueError:
        raise HTTPException(400, "Identifiant d'organisation invalide.")
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            row = await conn.fetchrow("""
                SELECT u.id user_id, m.role FROM users u
                JOIN memberships m ON m.user_id=u.id
                JOIN organizations o ON o.id=m.organization_id
                WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'
                AND m.status='ACTIVE' AND o.status='ACTIVE' AND o.id=$3::uuid
            """, principal.issuer, principal.subject, org_id)
            if not row:
                raise HTTPException(403, "Accès à cette organisation refusé.")
            await conn.execute("SELECT set_config('app.current_org_id',$1,true)", org_id)
            await conn.execute("SELECT set_config('app.current_user_id',$1,true)", str(row["user_id"]))
            yield TenantContext(principal, org_id, str(row["user_id"]), row["role"], conn)


async def get_tenant_identity(
    principal: Principal = Depends(get_principal),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
):
    """Resolve tenant membership without holding a connection during downstream work."""
    if not x_organization_id:
        raise HTTPException(400, "Sélectionnez une organisation.")
    try:
        org_id = str(UUID(x_organization_id))
    except ValueError:
        raise HTTPException(400, "Identifiant d'organisation invalide.")
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            row = await conn.fetchrow("""
                SELECT u.id user_id, m.role FROM users u
                JOIN memberships m ON m.user_id=u.id
                JOIN organizations o ON o.id=m.organization_id
                WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'
                AND m.status='ACTIVE' AND o.status='ACTIVE' AND o.id=$3::uuid
            """, principal.issuer, principal.subject, org_id)
    if not row:
        raise HTTPException(403, "Accès à cette organisation refusé.")
    return TenantContext(principal, org_id, str(row["user_id"]), row["role"], None)


async def require_org_admin(ctx: TenantContext = Depends(get_tenant_context)):
    if ctx.role != "ORG_ADMIN":
        raise HTTPException(403, "Permission insuffisante.")
    return ctx


async def require_legal_editor(ctx: TenantContext = Depends(get_tenant_context)):
    if ctx.role not in ("ORG_ADMIN", "LEGAL_EDITOR"):
        raise HTTPException(403, "Permission insuffisante.")
    return ctx


async def get_tenant_context_for_chat(
    principal: Principal = Depends(get_principal),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-ID"),
):
    """Keep tenant RLS identity on one connection, but never an open transaction during external calls."""
    if not x_organization_id:
        raise HTTPException(400, "Sélectionnez une organisation.")
    try:
        org_id = str(UUID(x_organization_id))
    except ValueError:
        raise HTTPException(400, "Identifiant d'organisation invalide.")
    async with get_pool().acquire() as conn:
        try:
            await conn.execute(
                """SELECT
                    set_config('app.oidc_issuer',$1,false),
                    set_config('app.oidc_subject',$2,false),
                    set_config('app.current_org_id','',false),
                    set_config('app.current_user_id','',false)""",
                principal.issuer, principal.subject,
            )
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT u.id user_id, m.role FROM users u
                    JOIN memberships m ON m.user_id=u.id
                    JOIN organizations o ON o.id=m.organization_id
                    WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'
                    AND m.status='ACTIVE' AND o.status='ACTIVE' AND o.id=$3::uuid""",
                    principal.issuer, principal.subject, org_id,
                )
            if not row:
                raise HTTPException(403, "Accès à cette organisation refusé.")
            user_id = str(row["user_id"])
            await conn.execute(
                """SELECT
                    set_config('app.current_org_id',$1,false),
                    set_config('app.current_user_id',$2,false)""",
                org_id, user_id,
            )
            yield TenantContext(principal, org_id, user_id, row["role"], conn)
        finally:
            try:
                await conn.execute(
                    """SELECT
                        set_config('app.oidc_issuer','',false),
                        set_config('app.oidc_subject','',false),
                        set_config('app.current_org_id','',false),
                        set_config('app.current_user_id','',false)"""
                )
            except Exception:
                terminate = getattr(conn, "terminate", None)
                if callable(terminate):
                    terminate()

async def require_org_admin_for_external(
    ctx: TenantContext = Depends(get_tenant_context_for_chat),
):
    """Authorize an admin without holding a DB transaction during external calls."""
    if ctx.role != "ORG_ADMIN":
        raise HTTPException(403, "Permission insuffisante.")
    return ctx


async def require_legal_editor_for_external(
    ctx: TenantContext = Depends(get_tenant_context_for_chat),
):
    """Authorize document editors without a DB transaction during external I/O."""
    if ctx.role not in ("ORG_ADMIN", "LEGAL_EDITOR"):
        raise HTTPException(403, "Permission insuffisante.")
    return ctx


async def require_platform_admin(principal: Principal = Depends(get_principal)):
    """Platform authority is read from the dedicated global registry, never from a tenant role."""
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            row = await conn.fetchrow(
                "SELECT u.id FROM users u JOIN platform_admins pa ON pa.user_id=u.id "
                "WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'",
                principal.issuer,
                principal.subject,
            )
    if not row:
        raise HTTPException(403, "Droit administrateur plateforme requis.")
    return {"principal": principal, "user_id": str(row["id"])}
