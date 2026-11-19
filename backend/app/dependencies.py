from dataclasses import dataclass
from uuid import UUID
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .security import verify_access_token, Principal
from .db import get_pool
bearer = HTTPBearer(auto_error=False)

@dataclass
class TenantContext:
    principal: Principal
    organization_id: str
    user_id: str
    role: str
    conn: object

async def get_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentification requise.")
    return verify_access_token(credentials.credentials)

async def get_tenant_context(request: Request, principal: Principal = Depends(get_principal),
        x_organization_id: str | None = Header(default=None, alias="X-Organization-ID")):
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
            # A verified OIDC email is required for any customer access.
            if not principal.email_verified or not principal.email:
                raise HTTPException(403, "Vérifiez votre adresse e-mail auprès de votre fournisseur de connexion pour activer l'accès.")
            account = await conn.fetchrow("""
                UPDATE users SET email=lower(trim($3)),
                  email_verified_at=COALESCE(email_verified_at,now())
                WHERE id=$1::uuid AND oidc_issuer=$2 AND status='ACTIVE'
                RETURNING email,trial_started_at,trial_expires_at
            """, str(row["user_id"]), principal.issuer, principal.email)
            if not account:
                raise HTTPException(403, "Compte actif introuvable.")
            founder = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM founder_entitlements
                  WHERE user_id=$1::uuid AND revoked_at IS NULL)
            """, str(row["user_id"]))
            subscription = await conn.fetchrow("""
                SELECT status,current_period_end FROM subscriptions
                WHERE organization_id=$1::uuid
            """, org_id)
            now = await conn.fetchval("SELECT now()")
            paid = bool(subscription and subscription["status"] in ("ACTIVE","TRIAL")
                and (subscription["current_period_end"] is None or subscription["current_period_end"] > now))
            trial_claim_conflict = False
            if account["trial_started_at"] is None and not (founder or paid):
                claimed = await conn.fetchval(
                    "SELECT claim_trial_email($1::uuid,$2)", str(row["user_id"]), account["email"])
                if claimed:
                    account = await conn.fetchrow("""
                        UPDATE users SET trial_started_at=COALESCE(trial_started_at,now()),
                          trial_expires_at=COALESCE(trial_expires_at,COALESCE(trial_started_at,now())+interval '72 hours')
                        WHERE id=$1::uuid
                        RETURNING email,trial_started_at,trial_expires_at
                    """, str(row["user_id"]))
                else:
                    trial_claim_conflict = True
            trial_active = bool(account["trial_expires_at"] and account["trial_expires_at"] > now)
            # Billing and identity routes stay available after trial expiry so the
            # customer can subscribe, retrieve invoices, or inspect access status.
            billing_access_paths = {
                "/api/v1/auth/me", "/api/v1/organizations",
                "/api/v1/billing/subscription", "/api/v1/billing/invoices",
                "/api/v1/billing/checkout", "/api/v1/billing/portal",
                "/api/v1/access/status",
            }
            if not (founder or paid or trial_active) and request.url.path not in billing_access_paths:
                if trial_claim_conflict:
                    raise HTTPException(409, {
                        "code": "TRIAL_ALREADY_USED",
                        "message": "Cette adresse e-mail vérifiée a déjà servi à activer une période d'essai. Connectez-vous au compte initial ou souscrivez une offre.",
                    })
                raise HTTPException(402, {
                    "code": "TRIAL_EXPIRED",
                    "message": "Votre période d'essai de 72 heures est terminée. Souscrivez une offre pour retrouver l'accès à Dikévia. Vos données sont conservées.",
                    "trial_expires_at": account["trial_expires_at"].isoformat() if account["trial_expires_at"] else None,
                })
            yield TenantContext(principal, org_id, str(row["user_id"]), row["role"], conn)

async def require_org_admin(ctx: TenantContext = Depends(get_tenant_context)):
    if ctx.role != "ORG_ADMIN":
        raise HTTPException(403, "Permission insuffisante.")
    return ctx
async def require_legal_editor(ctx: TenantContext = Depends(get_tenant_context)):
    if ctx.role not in ("ORG_ADMIN","LEGAL_EDITOR"):
        raise HTTPException(403, "Permission insuffisante.")
    return ctx


async def require_platform_admin(principal: Principal = Depends(get_principal)):
    """Platform authority is read from the dedicated global registry, never from a tenant role."""
    if not principal.email_verified or not principal.email:
        raise HTTPException(403, "Une adresse e-mail vérifiée est requise pour les opérations administrateur.")
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            row = await conn.fetchrow(
                "SELECT u.id FROM users u JOIN platform_admins pa ON pa.user_id=u.id "
                "WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'",
                principal.issuer, principal.subject)
    if not row:
        raise HTTPException(403, "Droit administrateur plateforme requis.")
    return {"principal": principal, "user_id": str(row["id"])}
