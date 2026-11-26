from contextlib import asynccontextmanager
import asyncio
import logging
import os
from uuid import uuid4, UUID
import hashlib
import json
import re
import secrets
import os
import zipfile
from io import BytesIO
from datetime import date, datetime, timezone
from fastapi import UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse
from .config import settings, validate_runtime_configuration
from .db import open_pool, close_pool, get_pool, get_corpus_ingest_pool, get_platform_admin_pool, assert_runtime_role_is_safe
from .dependencies import get_principal, get_tenant_context, get_tenant_identity, get_tenant_context_for_chat, require_org_admin, require_legal_editor, require_org_admin_for_external, require_legal_editor_for_external, require_platform_admin, require_syndicate_subscription, TenantContext
from .security import Principal
from .schemas import AskRequest, AskResponse, InvitationCreate, InvitationAccept, OrganizationCreate, CollectivityCreate, DocumentValidationUpdate, DocumentMetadataUpdate, MemberRoleUpdate
from .orchestrator import LegalOrchestrator
from .cgfp import search_cgfp, get_cgfp_article
from .document_processing import scan_with_clamav, ScannerUnavailable, MalwareDetected, extract_document_text, document_sha256_matches
from .document_storage import StorageError, StorageNotFound, delete_private_file, read_private_file, store_private_file
from .keycloak_admin import KeycloakAdmin, KeycloakAdminConfig, KeycloakAdminError
from .mailer import send_invitation_email
from .legifrance import connector as legifrance, LegifranceUnavailable
from .jurisprudence import AdministrativeCaseLawConnector, DECISION_ID_RE
from .billing import PLANS, public_plans, verify_stripe_signature, extract_subscription_state
from .legal_corpus import upsert_legal_document, search_legal_corpus
from .legal_assurance import assess_source_set
from .ai_provider import AIAnalysisResult, AIProviderUnavailable, analyze_question, answer_references_are_grounded, extract_analysis_content, check_provider_availability
from .legal_ingestion import parse_circulaires_xml, parse_administrative_open_data_zip, administrative_open_data_archive_url
from .dossiers import build_dossier_content, validate_dossier_content
from .legal_qualification import CONVERSATION_HISTORY_MESSAGE_LIMIT
from .rate_limit import consume_chat_request, consume_daily_chat_question
from .entitlements import resolve_entitlements
from .instances import prepare_instance_with_legal_sources
from .personal_documents import router as personal_documents_router
from .auth_sessions import router as oidc_sessions_router
import httpx

CHAT_SOURCE_METADATA_FIELDS = frozenset({
    "source_type",
    "source_id",
    "official_source_id",
    "source_version_id",
    "version_id",
    "version_key",
    "text_sha256",
    "title",
    "official_number",
    "case_number",
    "signature_date",
    "decision_date",
    "valid_from",
    "valid_to",
    "requested_effective_date",
    "version_role",
    "version_endpoint",
    "version_matches_facts_date",
    "temporal_status",
    "temporal_explanation",
    "source_status",
    "excerpt",
    "official_url",
    "source_url",
    "article",
    "page_start",
    "page_end",
    "citation_integrity",
    "collectivity",
    "local_document_type",
    "validation_status",
    "effective_from",
    "effective_to",
    "content_kind",
    "official_source",
    "legal_assurance",
    "collectivity_scope",
    "document_type",
    "reference_role",
    "claim_eligible",
    "transfer_status",
})

logger = logging.getLogger("dikevia.startup")
logger.setLevel(logging.INFO)


async def _startup_external_diagnostics() -> None:
    """Non-billable startup checks: PISTE ping/search and AI model catalog only."""
    if settings.app_env != "production" or not settings.startup_external_diagnostics_enabled:
        return

    logger.warning(
        "DIKEVIA_DIAGNOSTIC CONFIG legifrance_environment=%s cetat_fulltext_enabled=%s",
        legifrance.environment if legifrance.configured else "not-configured",
        settings.legifrance_cetat_fulltext_enabled,
    )

    if legifrance.configured:
        probe_date = datetime.now(ZoneInfo("Europe/Paris")).date()
        probes = (
            ("CGFP_L111_1", "article L. 111-1", None),
            ("CODE_CIVIL_1217", "article 1217", "Code civil"),
            ("CGFP_NONEXISTENT_L999_999", "article L999-999", None),
        )
        expected = {
            "CGFP_L111_1": {"id": "LEGIARTI000044427983", "num": "L111-1"},
            "CODE_CIVIL_1217": {"num": "1217"},
            "CGFP_NONEXISTENT_L999_999": {},
        }
        for label, query, code_name in probes:
            try:
                results = await legifrance.search_code_articles(
                    query, probe_date, code_name=code_name,
                )
                if label == "CGFP_NONEXISTENT_L999_999":
                    passed = len(results) == 0
                    logger.warning(
                        "DIKEVIA_DIAGNOSTIC PISTE_PROBE name=%s verdict=%s result_count=%d get_article_calls=%d status=%s",
                        label, "PASS" if passed else "FAIL", len(results),
                        0 if not results else len(results),
                        "NO_OFFICIAL_RESULT" if passed else "UNEXPECTED_ARTICLE",
                    )
                    continue

                expected_probe = expected[label]
                if len(results) != 1:
                    logger.warning(
                        "DIKEVIA_DIAGNOSTIC PISTE_PROBE name=%s verdict=FAIL result_count=%d reason=EXPECTED_EXACTLY_ONE",
                        label, len(results),
                    )
                    continue
                item = results[0]
                actual_num = item.get("article") or ""
                normalized_num = re.sub(r"[^A-Z0-9-]", "", actual_num.upper())
                id_ok = not expected_probe.get("id") or item.get("source_id") == expected_probe["id"]
                num_ok = normalized_num == expected_probe["num"]
                text_length = len(item.get("text") or "")
                text_ok = text_length > 0 if label == "CODE_CIVIL_1217" else True
                status_ok = item.get("version_status") == "IN_FORCE_ON_REQUESTED_DATE"
                passed = id_ok and num_ok and text_ok and status_ok
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_PROBE name=%s verdict=%s result_count=%d id=%s id_ok=%s num=%s normalized_num=%s num_ok=%s valid_from=%s valid_to=%s version_status=%s status_ok=%s text_length=%d text_ok=%s",
                    label, "PASS" if passed else "FAIL", len(results),
                    item.get("source_id"), id_ok, actual_num, normalized_num, num_ok,
                    item.get("valid_from"), item.get("valid_to"),
                    item.get("version_status"), status_ok, text_length, text_ok,
                )
            except Exception as exc:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_PROBE name=%s verdict=ERROR error_type=%s",
                    label, type(exc).__name__,
                )

    else:
        logger.warning("DIKEVIA_DIAGNOSTIC PISTE=NOT_CONFIGURED")

    # Probe the regulatory-text pillar with several grounded FPT overtime query forms.
    if legifrance.configured:
        for label, query, expected_number in (
            ("IHTS_FPT_FRAMEWORK", "décret n° 91-875", "91-875"),
            ("IHTS_FPT_WORKTIME", "décret n° 2001-623", "2001-623"),
            ("IHTS_NUMBER", "décret n° 2002-60", "2002-60"),
            ("IHTS_TITLE", "indemnités horaires", None),
            ("IHTS_WORKS", "travaux supplémentaires", None),
        ):
            try:
                regulatory_probe = await legifrance.search_regulatory_texts(
                    query, probe_date, limit=3,
                )
                full_text_count = sum(
                    1 for item in regulatory_probe
                    if item.get("source_type") == "LEGIFRANCE_LODA"
                    and item.get("source_id")
                    and len(item.get("full_text") or "") >= 80
                )
                exact_reference_count = sum(
                    1 for item in regulatory_probe
                    if expected_number and item.get("official_number") == expected_number
                )
                passed = full_text_count and (
                    not expected_number or exact_reference_count > 0
                )
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_LODA_IHTS_PROBE name=%s verdict=%s result_count=%d full_text_count=%d exact_reference_count=%d",
                    label, "PASS" if passed else "NO_RESULT",
                    len(regulatory_probe), full_text_count, exact_reference_count,
                )
            except Exception as exc:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_LODA_IHTS_PROBE name=%s verdict=ERROR error_type=%s",
                    label, type(exc).__name__,
                )

    # Validate the experimental CETAT consultation contract independently.
    # Search metadata is never promoted to legal evidence unless the returned
    # decision identifier and a substantial full text both match.
    if legifrance.configured:
        try:
            cetat_probe = AdministrativeCaseLawConnector(legifrance)
            decisions = await cetat_probe.search(
                "fonction publique territoriale agent public", probe_date
            )
            if not decisions:
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_CETAT_FULLTEXT_PROBE verdict=NO_RESULT result_count=0"
                )
            else:
                decision = await cetat_probe.consult(decisions[0]["source_id"])
                full_text_length = len(decision.get("text") or "")
                passed = (
                    decision.get("source_id") == decisions[0].get("source_id")
                    and decision.get("full_text_retrieved") is True
                    and full_text_length >= 80
                )
                logger.warning(
                    "DIKEVIA_DIAGNOSTIC PISTE_CETAT_FULLTEXT_PROBE verdict=%s result_count=%d text_length=%d",
                    "PASS" if passed else "FAIL", len(decisions), full_text_length,
                )
        except Exception as exc:
            logger.warning(
                "DIKEVIA_DIAGNOSTIC PISTE_CETAT_FULLTEXT_PROBE verdict=ERROR error_type=%s",
                type(exc).__name__,
            )

    ai_configured = bool(settings.ai_api_base_url and settings.ai_api_key and settings.ai_model)
    logger.warning(
        "DIKEVIA_DIAGNOSTIC AI_CHECK_START configured=%s base_url=%s key=%s model=%s",
        ai_configured,
        bool(settings.ai_api_base_url),
        bool(settings.ai_api_key),
        settings.ai_model or "not-configured",
    )
    try:
        ai_status = await asyncio.wait_for(check_provider_availability(), timeout=12.0)
    except asyncio.TimeoutError:
        ai_status = {"status": "TIMEOUT"}
        logger.warning("DIKEVIA_DIAGNOSTIC AI_MODEL_CATALOG=TIMEOUT")
    except Exception as exc:
        logger.warning("DIKEVIA_DIAGNOSTIC AI_MODEL_CATALOG=FAILED error_type=%s", type(exc).__name__)
    else:
        logger.warning(
            "DIKEVIA_DIAGNOSTIC AI_MODEL_CATALOG=%s model=%s http_status=%s reason=%s",
            ai_status.get("status"),
            settings.ai_model or "not-configured",
            ai_status.get("http_status", "-"),
            ai_status.get("reason", "-"),
        )


async def _startup_ai_provider_diagnostic() -> None:
    """Run a read-only AI provider/model availability check in staging and production."""
    configured = bool(settings.ai_api_base_url and settings.ai_api_key and settings.ai_model)
    parsed = urlparse(settings.ai_api_base_url) if settings.ai_api_base_url else None
    provider = "gemini" if (
        parsed and parsed.hostname == "generativelanguage.googleapis.com"
        and parsed.path.rstrip("/") == "/v1beta/openai"
    ) else ("openai_compatible" if configured else "not_configured")
    logger.warning(
        "DIKEVIA_DIAGNOSTIC AI_PROVIDER_CHECK_START environment=%s provider=%s configured=%s model=%s",
        settings.app_env, provider, configured, settings.ai_model or "not-configured",
    )
    try:
        status = await asyncio.wait_for(check_provider_availability(), timeout=12.0)
    except asyncio.TimeoutError:
        logger.warning("DIKEVIA_DIAGNOSTIC AI_PROVIDER_CHECK_RESULT status=TIMEOUT")
    except Exception as exc:
        logger.warning(
            "DIKEVIA_DIAGNOSTIC AI_PROVIDER_CHECK_RESULT status=FAILED error_type=%s",
            type(exc).__name__,
        )
    else:
        logger.warning(
            "DIKEVIA_DIAGNOSTIC AI_PROVIDER_CHECK_RESULT provider=%s model=%s status=%s http_status=%s",
            provider, settings.ai_model or "not-configured",
            status.get("status"), status.get("http_status", "-"),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_configuration(settings)
    await open_pool(settings.database_url, settings.legal_corpus_ingest_database_url, settings.platform_admin_database_url)
    if settings.database_url:
        await assert_runtime_role_is_safe()
    diagnostics_enabled = settings.app_env == "production" and settings.startup_external_diagnostics_enabled
    diagnostic_tasks = (
        [asyncio.create_task(_startup_external_diagnostics()),
         asyncio.create_task(_startup_ai_provider_diagnostic())]
        if diagnostics_enabled else []
    )
    try:
        yield
    finally:
        for task in diagnostic_tasks:
            if not task.done():
                task.cancel()
        if diagnostic_tasks:
            await asyncio.gather(*diagnostic_tasks, return_exceptions=True)
        await close_pool()

app = FastAPI(title="Dikevia API", version="3.38.0", debug=settings.debug, lifespan=lifespan,
              docs_url=None if settings.app_env == "production" else "/docs",
              redoc_url=None if settings.app_env == "production" else "/redoc",
              openapi_url=None if settings.app_env == "production" else "/openapi.json")
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
        allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"],
        allow_headers=["Authorization","Content-Type","X-Organization-ID","X-OIDC-ID-Token"])
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.include_router(personal_documents_router, dependencies=[Depends(require_syndicate_subscription)])
app.include_router(oidc_sessions_router)


@app.get("/auth-config.js", include_in_schema=False)
async def browser_oidc_configuration():
    """Expose only public OIDC client settings; never return provider secrets."""
    if not settings.oidc_client_id or not settings.oidc_issuer:
        return Response(
            "/* Runtime OIDC override not configured; use the static fallback. */",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )
    redirect_origin = settings.oidc_redirect_uri.rstrip("/") if settings.oidc_redirect_uri else (settings.invitation_base_url.rstrip("/") if settings.invitation_base_url else "")
    redirect_uri = json.dumps(redirect_origin + "/") if redirect_origin else "window.location.origin + '/'"
    silent_redirect_uri = (
        json.dumps(redirect_origin + "/static/silent-check-sso.html")
        if redirect_origin else "window.location.origin + '/static/silent-check-sso.html'"
    )
    script = (
        "window.CFDT_JURIS_OIDC = Object.freeze({"
        f"issuer:{json.dumps(settings.oidc_issuer)},"
        f"client_id:{json.dumps(settings.oidc_client_id)},"
        f"redirect_uri:{redirect_uri},"
        f"silent_redirect_uri:{silent_redirect_uri},"
        f"scopes:{json.dumps(settings.oidc_scopes)},"
        f"audience:{json.dumps(settings.oidc_authorization_audience or settings.oidc_audience)},"
        f"server_sessions_enabled:{str(settings.oidc_server_sessions_enabled).lower()}"
        "});"
    )
    return Response(
        script,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


orchestrator = LegalOrchestrator()
case_law_connector = AdministrativeCaseLawConnector(legifrance)


async def record_ai_usage_event(conn, organization_id, user_id, request_id, usage):
    """Append usage metadata without allowing telemetry failure to abort a user operation.

    The nested transaction creates a savepoint when called inside a request
    transaction. If the metering table is unavailable or rejects a state, the
    savepoint is rolled back and the legal response can still be persisted.
    """
    try:
        async with conn.transaction():
            await conn.execute("""INSERT INTO ai_usage_events(
                organization_id,user_id,request_id,operation,provider,model,prompt_tokens,
                completion_tokens,total_tokens,latency_ms,outcome)
                VALUES($1::uuid,$2::uuid,$3::uuid,$4,$5,$6,$7,$8,$9,$10,$11)
            """, organization_id, user_id, request_id, usage.get("operation", "answer_generation"),
                usage["provider"], usage["model"], usage.get("prompt_tokens"),
                usage.get("completion_tokens"), usage.get("total_tokens"), usage.get("latency_ms"),
                usage["outcome"])
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "AI usage metering write failed; request processing continues (error_type=%s)",
            type(exc).__name__,
        )


async def enforce_legal_connector_rate_limit(ctx: TenantContext) -> None:
    """Share the tenant/user minute bucket with chat before direct paid PISTE calls."""
    decision = await consume_chat_request(
        ctx.conn, ctx.organization_id, ctx.user_id, settings.chat_rate_limit_per_minute
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Limite de requêtes juridiques atteinte. Réessayez dans quelques instants.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )



async def _set_tenant_rls_context(conn, ctx: TenantContext) -> None:
    """Set transaction-local identity and tenant GUCs before every protected DB unit."""
    await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", ctx.principal.issuer)
    await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", ctx.principal.subject)
    await conn.execute("SELECT set_config('app.current_org_id',$1,true)", ctx.organization_id)
    await conn.execute("SELECT set_config('app.current_user_id',$1,true)", ctx.user_id)


class _TenantScopedReadConnection:
    """Short-lived, tenant-scoped read adapter for orchestrator corpus lookups.

    The orchestrator uses this adapter only for fetch() calls against the local
    and permanent legal corpora. Each call owns a pool connection and a short
    transaction; no database connection remains checked out during AI/network
    work between searches.
    """
    def __init__(self, pool, ctx: TenantContext):
        self._pool = pool
        self._ctx = ctx

    async def fetch(self, query: str, *args):
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await _set_tenant_rls_context(conn, self._ctx)
                return await conn.fetch(query, *args)


def _chat_orchestration_failure(conversation_id: UUID) -> AskResponse:
    """Return a safe, non-technical answer when legal orchestration is unavailable."""
    return AskResponse(
        request_id=str(uuid4()),
        conversation_id=conversation_id,
        verification_status="NON_VERIFIE",
        answer=(
            "Je n’ai pas pu terminer l’analyse de votre question en raison d’un "
            "incident temporaire. Votre message a été conservé dans la conversation. "
            "Aucune conclusion juridique ne peut être donnée pour le moment. "
            "Vous pouvez réessayer dans quelques instants."
        ),
        sources=[],
        missing_information=["Analyse juridique indisponible temporairement."],
        disclaimer="Aucune réponse juridique n’a pu être établie pour cette demande.",
    )



def _ai_safe_conversation_history(rows):
    """Exclude assistant turns that may contain private local-document text.

    Consent is per request. Historical assistant turns with local sources or
    missing provenance metadata are not sent back to an external model.
    """
    safe = []
    for row in reversed(rows):
        role = row["role"]
        if role == "assistant":
            metadata = row["metadata"]
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (TypeError, ValueError):
                    metadata = None
            if not isinstance(metadata, dict):
                continue
            if metadata.get("contains_local_documents") is True:
                continue
            sources = metadata.get("sources")
            if not isinstance(sources, list):
                continue
            if any(
                isinstance(source, dict)
                and source.get("source_type") in {"LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT", "PERSONAL_DOCUMENT"}
                for source in sources
            ):
                continue
        safe.append({"role": role, "content": row["content"]})
    return safe


def decode_jsonb(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, (dict, list)) else {}

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.app_env == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response

@app.get("/health")
async def health():
    # Liveness only: does not reveal infrastructure details.
    return {"status": "ok"}

@app.get("/ready")
async def readiness():
    # Readiness is intentionally distinct from liveness and checks DB reachability.
    try:
        await get_pool().fetchval("SELECT 1")
    except Exception:
        raise HTTPException(503, "Service temporairement indisponible.")
    return {"status": "ready", "revision": os.getenv("RENDER_GIT_COMMIT", "unknown")}

@app.get("/", response_class=HTMLResponse)
async def home():
    html = (FRONTEND/"index.html").read_text(encoding="utf-8")
    flag = "true" if settings.private_instance_mode else "false"
    vector_flag = "true" if settings.vector_search_enabled else "false"
    return html.replace("</head>", f"<script>window.PRIVATE_INSTANCE_MODE={flag};window.DIKEVIA_VECTOR_SEARCH_ENABLED={vector_flag};</script></head>")

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    # Served at the origin root so the PWA worker can control the app root.
    return FileResponse(
        FRONTEND / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )

@app.get("/api/v1/auth/me")
async def auth_me(principal: Principal = Depends(get_principal)):
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            row = await conn.fetchrow("SELECT id,email,display_name,status FROM users WHERE oidc_issuer=$1 AND oidc_subject=$2",
                                      principal.issuer, principal.subject)
    if not row or row["status"] != "ACTIVE":
        raise HTTPException(403,"Compte désactivé ou non provisionné.")
    return {"id":str(row["id"]),"email":row["email"],"display_name":row["display_name"]}

@app.get("/api/v1/account/identity")
async def account_identity(ctx: TenantContext = Depends(get_tenant_context)):
    # Return only the authenticated account's internal ID; never expose raw OIDC subject.
    return {"user_id": str(ctx.user_id), "oidc_identity_verified": True}


@app.get("/api/v1/organizations")
async def organizations(principal: Principal = Depends(get_principal)):
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)",principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)",principal.subject)
            rows = await conn.fetch("""
                SELECT o.id,o.slug,o.display_name,m.role FROM users u
                JOIN memberships m ON m.user_id=u.id JOIN organizations o ON o.id=m.organization_id
                WHERE u.oidc_issuer=$1 AND u.oidc_subject=$2 AND u.status='ACTIVE'
                  AND m.status='ACTIVE' AND o.status='ACTIVE' ORDER BY o.display_name
            """,principal.issuer,principal.subject)
    return [{"id":str(r["id"]),"slug":r["slug"],"display_name":r["display_name"],"role":r["role"]} for r in rows]

@app.get("/api/v1/billing/plans")
async def billing_plans():
    """Public catalogue; hidden entirely for private instances."""
    if settings.private_instance_mode:
        raise HTTPException(404, "La facturation n'est pas disponible sur cette instance privée.")
    return {"plans": public_plans(), "billing_provider": None, "billing_enabled": False, "currency": "EUR", "notice": "Offre Agent : 5 € TTC/mois et 5 questions par jour. Offres syndicales : 5, 10 ou 15 accès, tarif à définir. Souscription en ligne désactivée."}


@app.get("/api/v1/billing/subscription")
async def billing_subscription(ctx: TenantContext = Depends(get_tenant_context)):
    founder_entitlement = await ctx.conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM platform_founder_entitlements WHERE user_id=$1::uuid AND revoked_at IS NULL)",
        ctx.user_id,
    )
    if settings.private_instance_mode:
        active = await ctx.conn.fetchval(
            "SELECT count(*) FROM memberships WHERE organization_id=$1::uuid AND status='ACTIVE'",
            ctx.organization_id)
        return {"plan_code": "PRIVATE_PREMIUM_10", "status": "FOUNDING_FREE",
                "provider": None, "max_users": 10, "active_users": active,
                "paid_active_users": 0, "free_active_users": active,
                "founder_entitlement": bool(founder_entitlement), "premium_access": True,
                "billing_enabled": False}
    row = await ctx.conn.fetchrow("""SELECT plan_code,status,provider,current_period_end,
        cancel_at_period_end,free_access_until,updated_at FROM subscriptions
        WHERE organization_id=$1::uuid""", ctx.organization_id)
    plan_code = row["plan_code"] if row else "FOUNDING_FREE"
    plan_status = row["status"] if row else "FOUNDING_FREE"
    plan = PLANS.get(plan_code, PLANS["FOUNDING_FREE"])
    seat_counts = await ctx.conn.fetchrow("SELECT * FROM tenant_billing_seat_counts($1::uuid)", ctx.organization_id)
    paid_active_users = seat_counts["paid_active_users"]
    free_active_users = seat_counts["free_active_users"]
    active_users = paid_active_users + free_active_users
    entitlements = resolve_entitlements(plan_code, plan_status, founder=bool(founder_entitlement))
    daily_questions_used = 0
    if entitlements.daily_question_limit is not None:
        daily_questions_used = await ctx.conn.fetchval(
            """SELECT COALESCE((SELECT question_count FROM chat_daily_question_usage
                WHERE user_id=$1::uuid
                  AND usage_date=(now() AT TIME ZONE 'Europe/Paris')::date),0)""",
            ctx.user_id,
        )
    return {"plan_code": plan_code, "status": plan_status, "provider": row["provider"] if row else None,
            "max_users": entitlements.max_users, "active_users": active_users,
            "paid_active_users": paid_active_users, "free_active_users": free_active_users,
            "current_period_end": row["current_period_end"] if row else None,
            "cancel_at_period_end": row["cancel_at_period_end"] if row else False,
            "free_access_until": row["free_access_until"] if row else None,
            "founder_entitlement": bool(founder_entitlement),
            "premium_access": entitlements.syndicate_tools,
            "daily_question_limit": entitlements.daily_question_limit,
            "daily_questions_used": int(daily_questions_used or 0),
            "features": {"chatbot": entitlements.chatbot, "syndicate_tools": entitlements.syndicate_tools},
            "updated_at": row["updated_at"] if row else None}


@app.get("/api/v1/billing/invoices")
async def billing_invoice_history(limit: int = 50, ctx: TenantContext = Depends(get_tenant_context)):
    if settings.private_instance_mode:
        return {"invoices": [], "billing_enabled": False}
    rows = await ctx.conn.fetch("SELECT * FROM tenant_billing_invoice_history($1::uuid,$2)",
                                 ctx.organization_id, min(max(limit, 1), 100))
    return {"invoices": [dict(r) for r in rows]}


@app.get("/api/v1/platform/commercial/summary")
async def platform_commercial_summary(month: date | None = None, platform=Depends(require_platform_admin)):
    rows = await get_platform_admin_pool().fetch("SELECT * FROM platform_admin_commercial_summary($1::uuid,COALESCE($2::date,date_trunc('month',now())::date))",
                                  platform["user_id"], month)
    return dict(rows[0]) if rows else {}


@app.get("/api/v1/platform/commercial/invoices")
async def platform_commercial_invoices(limit: int = 100, platform=Depends(require_platform_admin)):
    rows = await get_platform_admin_pool().fetch("SELECT * FROM platform_admin_commercial_invoices($1::uuid,$2)",
                                  platform["user_id"], min(max(limit, 1), 200))
    return {"invoices": [dict(r) for r in rows]}


@app.get("/api/v1/platform/commercial/organizations")
async def platform_commercial_organizations(platform=Depends(require_platform_admin)):
    rows = await get_platform_admin_pool().fetch("SELECT * FROM platform_admin_list_organizations($1::uuid)", platform["user_id"])
    output = []
    for r in rows:
        counts = await get_platform_admin_pool().fetchrow("""SELECT * FROM platform_admin_organization_seat_counts($1::uuid,$2::uuid)""",
                                           platform["user_id"], r["id"])
        output.append({"id":str(r["id"]),"name":r["display_name"],"slug":r["slug"],
            "plan_code":r["plan_code"],"subscription_status":r["subscription_status"],
            "organization_status":r["organization_status"],"active_users":int(r["active_users"]),
            "paid_active_users":int(counts["paid_active_users"]),"free_active_users":int(counts["free_active_users"]),
            "pending_invitations":int(r["pending_invitations"]),"created_at":r["created_at"]})
    return {"organizations":output}


@app.post("/api/v1/billing/checkout")
async def billing_checkout(payload: dict, ctx: TenantContext = Depends(require_org_admin_for_external)):
    if settings.private_instance_mode:
        raise HTTPException(404, "Les paiements sont désactivés sur cette instance privée.")
    if not settings.stripe_billing_enabled:
        raise HTTPException(503, "Les paiements sont désactivés tant que les tarifs syndicaux et le parcours de souscription ne sont pas validés.")
    # Do not accept payments until the monthly credit ledger and enforcement are live.
    raise HTTPException(
        503,
        "La souscription en ligne reste désactivée tant que les tarifs syndicaux et les contrôles d'abonnement ne sont pas finalisés.",
    )


@app.post("/api/v1/billing/portal")
async def billing_portal(ctx: TenantContext = Depends(require_org_admin_for_external)):
    if settings.private_instance_mode or not settings.stripe_billing_enabled:
        raise HTTPException(404, "La facturation est désactivée.")
    if not settings.stripe_secret_key:
        raise HTTPException(503, "Le portail de facturation n'est pas encore configuré.")
    customer_id = await ctx.conn.fetchval("SELECT provider_customer_id FROM subscriptions WHERE organization_id=$1::uuid", ctx.organization_id)
    if not customer_id:
        raise HTTPException(409, "Aucun client de paiement n'est associé à cet espace.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.stripe.com/v1/billing_portal/sessions",
                data={"customer": customer_id, "return_url": settings.billing_cancel_url},
                auth=(settings.stripe_secret_key, ""))
        response.raise_for_status()
        session = response.json()
    except Exception:
        raise HTTPException(502, "Impossible d'ouvrir le portail de facturation.")
    return {"portal_url": session.get("url")}


@app.post("/api/v1/billing/stripe/webhook")
async def stripe_webhook(request: Request):
    if settings.private_instance_mode or not settings.stripe_billing_enabled:
        raise HTTPException(404, "Les webhooks de paiement sont désactivés.")
    raw = await request.body()
    signature = request.headers.get("stripe-signature")
    if not verify_stripe_signature(raw, signature, settings.stripe_webhook_secret):
        raise HTTPException(400, "Signature de paiement invalide.")
    try:
        event = json.loads(raw)
        event_id = event["id"]
        event_type = event["type"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Événement de paiement invalide.")
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.stripe_webhook_verified','verified',true)")
            inserted = await conn.fetchval("""INSERT INTO billing_webhook_events(provider_event_id,event_type)
                VALUES($1,$2) ON CONFLICT DO NOTHING RETURNING provider_event_id""", event_id, event_type)
            if not inserted:
                return {"received": True, "duplicate": True}
            # Persist Stripe invoice lifecycle events as a minimal commercial ledger.
            # The webhook signature is verified above; amounts remain integer cents.
            if event_type in ("invoice.created", "invoice.finalized", "invoice.updated", "invoice.paid",
                              "invoice.payment_succeeded", "invoice.payment_failed", "invoice.voided",
                              "invoice.marked_uncollectible"):
                invoice = (event.get("data") or {}).get("object") or {}
                stripe_invoice_id = invoice.get("id")
                stripe_subscription_id = invoice.get("subscription")
                if isinstance(stripe_subscription_id, dict):
                    stripe_subscription_id = stripe_subscription_id.get("id")
                metadata = invoice.get("metadata") or {}
                org_id = metadata.get("organization_id")
                if not org_id and stripe_subscription_id:
                    org_id = await conn.fetchval(
                        "SELECT platform_lookup_org_by_stripe_subscription($1)", stripe_subscription_id)
                if org_id and stripe_invoice_id:
                    try:
                        org_id = str(UUID(str(org_id)))
                    except ValueError:
                        org_id = None
                if org_id and stripe_invoice_id:
                    transitions = invoice.get("status_transitions") or {}
                    def stripe_time(value):
                        return datetime.fromtimestamp(value, timezone.utc) if isinstance(value, (int, float)) and value > 0 else None
                    await conn.execute("""INSERT INTO stripe_invoice_records(
                        stripe_invoice_id,organization_id,stripe_customer_id,stripe_subscription_id,
                        invoice_number,status,currency,amount_due,amount_paid,amount_remaining,
                        period_start,period_end,due_at,paid_at,issued_at,hosted_invoice_url,invoice_pdf_url,updated_at)
                        VALUES($1,$2::uuid,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,now())
                        ON CONFLICT(stripe_invoice_id) DO UPDATE SET
                        organization_id=EXCLUDED.organization_id,stripe_customer_id=EXCLUDED.stripe_customer_id,
                        stripe_subscription_id=EXCLUDED.stripe_subscription_id,invoice_number=EXCLUDED.invoice_number,
                        status=EXCLUDED.status,currency=EXCLUDED.currency,amount_due=EXCLUDED.amount_due,
                        amount_paid=EXCLUDED.amount_paid,amount_remaining=EXCLUDED.amount_remaining,
                        period_start=EXCLUDED.period_start,period_end=EXCLUDED.period_end,due_at=EXCLUDED.due_at,
                        paid_at=EXCLUDED.paid_at,issued_at=EXCLUDED.issued_at,
                        hosted_invoice_url=EXCLUDED.hosted_invoice_url,invoice_pdf_url=EXCLUDED.invoice_pdf_url,updated_at=now()""",
                        stripe_invoice_id, org_id, invoice.get("customer"), stripe_subscription_id,
                        invoice.get("number"), invoice.get("status") or event_type.removeprefix("invoice."),
                        invoice.get("currency") or "eur", int(invoice.get("amount_due") if invoice.get("amount_due") is not None else (invoice.get("total") or 0)),
                        int(invoice.get("amount_paid") or 0), int(invoice.get("amount_remaining") or 0),
                        stripe_time(invoice.get("period_start")), stripe_time(invoice.get("period_end")),
                        stripe_time(invoice.get("due_date")), stripe_time(transitions.get("paid_at")),
                        stripe_time(invoice.get("created")), invoice.get("hosted_invoice_url"), invoice.get("invoice_pdf"))
            state = extract_subscription_state(event)
            if state:
                # Existing Stripe subscriptions keep their historical recurring amount.
                # Preserve their grandfathered seat/plan code when old metadata is replayed.
                if state.get("provider_subscription_id"):
                    prior_plan = await conn.fetchval("SELECT platform_lookup_plan_by_stripe_subscription($1)", state["provider_subscription_id"])
                    if prior_plan in ("LEGACY_ESSENTIAL_3", "LEGACY_SYNDICAT_10"):
                        state["plan_code"] = prior_plan
                org_id = state.get("organization_id")
                if not org_id and state.get("provider_subscription_id"):
                    org_id = await conn.fetchval("SELECT platform_lookup_org_by_stripe_subscription($1)", state["provider_subscription_id"])
                if org_id:
                    await conn.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_id))
                    await conn.execute("""INSERT INTO subscriptions(organization_id,provider,provider_customer_id,
                        provider_subscription_id,plan_code,status,current_period_end,cancel_at_period_end,updated_at)
                        VALUES($1::uuid,'stripe',$2,$3,COALESCE($4,'FOUNDING_FREE'),$5,
                        CASE WHEN $6::bigint IS NULL THEN NULL ELSE to_timestamp($6::bigint) END,COALESCE($7,false),now())
                        ON CONFLICT(organization_id) DO UPDATE SET provider='stripe',
                        provider_customer_id=COALESCE(EXCLUDED.provider_customer_id,subscriptions.provider_customer_id),
                        provider_subscription_id=COALESCE(EXCLUDED.provider_subscription_id,subscriptions.provider_subscription_id),
                        plan_code=CASE WHEN EXCLUDED.plan_code='FOUNDING_FREE' THEN subscriptions.plan_code ELSE EXCLUDED.plan_code END,
                        status=EXCLUDED.status,current_period_end=COALESCE(EXCLUDED.current_period_end,subscriptions.current_period_end),
                        cancel_at_period_end=EXCLUDED.cancel_at_period_end,updated_at=now()""",
                        org_id, state.get("provider_customer_id"), state.get("provider_subscription_id"),
                        state.get("plan_code"), state["status"], state.get("current_period_end"),
                        state.get("cancel_at_period_end", False))
                    if state.get("plan_code") in ("INDIVIDUAL_1", "SYNDICAT_10", "SYNDICAT_50", "LEGACY_ESSENTIAL_3", "LEGACY_SYNDICAT_10"):
                        await conn.execute("UPDATE organizations SET plan_code=$2 WHERE id=$1::uuid", org_id, state["plan_code"])
    return {"received": True, "duplicate": False}


@app.get("/api/v1/platform/free-email-access")
async def platform_list_free_email_access(platform=Depends(require_platform_admin)):
    if settings.private_instance_mode:
        raise HTTPException(404, "Les accès commerciaux individuels sont désactivés sur cette instance privée.")
    rows = await get_platform_admin_pool().fetch("""SELECT id,email_normalized,note,expires_at,created_at,revoked_at
        FROM platform_free_email_access ORDER BY created_at DESC LIMIT 500""")
    return [{"id": str(r["id"]), "email": r["email_normalized"], "note": r["note"],
             "expires_at": r["expires_at"], "created_at": r["created_at"],
             "active": r["revoked_at"] is None and (r["expires_at"] is None or r["expires_at"] > datetime.now(timezone.utc))}
            for r in rows]


@app.post("/api/v1/platform/free-email-access", status_code=201)
async def platform_add_free_email_access(payload: dict, platform=Depends(require_platform_admin)):
    if settings.private_instance_mode:
        raise HTTPException(404, "Les accès commerciaux individuels sont désactivés sur cette instance privée.")
    email = str(payload.get("email", "")).strip().lower() if isinstance(payload, dict) else ""
    note = str(payload.get("note", "")).strip()[:500] if isinstance(payload, dict) else ""
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Adresse électronique invalide.")
    expires_at = payload.get("expires_at") if isinstance(payload, dict) else None
    if expires_at:
        try:
            expires_at = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("expiration passée")
        except ValueError:
            raise HTTPException(422, "La date d'expiration doit être une date future valide.")
    async with get_platform_admin_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""INSERT INTO platform_free_email_access(email_normalized,note,granted_by,expires_at)
                VALUES($1,$2,$3::uuid,$4::timestamptz)
                ON CONFLICT(email_normalized) DO UPDATE SET note=EXCLUDED.note,granted_by=EXCLUDED.granted_by,
                  expires_at=EXCLUDED.expires_at,revoked_at=NULL,updated_at=now()
                RETURNING id,email_normalized,note,expires_at,created_at""", email, note, platform["user_id"], expires_at)
            await conn.execute("""INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
                VALUES($1::uuid,'FREE_EMAIL_ACCESS_GRANTED','free_email_access',$2::uuid,jsonb_build_object('email',$3))""",
                platform["user_id"], row["id"], email)
    return {"id": str(row["id"]), "email": row["email_normalized"], "note": row["note"],
            "expires_at": row["expires_at"], "created_at": row["created_at"], "active": True}


@app.delete("/api/v1/platform/free-email-access/{access_id}")
async def platform_revoke_free_email_access(access_id: str, platform=Depends(require_platform_admin)):
    if settings.private_instance_mode:
        raise HTTPException(404, "Les accès commerciaux individuels sont désactivés sur cette instance privée.")
    try:
        access_uuid = str(UUID(access_id))
    except ValueError:
        raise HTTPException(422, "Identifiant d'accès invalide.")
    async with get_platform_admin_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""UPDATE platform_free_email_access SET revoked_at=now(),updated_at=now()
                WHERE id=$1::uuid AND revoked_at IS NULL RETURNING id,email_normalized""", access_uuid)
            if not row:
                raise HTTPException(404, "Accès gratuit introuvable ou déjà révoqué.")
            await conn.execute("""INSERT INTO platform_audit_events(actor_user_id,event_type,target_type,target_id,metadata)
                VALUES($1::uuid,'FREE_EMAIL_ACCESS_REVOKED','free_email_access',$2::uuid,jsonb_build_object('email',$3))""",
                platform["user_id"], row["id"], row["email_normalized"])
    return {"id": str(row["id"]), "email": row["email_normalized"], "active": False}



@app.get("/api/v1/platform/founder-entitlements")
async def platform_list_founder_entitlements(platform=Depends(require_platform_admin)):
    rows = await get_platform_admin_pool().fetch(
        "SELECT * FROM platform_admin_list_founder_entitlements($1::uuid)",
        platform["user_id"],
    )
    return {"entitlements": [
        {"user_id": str(row["user_id"]), "note": row["note"],
         "granted_at": row["granted_at"], "revoked_at": row["revoked_at"],
         "active": row["revoked_at"] is None}
        for row in rows
    ]}


@app.post("/api/v1/platform/founder-entitlements", status_code=201)
async def platform_grant_founder_entitlement(payload: dict, platform=Depends(require_platform_admin)):
    user_id = str(payload.get("user_id", "")).strip() if isinstance(payload, dict) else ""
    note = str(payload.get("note", "")).strip()[:500] if isinstance(payload, dict) else ""
    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(422, "Identifiant de compte invalide.")
    if len(note) < 8:
        raise HTTPException(422, "Le motif d'attribution doit contenir au moins 8 caractères.")
    granted = await get_platform_admin_pool().fetchval(
        "SELECT platform_admin_grant_founder_entitlement($1::uuid,$2::uuid,$3)",
        platform["user_id"], target_user_id, note,
    )
    if not granted:
        raise HTTPException(404, "Compte actif authentifié introuvable. Aucun accès n'a été attribué.")
    return {"user_id": str(granted), "active": True}


@app.delete("/api/v1/platform/founder-entitlements/{user_id}")
async def platform_revoke_founder_entitlement(user_id: str, platform=Depends(require_platform_admin)):
    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(422, "Identifiant de compte invalide.")
    revoked = await get_platform_admin_pool().fetchval(
        "SELECT platform_admin_revoke_founder_entitlement($1::uuid,$2::uuid)",
        platform["user_id"], target_user_id,
    )
    if not revoked:
        raise HTTPException(404, "Aucun accès fondateur actif pour ce compte.")
    return {"user_id": str(target_user_id), "active": False}


@app.post("/api/v1/platform/organizations/{organization_id}/grant-free")
async def platform_grant_free(organization_id: str, payload: dict,
        admin: dict = Depends(require_platform_admin)):
    if settings.private_instance_mode:
        raise HTTPException(404, "Les accès commerciaux individuels sont désactivés sur cette instance privée.")
    try:
        org_id = str(UUID(organization_id))
    except ValueError:
        raise HTTPException(422, "Identifiant d'organisation invalide.")
    note = str(payload.get("reason", "")).strip()[:500] if isinstance(payload, dict) else ""
    if len(note) < 8:
        raise HTTPException(422, "Un motif d'attribution d'au moins 8 caractères est requis.")
    changed = await get_platform_admin_pool().fetchval(
        "SELECT platform_admin_grant_free_access($1::uuid,$2::uuid,$3)",
        admin["user_id"], org_id, note)
    if not changed:
        raise HTTPException(404, "Organisation introuvable.")
    return {"organization_id": org_id, "plan_code": "FOUNDING_FREE", "status": "FOUNDING_FREE"}


@app.get("/api/v1/chat/conversations")
async def list_chat_conversations(ctx: TenantContext = Depends(get_tenant_context)):
    rows = await ctx.conn.fetch("""SELECT c.id,c.title,c.created_at,c.updated_at,
        (SELECT count(*) FROM chat_messages m WHERE m.conversation_id=c.id
            AND m.organization_id=$1::uuid AND m.user_id=$2::uuid) AS message_count,
        (SELECT content FROM chat_messages m WHERE m.conversation_id=c.id
            AND m.organization_id=$1::uuid AND m.user_id=$2::uuid
            ORDER BY m.created_at DESC,m.id DESC LIMIT 1) AS last_message,
        (SELECT metadata->>'public_service' FROM chat_messages m WHERE m.conversation_id=c.id
            AND m.organization_id=$1::uuid AND m.user_id=$2::uuid AND m.role='user'
            ORDER BY m.created_at,m.id LIMIT 1) AS public_service
        FROM chat_conversations c
        WHERE c.organization_id=$1::uuid AND c.user_id=$2::uuid
        ORDER BY c.updated_at DESC LIMIT 100""", ctx.organization_id, ctx.user_id)
    return [{"id": str(r["id"]), "title": r["title"], "created_at": r["created_at"],
        "updated_at": r["updated_at"], "message_count": r["message_count"],
        "last_message": (r["last_message"] or "")[:180], "public_service": r["public_service"] or "FPT"} for r in rows]


@app.post("/api/v1/chat/conversations", status_code=201)
async def create_chat_conversation(payload: dict, ctx: TenantContext = Depends(get_tenant_context)):
    title = str(payload.get("title", "Nouvelle conversation")).strip()[:160] or "Nouvelle conversation"
    row = await ctx.conn.fetchrow("""INSERT INTO chat_conversations(organization_id,user_id,title)
        VALUES($1::uuid,$2::uuid,$3) RETURNING id,title,created_at,updated_at""",
        ctx.organization_id, ctx.user_id, title)
    return {"id": str(row["id"]), "title": row["title"], "created_at": row["created_at"], "updated_at": row["updated_at"]}


@app.get("/api/v1/chat/conversations/{conversation_id}/messages")
async def get_chat_messages(conversation_id: str, ctx: TenantContext = Depends(get_tenant_context)):
    try:
        conversation_uuid = str(UUID(conversation_id))
    except ValueError:
        raise HTTPException(422, "Identifiant de conversation invalide.")
    rows = await ctx.conn.fetch("""SELECT m.id,m.role,m.content,m.metadata,m.created_at
        FROM chat_messages m JOIN chat_conversations c ON c.id=m.conversation_id
        WHERE c.id=$1::uuid AND c.organization_id=$2::uuid AND c.user_id=$3::uuid
          AND m.organization_id=$2::uuid AND m.user_id=$3::uuid
        ORDER BY m.created_at,m.id""", conversation_uuid, ctx.organization_id, ctx.user_id)
    return [{"id": str(r["id"]), "role": r["role"], "content": r["content"],
        "metadata": r["metadata"], "created_at": r["created_at"]} for r in rows]


@app.delete("/api/v1/chat/conversations/{conversation_id}", status_code=204)
async def delete_chat_conversation(conversation_id: str, ctx: TenantContext = Depends(get_tenant_context)):
    try:
        conversation_uuid = str(UUID(conversation_id))
    except ValueError:
        raise HTTPException(422, "Identifiant de conversation invalide.")
    result = await ctx.conn.execute("""DELETE FROM chat_conversations
        WHERE id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
        conversation_uuid, ctx.organization_id, ctx.user_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Conversation introuvable.")
    return None


@app.post("/api/v1/chat/conversations/{conversation_id}/dossier", status_code=201)
async def build_legal_dossier(conversation_id: str, ctx: TenantContext = Depends(require_syndicate_subscription)):
    """Compile a faithful, editable working dossier from this user's conversation."""
    try:
        conversation_uuid = str(UUID(conversation_id))
    except ValueError:
        raise HTTPException(422, "Identifiant de conversation invalide.")
    conversation = await ctx.conn.fetchrow(
        """SELECT id,title FROM chat_conversations
           WHERE id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
        conversation_uuid, ctx.organization_id, ctx.user_id)
    if not conversation:
        raise HTTPException(404, "Conversation introuvable dans cet espace utilisateur.")
    existing = await ctx.conn.fetchrow(
        """SELECT id,content,created_at,updated_at FROM legal_dossiers
           WHERE conversation_id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
        conversation_uuid, ctx.organization_id, ctx.user_id)
    if existing:
        return {"id": str(existing["id"]), "content": decode_jsonb(existing["content"]),
                "created_at": existing["created_at"], "updated_at": existing["updated_at"], "created": False}
    messages = await ctx.conn.fetch("""SELECT id,role,content,metadata,created_at FROM chat_messages
        WHERE conversation_id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid
        ORDER BY created_at,id""", conversation_uuid, ctx.organization_id, ctx.user_id)
    if not messages:
        raise HTTPException(409, "Ajoutez au moins un échange avant de constituer un dossier.")
    content = build_dossier_content(dict(conversation), [dict(row) for row in messages])
    row = await ctx.conn.fetchrow("""INSERT INTO legal_dossiers(organization_id,conversation_id,user_id,content)
        VALUES($1::uuid,$2::uuid,$3::uuid,$4::jsonb)
        ON CONFLICT(conversation_id) DO NOTHING
        RETURNING id,content,created_at,updated_at""",
        ctx.organization_id, conversation_uuid, ctx.user_id, json.dumps(content, ensure_ascii=False, default=str))
    if not row:
        row = await ctx.conn.fetchrow("""SELECT id,content,created_at,updated_at FROM legal_dossiers
            WHERE conversation_id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
                                      conversation_uuid, ctx.organization_id, ctx.user_id)
        created = False
    else:
        created = True
    return {"id": str(row["id"]), "content": decode_jsonb(row["content"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"], "created": created}


@app.get("/api/v1/chat/conversations/{conversation_id}/dossier")
async def get_legal_dossier(conversation_id: str, ctx: TenantContext = Depends(require_syndicate_subscription)):
    try:
        conversation_uuid = str(UUID(conversation_id))
    except ValueError:
        raise HTTPException(422, "Identifiant de conversation invalide.")
    row = await ctx.conn.fetchrow("""SELECT id,content,created_at,updated_at FROM legal_dossiers
        WHERE conversation_id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
                                  conversation_uuid, ctx.organization_id, ctx.user_id)
    if not row:
        raise HTTPException(404, "Aucun dossier n'a encore été constitué pour cette conversation.")
    return {"id": str(row["id"]), "content": decode_jsonb(row["content"]), "created_at": row["created_at"], "updated_at": row["updated_at"]}


@app.put("/api/v1/chat/conversations/{conversation_id}/dossier")
async def update_legal_dossier(conversation_id: str, payload: dict, ctx: TenantContext = Depends(require_syndicate_subscription)):
    try:
        conversation_uuid = str(UUID(conversation_id))
        content = validate_dossier_content(payload.get("content"))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    existing = await ctx.conn.fetchrow("""SELECT id,content FROM legal_dossiers
        WHERE conversation_id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
        conversation_uuid, ctx.organization_id, ctx.user_id)
    if not existing:
        raise HTTPException(404, "Aucun dossier n'a encore été constitué pour cette conversation.")
    stored = decode_jsonb(existing["content"])
    restricted_statuses = {"VALIDE_HUMAINEMENT", "CLOTURE"}
    if (
        content.get("status") in restricted_statuses
        or stored.get("status") in restricted_statuses
    ) and ctx.role not in ("ORG_ADMIN", "LEGAL_EDITOR"):
        raise HTTPException(403, "La validation humaine, la réouverture et la modification d'un dossier validé ou clôturé sont réservées aux responsables habilités.")
    # Original exchanges, AI analyses, citations and verification metadata are immutable here.
    # Only the explicitly editable dossier fields may be changed by the user.
    editable = {"status", "title", "employer", "objective", "facts_summary", "chronology",
                "documents_and_evidence", "conclusion", "action_plan"}
    for key in editable:
        if key in content:
            stored[key] = content[key]
    row = await ctx.conn.fetchrow("""UPDATE legal_dossiers SET content=$2::jsonb,updated_at=now()
        WHERE conversation_id=$1::uuid AND organization_id=$3::uuid AND user_id=$4::uuid
        RETURNING id,content,created_at,updated_at""",
        conversation_uuid, json.dumps(stored, ensure_ascii=False, default=str),
        ctx.organization_id, ctx.user_id)
    return {"id": str(row["id"]), "content": decode_jsonb(row["content"]), "created_at": row["created_at"], "updated_at": row["updated_at"]}


async def _lock_conversation_for_chat_turn(
    conn, conversation_id: str, organization_id: str, user_id: str,
    requested_public_service: str,
) -> None:
    """Lock an owned conversation and prevent mixing legal branches in its history."""
    conversation = await conn.fetchrow(
        """SELECT id FROM chat_conversations
        WHERE id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid
        FOR UPDATE""",
        str(conversation_id), organization_id, user_id,
    )
    if not conversation:
        raise HTTPException(404, "Conversation introuvable dans cet espace utilisateur.")
    # Read the first message in a separate statement after acquiring the row
    # lock. Under READ COMMITTED this gets a fresh snapshot, including a first
    # message committed by a concurrent request that was waiting on the lock.
    first_message = await conn.fetchrow(
        """SELECT COALESCE(NULLIF(metadata->>'public_service',''),'FPT') AS public_service
        FROM chat_messages
        WHERE conversation_id=$1::uuid AND organization_id=$2::uuid
          AND user_id=$3::uuid AND role='user'
        ORDER BY created_at,id
        LIMIT 1""",
        str(conversation_id), organization_id, user_id,
    )
    requested = str(requested_public_service or "FPT").upper()
    # An empty pre-created conversation has no branch yet: its first turn
    # selects the branch. Legacy conversations with messages but no metadata
    # remain FPT by default for backward compatibility.
    stored_public_service = str(
        first_message["public_service"] or "FPT"
    ).upper() if first_message else requested
    if stored_public_service != requested:
        labels = {
            "FPT": "fonction publique territoriale",
            "FPE": "fonction publique de l'État",
            "FPH": "fonction publique hospitalière",
        }
        raise HTTPException(
            409,
            "Cette conversation est rattachée à la "
            f"{labels.get(stored_public_service, stored_public_service)}. "
            "Pour éviter de mélanger des règles juridiques de versants différents, "
            "démarrez une nouvelle conversation pour la "
            f"{labels.get(requested, requested)}.",
        )


@app.post("/api/v1/instances/{instance}/prepare")
async def prepare_social_instance(
    instance: str,
    payload: dict,
    ctx: TenantContext = Depends(require_syndicate_subscription),
):
    """Prepare a structured CST/CAP/CCP/FS checklist for active union subscribers."""
    objet = payload.get("objet")
    try:
        if legifrance.configured:
            await enforce_legal_connector_rate_limit(ctx)
        return await prepare_instance_with_legal_sources(
            instance,
            objet,
            legifrance_connector=legifrance,
            case_law_connector=AdministrativeCaseLawConnector(legifrance),
            effective_date=datetime.now(ZoneInfo("Europe/Paris")).date(),
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/v1/chat/ask",response_model=AskResponse)
async def ask(payload: AskRequest,ctx: TenantContext=Depends(get_tenant_identity)):
    pool = get_pool()
    # Persist and rate-limit the incoming message in one short tenant transaction.
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _set_tenant_rls_context(conn, ctx)
            rate = await consume_chat_request(
                conn, ctx.organization_id, ctx.user_id, settings.chat_rate_limit_per_minute
            )
            if not rate.allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Limite technique de requêtes atteinte. Réessayez dans quelques instants."},
                    headers={"Retry-After": str(rate.retry_after_seconds)},
                )

            subscription = await conn.fetchrow(
                "SELECT plan_code,status FROM subscriptions WHERE organization_id=$1::uuid",
                ctx.organization_id,
            )
            founder = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM platform_founder_entitlements "
                "WHERE user_id=$1::uuid AND revoked_at IS NULL)",
                ctx.user_id,
            )
            entitlements = resolve_entitlements(
                subscription["plan_code"] if subscription else None,
                subscription["status"] if subscription else None,
                founder=bool(founder),
            )
            if entitlements.daily_question_limit is not None:
                daily = await consume_daily_chat_question(
                    conn, ctx.user_id, entitlements.daily_question_limit
                )
                if not daily.allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Vous avez atteint la limite de 5 questions aujourd'hui. Votre quota sera réinitialisé à minuit (heure de Paris)."},
                    )

            conversation_id = payload.conversation_id
            if conversation_id is None:
                row = await conn.fetchrow("""INSERT INTO chat_conversations(organization_id,user_id,title)
                    VALUES($1::uuid,$2::uuid,$3) RETURNING id""", ctx.organization_id, ctx.user_id,
                    payload.question[:157] + ("…" if len(payload.question) > 157 else ""))
                conversation_id = row["id"]
            else:
                await _lock_conversation_for_chat_turn(
                    conn, str(conversation_id), ctx.organization_id, ctx.user_id,
                    payload.public_service,
                )
            current_message_id = await conn.fetchval("""INSERT INTO chat_messages(organization_id,conversation_id,user_id,role,content,metadata)
                VALUES($1::uuid,$2::uuid,$3::uuid,'user',$4,$5::jsonb) RETURNING id""", ctx.organization_id,
                str(conversation_id), ctx.user_id, payload.question,
                json.dumps({"employer": payload.employer, "public_service": payload.public_service,
                    "facts_date": payload.facts_date, "facts_start_date": payload.facts_start_date,
                    "facts_end_date": payload.facts_end_date, "situation_ongoing": payload.situation_ongoing,
                    "confirm_local_document_ai_transfer": payload.confirm_local_document_ai_transfer}, ensure_ascii=False))
            history_rows = await conn.fetch("""SELECT role,content,metadata FROM chat_messages
                WHERE conversation_id=$1::uuid AND organization_id=$4::uuid AND user_id=$5::uuid
                  AND id<>$2::uuid AND role IN ('user','assistant')
                ORDER BY created_at DESC,id DESC LIMIT $3""", str(conversation_id), current_message_id,
                CONVERSATION_HISTORY_MESSAGE_LIMIT, ctx.organization_id, ctx.user_id)
            history = _ai_safe_conversation_history(history_rows)

    # No connection or transaction is held while the orchestrator plans or calls providers.
    scoped_reader = _TenantScopedReadConnection(pool, ctx)
    try:
        result = await orchestrator.ask(
            payload, ctx.organization_id, conn=scoped_reader, conversation_history=history,
            allow_local_documents=(
                payload.confirm_local_document_ai_transfer
                and settings.ai_local_documents_in_chat_enabled
            ),
            personal_user_id=ctx.user_id,
        )
    except Exception:
        failure = _chat_orchestration_failure(conversation_id)
        logger.exception(
            "Chat orchestration failed; a controlled response will be persisted (request_id=%s)",
            failure.request_id,
        )
        result = failure
    result.conversation_id = conversation_id

    # Persist the generated answer and usage in a second short transaction.
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _set_tenant_rls_context(conn, ctx)
            usage_events = list(result.ai_usage_events or [])
            if not usage_events and result.ai_usage is not None:
                usage_events = [result.ai_usage]
            for usage_event in usage_events:
                await record_ai_usage_event(
                    conn, ctx.organization_id, ctx.user_id, result.request_id, usage_event
                )
            await conn.execute("""INSERT INTO chat_messages(organization_id,conversation_id,user_id,role,content,metadata)
                VALUES($1::uuid,$2::uuid,$3::uuid,'assistant',$4,$5::jsonb)""", ctx.organization_id,
                str(conversation_id), ctx.user_id, result.answer,
                json.dumps({"verification_status": result.verification_status,
                    "contains_local_documents": any(
                        source.get("source_type") in {"LOCAL_DOCUMENT", "LOCAL_COLLECTIVITY_DOCUMENT", "PERSONAL_DOCUMENT"}
                        for source in result.sources
                    ),
                    "sources": [{k: (str(v)[:2500] if isinstance(v, str) else v) for k, v in source.items()
                        if k in CHAT_SOURCE_METADATA_FIELDS}
                        for source in result.sources[:30]],
                    "missing_information": result.missing_information, "disclaimer": result.disclaimer,
                    "clarification_question": result.clarification_question, "public_service": payload.public_service},
                    ensure_ascii=False, default=str))
            await conn.execute(
                """UPDATE chat_conversations SET updated_at=now()
                WHERE id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid""",
                str(conversation_id), ctx.organization_id, ctx.user_id,
            )
    return result

@app.get("/api/v1/integrations/legifrance/status", dependencies=[Depends(require_syndicate_subscription)])
async def legifrance_status(ctx: TenantContext = Depends(get_tenant_context)):
    return {"configured": legifrance.configured, "environment": legifrance.environment,
            "code_name": settings.legifrance_code_name,
            "status": "CONFIGURED_NOT_TESTED" if legifrance.configured else "NOT_CONFIGURED",
            "credentials_exposed": False}

@app.post("/api/v1/integrations/legifrance/check", dependencies=[Depends(require_syndicate_subscription)])
async def legifrance_check(ctx: TenantContext = Depends(get_tenant_context_for_chat)):
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    await enforce_legal_connector_rate_limit(ctx)
    try:
        await legifrance.ping()
    except LegifranceUnavailable:
        raise HTTPException(503, "Connexion PISTE impossible. Vérifier les identifiants, les consentements et les quotas.")
    return {"status": "CONNECTED", "environment": legifrance.environment,
            "message": "Le point de contrôle Légifrance répond. Cela ne valide pas encore une recherche juridique complète."}

@app.get("/api/v1/legal/legifrance/search", dependencies=[Depends(require_syndicate_subscription)])
async def search_legifrance(q: str, effective_date: date | None = None,
        ctx: TenantContext = Depends(get_tenant_context_for_chat)):
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "La recherche Légifrance doit contenir entre 2 et 500 caractères.")
    await enforce_legal_connector_rate_limit(ctx)
    try:
        results = await legifrance.search_code_articles(q, effective_date or date.today())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except LegifranceUnavailable:
        raise HTTPException(503, "Recherche Légifrance indisponible. Vérifier les identifiants, consentements et quotas.")
    return {"requested_date": (effective_date or date.today()).isoformat(),
            "results_count": len(results), "results": results,
            "warning": "Résultats API à vérifier ; l'absence de résultat ne prouve pas l'absence de règle."}

@app.get("/api/v1/legal/jurisprudence/administrative/search", dependencies=[Depends(require_syndicate_subscription)])
async def search_administrative_case_law(q: str, effective_date: date | None = None,
        ctx: TenantContext = Depends(get_tenant_context)):
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "La recherche de jurisprudence doit contenir entre 2 et 500 caractères.")
    await enforce_legal_connector_rate_limit(ctx)
    requested_date = effective_date or date.today()
    try:
        results = await case_law_connector.search(q, requested_date)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except LegifranceUnavailable:
        raise HTTPException(503, "Recherche de jurisprudence administrative indisponible.")
    return {
        "requested_date": requested_date.isoformat(),
        "results_count": len(results),
        "results": results,
        "verification_status": "METADONNEES_OFFICIELLES_NON_INTEGRALES" if results else "NON_VERIFIE",
        "warning": "La recherche retourne des métadonnées et extraits éventuels. Utiliser la route de consultation pour récupérer et contrôler le texte intégral. L'absence de résultat ne prouve pas l'absence de jurisprudence.",
    }


@app.get("/api/v1/legal/jurisprudence/administrative/{decision_id}", dependencies=[Depends(require_syndicate_subscription)])
async def consult_administrative_case_law(decision_id: str,
        ctx: TenantContext = Depends(get_tenant_context)):
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    if not isinstance(decision_id, str) or not DECISION_ID_RE.fullmatch(decision_id):
        raise HTTPException(422, "Identifiant de décision administrative invalide.")
    await enforce_legal_connector_rate_limit(ctx)
    try:
        result = await case_law_connector.consult(decision_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except LegifranceUnavailable:
        raise HTTPException(503, "Consultation intégrale indisponible ou décision non vérifiable.")
    return {"verification_status": "TEXTE_INTEGRAL_OFFICIEL_ID_VERIFIE", "decision": result,
            "warning": "La récupération du texte intégral et la correspondance de l'identifiant sont contrôlées. Cela ne constitue pas une analyse de la portée juridique, ni une vérification exhaustive des revirements ou de l'état actuel du droit."}


@app.get("/api/v1/legal/knowledge/search", dependencies=[Depends(require_syndicate_subscription)])
async def search_permanent_legal_knowledge(q: str, effective_date: date | None = None,
        limit: int = 12, ctx: TenantContext = Depends(get_tenant_context)):
    requested_date = effective_date or date.today()
    try:
        results = await search_legal_corpus(ctx.conn, q, requested_date, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    public_results = [{k: v for k, v in item.items() if k != "full_text"} for item in results]
    return {"requested_date": requested_date.isoformat(), "results_count": len(public_results),
        "results": public_results,
        "warning": "Le statut temporel est calculé à partir des dates stockées. Une date manquante ou un statut inconnu ne permet pas de conclure à l'applicabilité juridique.",
        "corpus_scope": ["LEGI/LODA", "CETAT", "CIRCULAIRES"]}


@app.post("/api/v1/legal/compliance/review/{document_id}")
async def review_local_rule_compliance(document_id: str, q: str,
        effective_date: date | None = None, confirm_local_document_ai_transfer: bool = False,
        ctx: TenantContext = Depends(require_syndicate_subscription)):
    """Prepare a sourced comparison of one tenant-local document with national sources.

    This endpoint flags review needs; it never declares a local act illegal.
    """
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(400, "Identifiant de document invalide.")
    query = q.strip()
    if len(query) < 8 or len(query) > 500:
        raise HTTPException(422, "La question de contrôle doit contenir entre 8 et 500 caractères.")
    async with ctx.conn.transaction():
        rate = await consume_chat_request(
            ctx.conn, ctx.organization_id, ctx.user_id, settings.chat_rate_limit_per_minute
        )
    if not rate.allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Limite de requêtes atteinte. Réessayez dans quelques instants."},
            headers={"Retry-After": str(rate.retry_after_seconds)},
        )
    requested_date = effective_date or date.today()
    local = await ctx.conn.fetchrow("""
      SELECT d.id,d.title,d.document_type,d.official_number,d.official_url,d.validation_status,
        d.validation_note,d.effective_from,d.effective_to,d.adopted_at,d.published_at,
        d.scan_status,c.id collectivity_id,c.name collectivity_name,dt.extracted_text,dt.extraction_status,
        dt.version_number,dt.sha256
      FROM documents d
      JOIN collectivities c ON c.id=d.collectivity_id AND c.organization_id=d.organization_id
      LEFT JOIN LATERAL (SELECT x.extracted_text,x.extraction_status,x.version_number,x.sha256
        FROM document_text x WHERE x.organization_id=d.organization_id AND x.document_id=d.id
        ORDER BY x.version_number DESC LIMIT 1) dt ON true
      WHERE d.id=$1::uuid AND d.organization_id=$2::uuid
    """, document_id, ctx.organization_id)
    if not local:
        raise HTTPException(404, "Document local introuvable dans cet espace.")
    if local["scan_status"] != "CLEAN":
        raise HTTPException(409, "Le document doit avoir un contrôle antivirus concluant avant son analyse.")
    if not local["extracted_text"] or local["extraction_status"] != "EXTRACTED":
        raise HTTPException(409, "Aucun texte exploitable n'est disponible. Réindexer ou vérifier le document avant le contrôle.")

    local_source = {
        "source_type": "LOCAL_COLLECTIVITY_DOCUMENT", "source_id": str(local["id"]),
        "title": local["title"], "document_kind": "LOCAL_DOCUMENT",
        "local_document_type": local["document_type"], "official_number": local["official_number"],
        "official_url": local["official_url"], "validation_status": local["validation_status"],
        "valid_from": local["effective_from"], "valid_to": local["effective_to"],
        "collectivity": local["collectivity_name"], "content_kind": "FULL_TEXT",
        "excerpt": str(local["extracted_text"])[:9000], "text": str(local["extracted_text"])[:9000],
        "source_status": "TENANT_DOCUMENT_EXTRACTED", "temporal_status": "UNKNOWN",
    }
    try:
        national = await search_legal_corpus(ctx.conn, query, requested_date, limit=15)
    except (ValueError, OSError) as exc:
        raise HTTPException(503, "Le corpus national n'a pas pu être interrogé.") from exc
    national_sources = [{**item, "source_url": item.get("official_url")} for item in national
        if item.get("content_kind") == "FULL_TEXT" and isinstance(item.get("citation_integrity"), dict) and item["citation_integrity"].get("valid") is True]
    sources = [local_source] + national_sources
    assurance = assess_source_set(sources)
    local_assurance = assurance["sources"][0].get("legal_assurance", {})
    national_assurance = [item.get("legal_assurance", {}) for item in assurance["sources"][1:]]
    assurance_summary = {key: value for key, value in assurance.items() if key != "sources"}
    usable_national = [item for item in national_sources if item.get("temporal_status") in {
        "IN_FORCE_ON_REQUESTED_DATE", "DECISION_AVAILABLE_BY_REQUESTED_DATE"}]
    ai_review = None
    if (usable_national and settings.ai_api_key and settings.ai_model
            and settings.ai_local_document_review_enabled and confirm_local_document_ai_transfer):
        review_question = (
            "CONTROLE DE COHERENCE D'UNE REGLE LOCALE. Question de contrôle : " + query +
            "\nCompare uniquement le document local fourni avec les textes nationaux intégraux et temporellement exploitables. "
            "Signale les points de compatibilité apparente, les différences de champ ou de date et les éléments impossibles à trancher. "
            "Ne déclare jamais le document illégal. Ne suppose pas qu'une absence de résultat prouve la conformité. "
            "Toute affirmation juridique doit être rattachée aux références exactes présentes dans les sources."
        )
        request_id = str(uuid4())
        try:
            candidate_result = await analyze_question(
                question=review_question, employer="NATIONAL", facts_date=requested_date.isoformat(),
                sources=[local_source] + usable_national, conversation_history=None,
                allow_local_documents=True)
            candidate = extract_analysis_content(candidate_result)
            usage = None
            if isinstance(candidate_result, AIAnalysisResult):
                usage = {
                    "provider": "openai_compatible", "model": candidate_result.model,
                    "prompt_tokens": candidate_result.prompt_tokens,
                    "completion_tokens": candidate_result.completion_tokens,
                    "total_tokens": candidate_result.total_tokens, "outcome": "ANSWERED",
                }
            allowed_refs = {item.get("article") for item in usable_national if item.get("article")}
            allowed_authorities = {value for item in usable_national for value in
                (item.get("official_number"), item.get("source_id"), item.get("case_number")) if value}
            if candidate and answer_references_are_grounded(candidate, allowed_refs, allowed_authorities):
                ai_review = candidate
            elif usage is not None:
                usage["outcome"] = "REJECTED_UNGROUNDED"
            if usage is not None:
                async with ctx.conn.transaction():
                    await record_ai_usage_event(ctx.conn, ctx.organization_id, ctx.user_id, request_id, usage)
        except AIProviderUnavailable:
            async with ctx.conn.transaction():
                await record_ai_usage_event(ctx.conn, ctx.organization_id, ctx.user_id, request_id, {
                    "provider": "openai_compatible", "model": settings.ai_model[:160],
                    "prompt_tokens": None, "completion_tokens": None, "total_tokens": None,
                    "outcome": "PROVIDER_ERROR",
                })
        except Exception:
            ai_review = None
    async with ctx.conn.transaction():
        await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
          VALUES($1::uuid,$2::uuid,'LOCAL_RULE_COMPLIANCE_REVIEWED','document',$3::uuid,$4::jsonb)""",
          ctx.organization_id, ctx.user_id, document_id,
          json.dumps({"query": query, "effective_date": requested_date.isoformat(),
            "national_sources": len(national_sources),
            "local_document_ai_transfer_confirmed": confirm_local_document_ai_transfer,
            "ai_review_enabled": ai_review is not None}, ensure_ascii=False))
    return {
      "status": "COMPARISON_REQUIRED" if national_sources else "NATIONAL_SOURCES_NOT_FOUND",
      "requested_date": requested_date.isoformat(),
      "collectivity": local["collectivity_name"],
      "source_assessment": assurance_summary,
      "local_document": {"id": str(local["id"]), "title": local["title"], "document_type": local["document_type"],
        "validation_status": local["validation_status"], "effective_from": local["effective_from"],
        "effective_to": local["effective_to"], "extraction_status": local["extraction_status"],
        "excerpt_length": len(local["extracted_text"]), "legal_assurance": local_assurance},
      "national_sources": [{**{k: v for k, v in item.items() if k not in {"full_text", "text"}},
        "legal_assurance": national_assurance[i]} for i, item in enumerate(national_sources)],
      "preliminary_review": ai_review,
      "conclusion": "Aucune déclaration automatique de légalité ou d'illégalité. La comparaison est un signalement de points à examiner ; une validation humaine contextualisée est indispensable.",
      "limitations": ["Une recherche ciblée n'est pas exhaustive.",
        "La pertinence et l'applicabilité de chaque texte doivent être contrôlées.",
        "Le contrôle ne remplace pas l'examen des délibérations, annexes, accords, jurisprudences et circonstances locales.",
        "L'absence de source retrouvée ne prouve ni la conformité ni l'absence de règle applicable."],
    }


@app.get("/api/v1/platform/legal-corpus/freshness")
async def legal_corpus_freshness(admin=Depends(require_platform_admin)):
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        latest = await conn.fetch("""SELECT source_type,run_mode,status,records_seen,records_imported,
            records_rejected,started_at,finished_at,error_summary
          FROM legal_ingestion_runs ORDER BY started_at DESC LIMIT 30""")
        counts = await conn.fetch("""SELECT source_type,status,source_status,count(*)::int document_count,
            max(last_seen_at) last_seen_at FROM legal_documents GROUP BY source_type,status,source_status""")
    return {"runs": [dict(row) for row in latest], "corpus_inventory": [dict(row) for row in counts],
        "warning": "Indicateurs de dernière ingestion connue uniquement. Ils ne prouvent ni l'exhaustivité du corpus ni une veille continue ; les tâches planifiées doivent être configurées et surveillées par l'exploitant."}


@app.post("/api/v1/platform/legal-corpus/ingest/regulatory")
async def ingest_regulatory_corpus(q: str, effective_date: date | None = None,
        limit: int = 10, admin=Depends(require_platform_admin)):
    if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "La recherche réglementaire doit contenir entre 2 et 500 caractères.")
    if not 1 <= limit <= 20:
        raise HTTPException(422, "La limite d'import réglementaire doit être comprise entre 1 et 20.")
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    requested_date = effective_date or date.today()
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("""INSERT INTO legal_ingestion_runs(source_type,run_mode,status,query_text)
            VALUES('LEGIFRANCE_LODA','SEARCH_IMPORT','RUNNING',$1) RETURNING id""", q[:500])
        imported = rejected = 0
        try:
            items = await legifrance.search_regulatory_texts(q, requested_date, limit)
            async with conn.transaction():
                for item in items:
                    try:
                        await upsert_legal_document(conn, item)
                        imported += 1
                    except (ValueError, TypeError):
                        rejected += 1
            status = "SUCCEEDED" if imported and not rejected else ("PARTIAL" if imported or rejected else "PARTIAL")
            await conn.execute("UPDATE legal_ingestion_runs SET status=$2,records_seen=$3,records_imported=$4,records_rejected=$5,finished_at=now() WHERE id=$1",
                run["id"], status, len(items), imported, rejected)
            return {"run_id": str(run["id"]), "status": status, "records_seen": len(items),
                "records_imported": imported, "records_rejected": rejected,
                "requested_date": requested_date.isoformat(),
                "warning": "Import des textes réglementaires retrouvés par l'API Légifrance. L'exhaustivité du fonds n'est pas garantie par une recherche ciblée."}
        except (LegifranceUnavailable, ValueError) as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], str(exc)[:1000])
            raise HTTPException(503 if isinstance(exc, LegifranceUnavailable) else 422, str(exc))
        except Exception as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], type(exc).__name__)
            raise


@app.post("/api/v1/platform/legal-corpus/ingest/administrative-case-law")
async def ingest_administrative_case_law(q: str, effective_date: date | None = None,
        limit: int = 10, admin=Depends(require_platform_admin)):
    if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "La recherche de jurisprudence doit contenir entre 2 et 500 caractères.")
    if not 1 <= limit <= 20:
        raise HTTPException(422, "La limite d'import de jurisprudence doit être comprise entre 1 et 20.")
    if not settings.legifrance_cetat_fulltext_enabled:
        raise HTTPException(503, "L'import du texte intégral CETAT est désactivé jusqu'à validation du contrat de consultation sur PISTE.")
    if not legifrance.configured:
        raise HTTPException(503, "Identifiants PISTE non configurés.")
    requested_date = effective_date or date.today()
    if not 1 <= limit <= 20:
        raise HTTPException(422, "La limite doit être comprise entre 1 et 20.")
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("""INSERT INTO legal_ingestion_runs(source_type,run_mode,status,query_text)
            VALUES('LEGIFRANCE_CETAT','SEARCH_IMPORT','RUNNING',$1) RETURNING id""", q[:500])
        imported = rejected = 0
        try:
            hits = await case_law_connector.search(q, requested_date)
            async with conn.transaction():
                for hit in hits[:limit]:
                    try:
                        decision = await case_law_connector.consult(hit["source_id"])
                        decision_date = None
                        try:
                            decision_date = date.fromisoformat((decision.get("decision_date") or "")[:10])
                        except ValueError:
                            pass
                        await upsert_legal_document(conn, {
                            "source_type": "LEGIFRANCE_CETAT", "source_id": decision["source_id"],
                            "title": decision.get("title") or hit.get("title") or decision["source_id"],
                            "document_kind": "ADMIN_CASELAW", "official_number": decision.get("case_number"),
                            "jurisdiction": decision.get("jurisdiction"), "publisher": "Juridictions administratives",
                            "official_url": decision.get("source_url"), "signature_date": decision_date,
                            "status": "UNKNOWN", "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
                            "valid_from": None, "valid_to": None, "version_status": "UNKNOWN",
                            "version_key": "decision-" + decision["source_id"],
                            "source_version_id": decision["source_id"], "full_text": decision.get("text", ""),
                            "raw_metadata": {"case_number": decision.get("case_number"),
                                "decision_date": decision.get("decision_date"), "jurisdiction": decision.get("jurisdiction")},
                            "raw_version_payload": {"requested_date": requested_date.isoformat(),
                                "api_method": "/consult/juri"}})
                        imported += 1
                    except (LegifranceUnavailable, ValueError, KeyError, TypeError):
                        rejected += 1
            status = "SUCCEEDED" if imported and not rejected else "PARTIAL"
            await conn.execute("UPDATE legal_ingestion_runs SET status=$2,records_seen=$3,records_imported=$4,records_rejected=$5,finished_at=now() WHERE id=$1",
                run["id"], status, len(hits), imported, rejected)
            return {"run_id": str(run["id"]), "status": status, "records_seen": len(hits),
                "records_imported": imported, "records_rejected": rejected,
                "warning": "Seules les décisions dont le texte intégral et l'identifiant ont été contrôlés sont indexées comme texte intégral. Les résultats de recherche non consultables ne sont pas présentés comme décisions vérifiées."}
        except (LegifranceUnavailable, ValueError) as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], str(exc)[:1000])
            raise HTTPException(503 if isinstance(exc, LegifranceUnavailable) else 422, str(exc))
        except Exception as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], type(exc).__name__)
            raise


@app.post("/api/v1/platform/legal-corpus/ingest/circulaires-xml")
async def ingest_circulaires_open_data(file: UploadFile = File(...), admin=Depends(require_platform_admin)):
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(422, "Fournir un fichier XML CIRCULAIRES DILA.")
    raw = await file.read(50 * 1024 * 1024 + 1)
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "Fichier XML limité à 50 Mo.")
    try:
        items = parse_circulaires_xml(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("""INSERT INTO legal_ingestion_runs(source_type,run_mode,status,query_text)
            VALUES('DILA_CIRCULAIRES','BULK_XML_IMPORT','RUNNING',$1) RETURNING id""", file.filename[:250])
        imported = rejected = 0
        try:
            async with conn.transaction():
                for item in items:
                    try:
                        await upsert_legal_document(conn, item)
                        imported += 1
                    except (ValueError, TypeError):
                        rejected += 1
            status = "SUCCEEDED" if imported and not rejected else "PARTIAL"
            await conn.execute("UPDATE legal_ingestion_runs SET status=$2,records_seen=$3,records_imported=$4,records_rejected=$5,finished_at=now() WHERE id=$1",
                run["id"], status, len(items), imported, rejected)
        except Exception as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], type(exc).__name__)
            raise
    return {"run_id": str(run["id"]), "status": status, "records_seen": len(items),
        "records_imported": imported, "records_rejected": rejected,
        "warning": "Le flux CIRCULAIRES peut ne fournir que des métadonnées. Les circulaires sans texte intégral restent explicitement identifiées comme telles."}


@app.post("/api/v1/platform/legal-corpus/ingest/administrative-open-data-archive")
async def ingest_administrative_open_data_archive(
    court: str, year: int, month: int, admin=Depends(require_platform_admin),
):
    """Download one monthly archive from the fixed official open-data host."""
    try:
        archive_url = administrative_open_data_archive_url(court, year, month)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    max_archive_bytes = 100 * 1024 * 1024
    timeout = httpx.Timeout(60.0, connect=10.0)
    chunks: list[bytes] = []
    total_bytes = 0
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            async with client.stream("GET", archive_url) as response:
                if response.status_code == 404:
                    raise HTTPException(404, "Cette archive mensuelle n'est pas publiée sur la plateforme officielle.")
                if response.status_code != 200:
                    raise HTTPException(502, f"La plateforme officielle a répondu HTTP {response.status_code}.")
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        if int(content_length) > max_archive_bytes:
                            raise HTTPException(413, "Archive ZIP limitée à 100 Mo.")
                    except ValueError:
                        pass
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_archive_bytes:
                        raise HTTPException(413, "Archive ZIP limitée à 100 Mo.")
                    chunks.append(chunk)
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Le téléchargement de l'archive officielle a dépassé le délai autorisé.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "La plateforme officielle de données ouvertes est momentanément inaccessible.") from exc

    raw = b"".join(chunks)
    if not raw.startswith(b"PK\x03\x04"):
        raise HTTPException(502, "La ressource téléchargée n'est pas une archive ZIP reconnue.")
    filename = archive_url.rsplit("/", 1)[-1]
    uploaded = UploadFile(filename=filename, file=BytesIO(raw))
    return await ingest_administrative_open_data_zip(uploaded, admin=admin)


@app.post("/api/v1/platform/legal-corpus/ingest/administrative-open-data-zip")
async def ingest_administrative_open_data_zip(file: UploadFile = File(...), admin=Depends(require_platform_admin)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(422, "Fournir une archive ZIP officielle de la justice administrative.")
    raw = await file.read(100 * 1024 * 1024 + 1)
    if len(raw) > 100 * 1024 * 1024:
        raise HTTPException(413, "Archive ZIP limitée à 100 Mo.")
    try:
        items = await asyncio.to_thread(parse_administrative_open_data_zip, raw, file.filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not items:
        raise HTTPException(422, "Aucune décision intégrale pertinente pour la fonction publique territoriale n'a été trouvée dans cette archive.")
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow("""INSERT INTO legal_ingestion_runs(source_type,source_key,run_mode,status,query_text)
            VALUES('OTHER_OFFICIAL','JUSTICE_ADMIN_OPEN_DATA','BULK_XML_IMPORT','RUNNING',$1) RETURNING id""", file.filename[:250])
        imported = rejected = 0
        try:
            async with conn.transaction():
                for item in items:
                    try:
                        await upsert_legal_document(conn, item)
                        imported += 1
                    except (ValueError, TypeError):
                        rejected += 1
            status = "SUCCEEDED" if imported and not rejected else "PARTIAL"
            await conn.execute("UPDATE legal_ingestion_runs SET status=$2,records_seen=$3,records_imported=$4,records_rejected=$5,finished_at=now() WHERE id=$1",
                run["id"], status, len(items), imported, rejected)
            return {"run_id": str(run["id"]), "status": status, "records_seen": len(items),
                "records_imported": imported, "records_rejected": rejected,
                "warning": "Import des seules décisions XML officielles intégrales dont le lien avec la fonction publique territoriale est détecté. La sélection automatique peut manquer des décisions dont les faits sont insuffisamment explicites ; l'exhaustivité n'est pas garantie."}
        except Exception as exc:
            await conn.execute("UPDATE legal_ingestion_runs SET status='FAILED',error_summary=$2,finished_at=now() WHERE id=$1",
                run["id"], type(exc).__name__)
            raise


@app.get("/api/v1/platform/legal-corpus/ingestion-runs")
async def list_legal_ingestion_runs(limit: int = 30, admin=Depends(require_platform_admin)):
    if not 1 <= limit <= 100:
        raise HTTPException(422, "La limite doit être comprise entre 1 et 100.")
    pool = get_corpus_ingest_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id,source_type,run_mode,status,query_text,records_seen,records_imported,records_rejected,error_summary,started_at,finished_at FROM legal_ingestion_runs ORDER BY started_at DESC LIMIT $1", limit)
    return {"runs": [{**dict(row), "id": str(row["id"])} for row in rows]}


@app.get("/api/v1/legal/cgfp/source", dependencies=[Depends(require_syndicate_subscription)])
async def cgfp_source(ctx: TenantContext = Depends(get_tenant_context)):
    try:
        result = search_cgfp("L1", limit=1)
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(503, "Index documentaire du CGFP indisponible.")
    return {"source": result["source"], "verification_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
            "warning": "Métadonnées du snapshot local. Vérification officielle Légifrance non effectuée."}

@app.get("/api/v1/legal/cgfp/articles/{article_ref}", dependencies=[Depends(require_syndicate_subscription)])
async def get_national_cgfp_article(article_ref: str, ctx: TenantContext = Depends(get_tenant_context)):
    try:
        article = get_cgfp_article(article_ref)
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(503, "Index documentaire du CGFP indisponible.")
    if article is None:
        raise HTTPException(404, "Référence d'article invalide ou absente de l'index CGFP.")
    return {"verification_status": "PARTIELLEMENT_VERIFIE", "article": article,
            "warning": "Texte extrait du snapshot PDF ; contrôler la rédaction officielle et la version applicable à la date des faits sur Légifrance."}

@app.get("/api/v1/legal/cgfp/search", dependencies=[Depends(require_syndicate_subscription)])
async def search_national_cgfp(q: str, limit: int = 8, ctx: TenantContext = Depends(get_tenant_context)):
    if len(q.strip()) < 2 or len(q) > 500:
        raise HTTPException(422, "La recherche doit contenir entre 2 et 500 caractères.")
    if not 1 <= limit <= 20:
        raise HTTPException(422, "La limite doit être comprise entre 1 et 20.")
    try:
        result = search_cgfp(q, limit=limit)
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(503, "Index documentaire du CGFP indisponible.")
    return {"verification_status": "PARTIELLEMENT_VERIFIE" if result["results"] else "NON_VERIFIE",
            "source": result["source"], "results": result["results"],
            "warning": "Résultats issus d’un snapshot documentaire ; vérifier la version applicable et les textes officiels sur Légifrance."}

@app.get("/api/v1/organizations/me/members", dependencies=[Depends(require_syndicate_subscription)])
async def members(ctx: TenantContext=Depends(require_org_admin)):
    rows=await ctx.conn.fetch("""
      SELECT u.id,u.email,u.display_name,m.role,m.status,m.created_at
      FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.organization_id=$1::uuid ORDER BY m.created_at
    """,ctx.organization_id)
    return [{"id":str(r["id"]),"email":r["email"],"display_name":r["display_name"],
      "role":r["role"],"status":r["status"],"created_at":r["created_at"]} for r in rows]

@app.get("/api/v1/collectivities", dependencies=[Depends(require_syndicate_subscription)])
async def list_collectivities(ctx: TenantContext = Depends(get_tenant_context)):
    rows = await ctx.conn.fetch(
        "SELECT id,code,name,created_at FROM collectivities WHERE organization_id=$1::uuid ORDER BY name",
        ctx.organization_id)
    return [{"id":str(r["id"]),"code":r["code"],"name":r["name"],"created_at":r["created_at"]} for r in rows]

@app.post("/api/v1/collectivities", status_code=201, dependencies=[Depends(require_syndicate_subscription)])
async def create_collectivity(payload: CollectivityCreate, ctx: TenantContext = Depends(require_org_admin)):
    try:
        row = await ctx.conn.fetchrow(
            "INSERT INTO collectivities(organization_id,code,name) VALUES($1::uuid,$2,$3) RETURNING id,code,name,created_at",
            ctx.organization_id, payload.code, payload.name)
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(409, "Ce code de collectivité existe déjà dans cet espace.")
        raise
    await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
      VALUES($1::uuid,$2::uuid,'COLLECTIVITY_CREATED','collectivity',$3::uuid)""",ctx.organization_id,ctx.user_id,row["id"])
    return {"id":str(row["id"]),"code":row["code"],"name":row["name"],"created_at":row["created_at"]}

@app.get("/api/v1/documents", dependencies=[Depends(require_syndicate_subscription)])
async def documents(ctx: TenantContext=Depends(get_tenant_context)):
    rows=await ctx.conn.fetch("""
      SELECT d.id,d.collectivity_id,c.name collectivity_name,d.title,d.document_type,d.official_number,
        d.validation_status,d.effective_from,d.effective_to,d.original_filename,d.mime_type,
        d.file_size_bytes,d.sha256,d.scan_status,d.scan_engine,d.scanned_at,d.created_at,
        (SELECT count(*) FROM document_versions v WHERE v.organization_id=d.organization_id AND v.document_id=d.id) version_count
      FROM documents d JOIN collectivities c ON c.id=d.collectivity_id AND c.organization_id=d.organization_id
      WHERE d.organization_id=$1::uuid ORDER BY d.created_at DESC LIMIT 500
    """,ctx.organization_id)
    return [{"id":str(r["id"]),"collectivity_id":str(r["collectivity_id"]),"collectivity_name":r["collectivity_name"],
      "title":r["title"],"document_type":r["document_type"],"official_number":r["official_number"],
      "validation_status":r["validation_status"],"effective_from":r["effective_from"],"effective_to":r["effective_to"],
      "original_filename":r["original_filename"],"mime_type":r["mime_type"],"file_size_bytes":r["file_size_bytes"],
      "sha256":r["sha256"],"scan_status":r["scan_status"],"scan_engine":r["scan_engine"],"scanned_at":r["scanned_at"],"created_at":r["created_at"],"version_count":r["version_count"]} for r in rows]

@app.get("/api/v1/documents/search", dependencies=[Depends(require_syndicate_subscription)])
async def search_documents(q: str, collectivity_id: str | None = None, limit: int = 20,
    ctx: TenantContext = Depends(get_tenant_context)):
    query = q.strip()
    if len(query) < 3 or len(query) > 300:
        raise HTTPException(422, "La recherche doit contenir entre 3 et 300 caractères.")
    if not 1 <= limit <= 50:
        raise HTTPException(422, "La limite doit être comprise entre 1 et 50.")
    if collectivity_id:
        try:
            UUID(collectivity_id)
        except ValueError:
            raise HTTPException(400, "Identifiant de collectivité invalide.")
    rows = await ctx.conn.fetch("""
      SELECT d.id,d.title,d.document_type,d.validation_status,d.effective_from,d.effective_to,
        c.name AS collectivity_name,dt.extraction_status,
        ts_rank(dt.search_vector, plainto_tsquery('french', $2)) AS relevance,
        ts_headline('french',dt.extracted_text,plainto_tsquery('french',$2),
          'MaxWords=35,MinWords=12,ShortWord=2,HighlightAll=false') AS excerpt
      FROM document_text dt
      JOIN documents d ON d.organization_id=dt.organization_id AND d.id=dt.document_id AND d.sha256=dt.sha256
      JOIN collectivities c ON c.organization_id=d.organization_id AND c.id=d.collectivity_id
      WHERE dt.organization_id=$1::uuid AND dt.search_vector @@ plainto_tsquery('french',$2)
        AND ($3::uuid IS NULL OR d.collectivity_id=$3::uuid)
      ORDER BY relevance DESC,d.published_at DESC NULLS LAST LIMIT $4
    """,ctx.organization_id,query,collectivity_id,limit)
    return [{"id":str(r["id"]),"title":r["title"],"document_type":r["document_type"],
      "validation_status":r["validation_status"],"effective_from":r["effective_from"],
      "effective_to":r["effective_to"],"collectivity_name":r["collectivity_name"],
      "extraction_status":r["extraction_status"],"relevance":float(r["relevance"]),"excerpt":r["excerpt"]} for r in rows]


@app.get("/api/v1/documents/{document_id}", dependencies=[Depends(require_syndicate_subscription)])
async def document(document_id:str,ctx:TenantContext=Depends(get_tenant_context)):
    row=await ctx.conn.fetchrow("""SELECT d.id,d.collectivity_id,c.name collectivity_name,d.title,d.document_type,
      d.official_number,d.official_url,d.adopted_at,d.published_at,d.effective_from,d.effective_to,
      d.validation_status,d.validation_note,d.original_filename,d.mime_type,d.file_size_bytes,d.sha256,
      d.validated_by,d.validated_at,d.scan_status,d.scan_engine,d.scanned_at,d.created_at
      FROM documents d JOIN collectivities c ON c.id=d.collectivity_id AND c.organization_id=d.organization_id
      WHERE d.id=$1::uuid AND d.organization_id=$2::uuid""",document_id,ctx.organization_id)
    if not row:
        raise HTTPException(404,"Document introuvable.")
    return {k:(str(v) if k in ("id","collectivity_id","validated_by") and v is not None else v) for k,v in dict(row).items()}

MAX_DOCUMENT_BYTES = max(1, settings.document_max_size_mb) * 1024 * 1024
ALLOWED_MIME = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

async def scan_uploaded_bytes(data: bytes) -> dict:
    try:
        result = await asyncio.to_thread(scan_with_clamav, data, settings.clamav_host,
            settings.clamav_port, settings.clamav_timeout_seconds)
        return {"scan_status": result.status, "scan_engine": result.engine}
    except MalwareDetected:
        raise HTTPException(422, "Le fichier a été refusé : le contrôle antivirus a détecté un contenu malveillant.")
    except ScannerUnavailable:
        raise HTTPException(503, "Le contrôle antivirus est indisponible. Le fichier n'a pas été enregistré.")


async def read_and_validate_document(upload: UploadFile) -> tuple[bytes,str,str]:
    name = (upload.filename or "document").replace("\\", "/").split("/")[-1].strip()
    if not name or len(name) > 240:
        raise HTTPException(400,"Nom de fichier invalide.")
    ext = Path(name).suffix.lower()
    if ext not in (".pdf", ".docx"):
        raise HTTPException(415,"Seuls les fichiers PDF et DOCX sont acceptés.")
    chunks=[]
    total=0
    while True:
        chunk=await upload.read(1024*1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_DOCUMENT_BYTES:
            raise HTTPException(413,f"Fichier trop volumineux (maximum {settings.document_max_size_mb} Mo).")
        chunks.append(chunk)
    data=b"".join(chunks)
    if not data:
        raise HTTPException(400,"Le fichier est vide.")
    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(415,"Le contenu ne correspond pas à un PDF valide.")
        mime="application/pdf"
    else:
        try:
            with zipfile.ZipFile(BytesIO(data)) as zf:
                names=set(zf.namelist())
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise ValueError("DOCX structure missing")
                infos = zf.infolist()
                expanded = sum(item.file_size for item in infos)
                if expanded > 100 * 1024 * 1024 or any(item.file_size > 0 and item.compress_size == 0 for item in infos):
                    raise ValueError("DOCX expanded size exceeds safety limit")
                if any(item.compress_size and item.file_size / item.compress_size > 100 for item in infos):
                    raise ValueError("DOCX compression ratio exceeds safety limit")
        except Exception:
            raise HTTPException(415,"Le contenu ne correspond pas à un document DOCX valide.")
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if upload.content_type and upload.content_type != "application/octet-stream" and upload.content_type != mime:
        raise HTTPException(415,"Le type MIME déclaré ne correspond pas au format du fichier.")
    return data,name,mime

async def load_private_document(storage_key: str, missing_message: str) -> bytes:
    try:
        return await asyncio.to_thread(read_private_file, storage_key)
    except StorageNotFound:
        raise HTTPException(404, missing_message)
    except StorageError:
        raise HTTPException(503, "Le stockage privé est temporairement indisponible.")


@app.post("/api/v1/documents",status_code=201, dependencies=[Depends(require_syndicate_subscription)])
async def upload_document(
    title: str = Form(...), document_type: str = Form(...), collectivity_id: str = Form(...),
    official_number: str | None = Form(default=None), official_url: str | None = Form(default=None),
    adopted_at: date | None = Form(default=None), published_at: date | None = Form(default=None),
    effective_from: date | None = Form(default=None), effective_to: date | None = Form(default=None),
    file: UploadFile = File(...), ctx: TenantContext = Depends(require_legal_editor_for_external)):
    if not title.strip() or len(title)>300 or not document_type.strip() or len(document_type)>80:
        raise HTTPException(422,"Titre ou type de document invalide.")
    try:
        UUID(collectivity_id)
    except ValueError:
        raise HTTPException(400,"Identifiant de collectivité invalide.")
    collectivity=await ctx.conn.fetchrow("SELECT id FROM collectivities WHERE id=$1::uuid AND organization_id=$2::uuid",collectivity_id,ctx.organization_id)
    if not collectivity:
        raise HTTPException(404,"Collectivité introuvable dans cet espace.")
    data,filename,mime=await read_and_validate_document(file)
    scan = await scan_uploaded_bytes(data)
    extracted_text, extraction_status = extract_document_text(data, mime)
    digest=hashlib.sha256(data).hexdigest()
    doc_id=str(uuid4())
    try:
        storage_key=await asyncio.to_thread(store_private_file,ctx.organization_id,doc_id,1,data,Path(filename).suffix.lower(),mime)
    except StorageError:
        raise HTTPException(503, "Le stockage privé est temporairement indisponible.")
    try:
        async with ctx.conn.transaction():
            row=await ctx.conn.fetchrow("""INSERT INTO documents(organization_id,id,collectivity_id,title,document_type,official_number,
              adopted_at,published_at,effective_from,effective_to,official_url,storage_key,sha256,validation_status,
              uploaded_by,original_filename,mime_type,file_size_bytes,scan_status,scan_engine,scanned_at)
              VALUES($1::uuid,$2::uuid,$3::uuid,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'COLLECTED_UNVERIFIED',$14::uuid,$15,$16,$17,$18,$19,now())
              RETURNING id,created_at""",ctx.organization_id,doc_id,collectivity_id,title.strip(),document_type.strip(),official_number,
              adopted_at,published_at,effective_from,effective_to,official_url,storage_key,digest,ctx.user_id,filename,mime,len(data),scan["scan_status"],scan["scan_engine"])
            await ctx.conn.execute("""INSERT INTO document_versions(organization_id,document_id,version_number,storage_key,sha256,
              effective_from,effective_to,original_filename,mime_type,file_size_bytes,uploaded_by,scan_status,scan_engine,scanned_at)
              VALUES($1::uuid,$2::uuid,1,$3,$4,$5,$6,$7,$8,$9,$10::uuid,$11,$12,now())""",ctx.organization_id,doc_id,storage_key,digest,
              effective_from,effective_to,filename,mime,len(data),ctx.user_id,scan["scan_status"],scan["scan_engine"])
            await ctx.conn.execute("""INSERT INTO document_text(organization_id,document_id,version_number,sha256,extracted_text,extraction_status)
              VALUES($1::uuid,$2::uuid,1,$3,$4,$5)""",ctx.organization_id,doc_id,digest,extracted_text,extraction_status)
            await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
              VALUES($1::uuid,$2::uuid,'DOCUMENT_UPLOADED','document',$3::uuid,jsonb_build_object('version',1,'sha256',$4))""",
              ctx.organization_id,ctx.user_id,doc_id,digest)
    except Exception:
        try:
            await asyncio.to_thread(delete_private_file,storage_key)
        except StorageError:
            pass
        raise
    return {"id":doc_id,"version":1,"title":title.strip(),"original_filename":filename,"mime_type":mime,
      "file_size_bytes":len(data),"sha256":digest,"scan_status":scan["scan_status"],
      "extraction_status":extraction_status,"validation_status":"COLLECTED_UNVERIFIED","created_at":row["created_at"]}

@app.post("/api/v1/documents/{document_id}/versions",status_code=201, dependencies=[Depends(require_syndicate_subscription)])
async def upload_document_version(document_id:str,file:UploadFile=File(...),effective_from:date|None=Form(default=None),
    effective_to:date|None=Form(default=None),ctx:TenantContext=Depends(require_legal_editor)):
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(400,"Identifiant de document invalide.")
    doc=await ctx.conn.fetchrow("SELECT id FROM documents WHERE id=$1::uuid AND organization_id=$2::uuid",document_id,ctx.organization_id)
    if not doc:
        raise HTTPException(404,"Document introuvable.")
    data,filename,mime=await read_and_validate_document(file)
    scan = await scan_uploaded_bytes(data)
    extracted_text, extraction_status = extract_document_text(data, mime)
    digest=hashlib.sha256(data).hexdigest()
    storage_key=None
    version=None
    try:
        async with ctx.conn.transaction():
            # The document row is the serialization point for concurrent version uploads.
            # The lock must be acquired inside this transaction and held through commit.
            locked_doc=await ctx.conn.fetchrow(
                "SELECT id FROM documents WHERE id=$1::uuid AND organization_id=$2::uuid FOR UPDATE",
                document_id,ctx.organization_id)
            if not locked_doc:
                raise HTTPException(404,"Document introuvable.")
            version=await ctx.conn.fetchval(
                "SELECT COALESCE(max(version_number),0)+1 FROM document_versions WHERE organization_id=$1::uuid AND document_id=$2::uuid",
                ctx.organization_id,document_id)
            storage_key=await asyncio.to_thread(store_private_file,ctx.organization_id,document_id,version,data,Path(filename).suffix.lower(),mime)
            await ctx.conn.execute("""INSERT INTO document_versions(organization_id,document_id,version_number,storage_key,sha256,
              effective_from,effective_to,original_filename,mime_type,file_size_bytes,uploaded_by,scan_status,scan_engine,scanned_at)
              VALUES($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,$9,$10,$11::uuid,$12,$13,now())""",ctx.organization_id,document_id,version,
              storage_key,digest,effective_from,effective_to,filename,mime,len(data),ctx.user_id,scan["scan_status"],scan["scan_engine"])
            await ctx.conn.execute("""UPDATE documents SET storage_key=$3,sha256=$4,original_filename=$5,mime_type=$6,
              file_size_bytes=$7,effective_from=COALESCE($8,effective_from),effective_to=$9,
              validation_status='COLLECTED_UNVERIFIED',validated_by=NULL,validated_at=NULL,validation_note=NULL,
              scan_status=$10,scan_engine=$11,scanned_at=now()
              WHERE organization_id=$1::uuid AND id=$2::uuid""",ctx.organization_id,document_id,storage_key,digest,filename,mime,len(data),effective_from,effective_to,scan["scan_status"],scan["scan_engine"])
            await ctx.conn.execute("""INSERT INTO document_text(organization_id,document_id,version_number,sha256,extracted_text,extraction_status)
              VALUES($1::uuid,$2::uuid,$3,$4,$5,$6)""",ctx.organization_id,document_id,version,digest,extracted_text,extraction_status)
            await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
              VALUES($1::uuid,$2::uuid,'DOCUMENT_VERSION_UPLOADED','document',$3::uuid,jsonb_build_object('version',$4,'sha256',$5))""",
              ctx.organization_id,ctx.user_id,document_id,version,digest)
    except Exception as exc:
        if storage_key:
            try:
                await asyncio.to_thread(delete_private_file,storage_key)
            except StorageError:
                pass
        if isinstance(exc, StorageError):
            raise HTTPException(503, "Le stockage privé est temporairement indisponible.")
        raise
    return {"document_id":document_id,"version":version,"original_filename":filename,"sha256":digest,
      "scan_status":scan["scan_status"],"extraction_status":extraction_status,"validation_status":"COLLECTED_UNVERIFIED"}

@app.get("/api/v1/documents/{document_id}/versions", dependencies=[Depends(require_syndicate_subscription)])
async def document_versions(document_id:str,ctx:TenantContext=Depends(get_tenant_context)):
    rows=await ctx.conn.fetch("""SELECT id,version_number,original_filename,mime_type,file_size_bytes,sha256,scan_status,scan_engine,scanned_at,
      effective_from,effective_to,created_at FROM document_versions WHERE organization_id=$1::uuid AND document_id=$2::uuid
      ORDER BY version_number DESC""",ctx.organization_id,document_id)
    if not rows:
        raise HTTPException(404,"Document ou versions introuvables.")
    return [{"id":str(r["id"]),"version_number":r["version_number"],"original_filename":r["original_filename"],
      "mime_type":r["mime_type"],"file_size_bytes":r["file_size_bytes"],"sha256":r["sha256"],"scan_status":r["scan_status"],"scan_engine":r["scan_engine"],"scanned_at":r["scanned_at"],
      "effective_from":r["effective_from"],"effective_to":r["effective_to"],"created_at":r["created_at"]} for r in rows]

@app.post("/api/v1/documents/{document_id}/reindex", dependencies=[Depends(require_syndicate_subscription)])
async def reindex_document_versions(document_id: str, ctx: TenantContext = Depends(require_legal_editor)):
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(400, "Identifiant de document invalide.")
    rows = await ctx.conn.fetch("""SELECT version_number,storage_key,mime_type,sha256,scan_status
      FROM document_versions WHERE organization_id=$1::uuid AND document_id=$2::uuid ORDER BY version_number""",
      ctx.organization_id,document_id)
    if not rows:
        raise HTTPException(404, "Document introuvable.")
    extracted=[]
    for row in rows:
        if row["scan_status"] != "CLEAN":
            raise HTTPException(409, "Toutes les versions doivent être analysées et déclarées saines avant réindexation.")
        if not row["storage_key"]:
            raise HTTPException(404, "Une version ne possède pas de fichier dans le stockage privé.")
        data=await load_private_document(row["storage_key"], "Un fichier de version est absent du stockage privé.")
        if not document_sha256_matches(data, row["sha256"]):
            raise HTTPException(409, "Une version a été modifiée ou corrompue dans le stockage privé. Réparez le fichier avant réindexation.")
        text_value,status=extract_document_text(data,row["mime_type"] or "")
        extracted.append((row["version_number"],row["sha256"],text_value,status))
    async with ctx.conn.transaction():
        for version_number,digest,text_value,status in extracted:
            await ctx.conn.execute("""INSERT INTO document_text(organization_id,document_id,version_number,sha256,extracted_text,extraction_status)
              VALUES($1::uuid,$2::uuid,$3,$4,$5,$6)
              ON CONFLICT(organization_id,document_id,version_number) DO UPDATE
              SET sha256=EXCLUDED.sha256,extracted_text=EXCLUDED.extracted_text,extraction_status=EXCLUDED.extraction_status""",
              ctx.organization_id,document_id,version_number,digest,text_value,status)
        await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
          VALUES($1::uuid,$2::uuid,'DOCUMENT_REINDEXED','document',$3::uuid,$4::jsonb)""",
          ctx.organization_id,ctx.user_id,document_id,json.dumps({"versions":len(extracted)}))
    return {"document_id":document_id,"versions":[{"version":v,"extraction_status":status} for v,_,__,status in extracted]}


@app.post("/api/v1/documents/{document_id}/rescan", dependencies=[Depends(require_syndicate_subscription)])
async def rescan_document_versions(document_id: str, ctx: TenantContext = Depends(require_legal_editor)):
    try:
        UUID(document_id)
    except ValueError:
        raise HTTPException(400, "Identifiant de document invalide.")
    rows = await ctx.conn.fetch("""SELECT version_number,storage_key,sha256 FROM document_versions
      WHERE organization_id=$1::uuid AND document_id=$2::uuid ORDER BY version_number""",ctx.organization_id,document_id)
    legacy_current = None
    if not rows:
        legacy_current = await ctx.conn.fetchrow("""SELECT storage_key,sha256,effective_from,effective_to,
          original_filename,mime_type,file_size_bytes,uploaded_by FROM documents
          WHERE organization_id=$1::uuid AND id=$2::uuid""",ctx.organization_id,document_id)
        if not legacy_current or not legacy_current["storage_key"]:
            raise HTTPException(404, "Document introuvable ou fichier absent du stockage privé.")
        rows = [{"version_number":1,"storage_key":legacy_current["storage_key"]}]
    results=[]
    for row in rows:
        if not row["storage_key"]:
            raise HTTPException(404, "Une version ne possède pas de fichier dans le stockage privé.")
        data=await load_private_document(row["storage_key"], "Un fichier de version est absent du stockage privé.")
        if not document_sha256_matches(data, row["sha256"]):
            results.append({"version":row["version_number"],"scan_status":"INFECTED","scan_engine":"INTEGRITY_CHECK"})
            continue
        try:
            result=await asyncio.to_thread(scan_with_clamav,data,settings.clamav_host,
                settings.clamav_port,settings.clamav_timeout_seconds)
            status=result.status
            engine=result.engine
        except MalwareDetected:
            status="INFECTED"
            engine="ClamAV"
        except ScannerUnavailable:
            raise HTTPException(503, "Le contrôle antivirus est indisponible ; aucun statut n'a été modifié.")
        results.append({"version":row["version_number"],"scan_status":status,"scan_engine":engine})
    async with ctx.conn.transaction():
        if legacy_current:
            item = results[0]
            await ctx.conn.execute("""INSERT INTO document_versions(organization_id,document_id,version_number,storage_key,sha256,
              effective_from,effective_to,original_filename,mime_type,file_size_bytes,uploaded_by,scan_status,scan_engine,scanned_at)
              VALUES($1::uuid,$2::uuid,1,$3,$4,$5,$6,$7,$8,$9,$10::uuid,$11,$12,now())""",
              ctx.organization_id,document_id,legacy_current["storage_key"],legacy_current["sha256"],
              legacy_current["effective_from"],legacy_current["effective_to"],legacy_current["original_filename"],
              legacy_current["mime_type"],legacy_current["file_size_bytes"],legacy_current["uploaded_by"],
              item["scan_status"],item["scan_engine"])
        else:
            for item in results:
                await ctx.conn.execute("""UPDATE document_versions SET scan_status=$4,scan_engine=$5,scanned_at=now()
                  WHERE organization_id=$1::uuid AND document_id=$2::uuid AND version_number=$3""",
                  ctx.organization_id,document_id,item["version"],item["scan_status"],item["scan_engine"])
        current_version=max(item["version"] for item in results)
        current_item=next(item for item in results if item["version"] == current_version)
        current_status=current_item["scan_status"]
        current_engine=current_item["scan_engine"]
        await ctx.conn.execute("""UPDATE documents SET scan_status=$3,scan_engine=$4,scanned_at=now()
          WHERE organization_id=$1::uuid AND id=$2::uuid""",ctx.organization_id,document_id,current_status,current_engine)
        await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
          VALUES($1::uuid,$2::uuid,'DOCUMENT_ANTIVIRUS_RESCAN','document',$3::uuid,$4::jsonb)""",
          ctx.organization_id,ctx.user_id,document_id,json.dumps({"versions":results}))
    return {"document_id":document_id,"versions":results}


@app.get("/api/v1/documents/{document_id}/download", dependencies=[Depends(require_syndicate_subscription)])
async def download_document(document_id:str,ctx:TenantContext=Depends(get_tenant_context_for_chat)):
    row=await ctx.conn.fetchrow("SELECT storage_key,original_filename,mime_type,scan_status,sha256 FROM documents WHERE id=$1::uuid AND organization_id=$2::uuid",document_id,ctx.organization_id)
    if not row or not row["storage_key"]:
        raise HTTPException(404,"Fichier introuvable.")
    if row["scan_status"] != "CLEAN":
        raise HTTPException(423,"Le fichier n'est pas validé par le contrôle antivirus.")
    data=await load_private_document(row["storage_key"], "Fichier introuvable dans le stockage privé.")
    if not document_sha256_matches(data, row["sha256"]):
        raise HTTPException(409,"Le fichier a été modifié ou corrompu dans le stockage privé. Téléchargement bloqué.")
    filename=row["original_filename"] or "document"
    return Response(content=data,media_type=row["mime_type"] or "application/octet-stream",headers={
        "Content-Disposition":f"attachment; filename=\"document\"; filename*=UTF-8''{quote(filename)}",
        "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@app.get("/api/v1/documents/{document_id}/versions/{version_number}/download", dependencies=[Depends(require_syndicate_subscription)])
async def download_document_version(document_id:str,version_number:int,ctx:TenantContext=Depends(get_tenant_context_for_chat)):
    row=await ctx.conn.fetchrow("""SELECT storage_key,original_filename,mime_type,scan_status,sha256 FROM document_versions
      WHERE organization_id=$1::uuid AND document_id=$2::uuid AND version_number=$3""",ctx.organization_id,document_id,version_number)
    if not row or not row["storage_key"]:
        raise HTTPException(404,"Version introuvable.")
    if row["scan_status"] != "CLEAN":
        raise HTTPException(423,"La version n'est pas validée par le contrôle antivirus.")
    data=await load_private_document(row["storage_key"], "Fichier introuvable dans le stockage privé.")
    if not document_sha256_matches(data, row["sha256"]):
        raise HTTPException(409,"Le fichier a été modifié ou corrompu dans le stockage privé. Téléchargement bloqué.")
    filename=row["original_filename"] or "document"
    return Response(content=data,media_type=row["mime_type"] or "application/octet-stream",headers={
        "Content-Disposition":f"attachment; filename=\"document\"; filename*=UTF-8''{quote(filename)}",
        "Cache-Control":"private, no-store","X-Content-Type-Options":"nosniff"})

@app.put("/api/v1/documents/{document_id}", dependencies=[Depends(require_syndicate_subscription)])
async def update_document_metadata(document_id:str,payload:DocumentMetadataUpdate,ctx:TenantContext=Depends(require_legal_editor)):
    try:
        UUID(document_id)
        UUID(payload.collectivity_id)
    except ValueError:
        raise HTTPException(400,"Identifiant invalide.")
    collectivity=await ctx.conn.fetchrow("SELECT id FROM collectivities WHERE id=$1::uuid AND organization_id=$2::uuid",payload.collectivity_id,ctx.organization_id)
    if not collectivity:
        raise HTTPException(404,"Collectivité introuvable dans cet espace.")
    if payload.effective_from and payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(422,"La date de fin d'application précède la date de début.")
    row=await ctx.conn.fetchrow("""UPDATE documents SET collectivity_id=$3::uuid,title=$4,document_type=$5,
      official_number=$6,official_url=$7,adopted_at=$8,published_at=$9,effective_from=$10,effective_to=$11
      WHERE id=$1::uuid AND organization_id=$2::uuid RETURNING id,title,document_type,collectivity_id""",
      document_id,ctx.organization_id,payload.collectivity_id,payload.title.strip(),payload.document_type.strip(),
      payload.official_number,payload.official_url,payload.adopted_at,payload.published_at,payload.effective_from,payload.effective_to)
    if not row:
        raise HTTPException(404,"Document introuvable.")
    await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
      VALUES($1::uuid,$2::uuid,'DOCUMENT_METADATA_UPDATED','document',$3::uuid)""",ctx.organization_id,ctx.user_id,document_id)
    return {"id":str(row["id"]),"title":row["title"],"document_type":row["document_type"],"collectivity_id":str(row["collectivity_id"])}

@app.patch("/api/v1/documents/{document_id}/validation", dependencies=[Depends(require_syndicate_subscription)])
async def validate_document(document_id:str,payload:DocumentValidationUpdate,ctx:TenantContext=Depends(require_legal_editor)):
    if payload.validation_status in ("VERIFIED_APPLICABLE", "VERIFIED_HISTORICAL", "REPEALED", "REPLACED") and not (payload.validation_note or "").strip():
        raise HTTPException(422,"Une justification est obligatoire pour une validation juridique.")
    row=await ctx.conn.fetchrow("""UPDATE documents SET validation_status=$3,validation_note=$4,validated_by=$5::uuid,
      validated_at=now() WHERE id=$1::uuid AND organization_id=$2::uuid RETURNING id,validation_status,validated_by,validated_at""",
      document_id,ctx.organization_id,payload.validation_status,payload.validation_note,ctx.user_id)
    if not row:
        raise HTTPException(404,"Document introuvable.")
    await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES($1::uuid,$2::uuid,'DOCUMENT_VALIDATED','document',$3::uuid,jsonb_build_object('status',$4))""",
      ctx.organization_id,ctx.user_id,document_id,payload.validation_status)
    return {"id":str(row["id"]),"validation_status":row["validation_status"],"validated_by":str(row["validated_by"]),"validated_at":row["validated_at"]}


@app.post("/api/v1/organizations/me/invitations", status_code=201, dependencies=[Depends(require_syndicate_subscription)])
async def create_invitation(payload: InvitationCreate, response: Response, ctx: TenantContext = Depends(require_org_admin)):
    """Create a one-time invitation. The raw token is returned once for secure manual delivery."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    email = str(payload.email).strip().lower()
    if settings.private_instance_mode:
        is_platform_admin = await ctx.conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=$1::uuid)", ctx.user_id)
        if not is_platform_admin:
            raise HTTPException(403, "Seul l'administrateur désigné peut gérer les comptes de cette instance.")
        if payload.role == "ORG_ADMIN":
            raise HTTPException(422, "Les comptes invités ne peuvent pas recevoir le rôle administrateur.")
    token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    existing = await ctx.conn.fetchrow("""
      SELECT 1 FROM memberships m JOIN users u ON u.id=m.user_id
      WHERE m.organization_id=$1::uuid AND lower(u.email)=lower($2) AND m.status='ACTIVE'
    """, ctx.organization_id, email)
    if existing:
        raise HTTPException(409, "Cette adresse dispose déjà d'un accès actif dans cette organisation.")
    if not settings.private_instance_mode:
        sub = await ctx.conn.fetchrow("SELECT plan_code,status FROM subscriptions WHERE organization_id=$1::uuid", ctx.organization_id)
        current_plan = PLANS.get(sub["plan_code"], PLANS["FOUNDING_FREE"]) if sub else PLANS["FOUNDING_FREE"]
        is_free_email = await ctx.conn.fetchval("""SELECT EXISTS(SELECT 1 FROM platform_free_email_access
            WHERE email_normalized=$1 AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at>now()))""", email)
        if not is_free_email and sub and sub["status"] not in ("ACTIVE", "TRIAL", "FOUNDING_FREE"):
            raise HTTPException(402, "Abonnement à régulariser avant d'ajouter des utilisateurs payants.")
        if not is_free_email:
            seat_counts = await ctx.conn.fetchrow("SELECT * FROM tenant_billing_seat_counts($1::uuid)", ctx.organization_id)
            occupied = seat_counts["paid_active_users"] + seat_counts["pending_paid_invitations"]
            if occupied >= current_plan["max_users"]:
                raise HTTPException(402, f"Limite de {current_plan['max_users']} utilisateurs payants atteinte. Les adresses bénéficiant d'un accès gratuit ne consomment pas de place.")
    async with ctx.conn.transaction():
        allowed = await ctx.conn.fetchval(
            "SELECT beta_user_slot_available($1,$2)", email, settings.beta_max_users)
        if not allowed:
            raise HTTPException(409, f"Limite temporaire de {settings.beta_max_users} utilisateurs atteinte pour la bêta.")
        row = await ctx.conn.fetchrow("""
          INSERT INTO invitations(organization_id,email_normalized,role,invited_by,status,token_hash,expires_at)
          VALUES($1::uuid,$2,$3,$4::uuid,'PENDING',$5,now()+interval '7 days')
          ON CONFLICT (organization_id,(lower(email_normalized))) WHERE status='PENDING' DO NOTHING
          RETURNING id,email_normalized,role,status,expires_at
        """, ctx.organization_id, email, payload.role, ctx.user_id, token_hash)
    if not row:
        raise HTTPException(409, "Une invitation est déjà en attente pour cette adresse dans cette organisation.")
    delivery = "MANUAL_SECURE_DELIVERY"
    keycloak_user_id = None
    smtp_ready = bool(settings.smtp_host and settings.smtp_from)
    keycloak_ready = bool(settings.keycloak_admin_base_url and settings.keycloak_admin_client_secret)
    auth0_ready = settings.oidc_provider == "auth0" and bool(settings.oidc_client_id)
    if smtp_ready and (keycloak_ready or auth0_ready):
        try:
            if settings.oidc_provider == "keycloak":
                admin = KeycloakAdmin(KeycloakAdminConfig(
                    base_url=settings.keycloak_admin_base_url, realm=settings.keycloak_admin_realm,
                    client_id=settings.keycloak_admin_client_id, client_secret=settings.keycloak_admin_client_secret,
                    timeout=settings.keycloak_admin_timeout_seconds))
                keycloak_user_id, created_in_keycloak, email_verified = await admin.ensure_user(email)
                if not email_verified:
                    await admin.send_verification(
                        keycloak_user_id, settings.invitation_base_url.rstrip("/") + "/", created_in_keycloak
                    )
            # Auth0 handles account creation and email verification through Universal Login.
            # Dikévia sends only its own single-use organization invitation token.
            organization = await ctx.conn.fetchrow("SELECT display_name FROM organizations WHERE id=$1::uuid", ctx.organization_id)
            organization_name = organization["display_name"] if organization else "votre organisation"
            invite_url = f"{settings.invitation_base_url.rstrip('/')}/?invitation_token={token}"
            await asyncio.to_thread(send_invitation_email, settings.smtp_host, settings.smtp_port,
                settings.smtp_username, settings.smtp_password, settings.smtp_from, email,
                organization_name, payload.role, invite_url, True)
            delivery = "SMTP_EMAIL_SENT"
        except Exception:
            await ctx.conn.execute("UPDATE invitations SET status='REVOKED' WHERE id=$1::uuid", row["id"])
            raise HTTPException(503, "L'invitation n'a pas été envoyée. Vérifiez le fournisseur d'identité et le serveur SMTP.")
    await ctx.conn.execute("""
      INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES($1::uuid,$2::uuid,'INVITATION_CREATED','invitation',$3::uuid,jsonb_build_object('role',$4,'email',$5,'delivery',$6))
    """, ctx.organization_id, ctx.user_id, row["id"], payload.role, email, delivery)
    result = {"id": str(row["id"]), "email": row["email_normalized"], "role": row["role"],
              "status": row["status"], "expires_at": row["expires_at"], "delivery": delivery}
    if delivery == "SMTP_EMAIL_SENT":
        if keycloak_user_id:
            result["keycloak_user_id"] = keycloak_user_id
    else:
        result["invitation_token"] = token
        result["warning"] = "Le provisionnement automatique n'est pas configuré. Transmettez ce jeton par un canal sûr."
    return result

@app.delete("/api/v1/organizations/me/invitations/{invitation_id}", status_code=204, dependencies=[Depends(require_syndicate_subscription)])
async def revoke_invitation(invitation_id: str, ctx: TenantContext = Depends(require_org_admin)):
    if settings.private_instance_mode and not await ctx.conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=$1::uuid)", ctx.user_id):
        raise HTTPException(403, "Seul l'administrateur désigné peut gérer les invitations.")
    row = await ctx.conn.fetchrow("""
      UPDATE invitations SET status='REVOKED'
      WHERE id=$1::uuid AND organization_id=$2::uuid AND status='PENDING'
      RETURNING id
    """, invitation_id, ctx.organization_id)
    if not row:
        raise HTTPException(404, "Invitation en attente introuvable.")
    await ctx.conn.execute("""
      INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
      VALUES($1::uuid,$2::uuid,'INVITATION_REVOKED','invitation',$3::uuid)
    """, ctx.organization_id, ctx.user_id, row["id"])
    return Response(status_code=204)

@app.post("/api/v1/invitations/accept", status_code=200)
async def accept_invitation(payload: InvitationAccept, response: Response, principal: Principal = Depends(get_principal)):
    """Accept an invitation for the authenticated OIDC identity; token is single-use and email-bound."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.oidc_issuer',$1,true)", principal.issuer)
            await conn.execute("SELECT set_config('app.oidc_subject',$1,true)", principal.subject)
            await conn.execute("SELECT set_config('app.invitation_token_hash',$1,true)", token_hash)
            invitation = await conn.fetchrow("""
              SELECT id,organization_id,email_normalized,role,status,expires_at
              FROM invitations WHERE token_hash=$1 FOR UPDATE
            """, token_hash)
            if not invitation or invitation["status"] != "PENDING" or invitation["expires_at"] <= await conn.fetchval("SELECT now()"):
                raise HTTPException(400, "Invitation invalide, expirée ou déjà utilisée.")
            claims_email = principal.email
            # Email is taken from verified OIDC claims, not from request data.
            if not claims_email or not principal.email_verified:
                raise HTTPException(403, "Le fournisseur d'identité doit fournir un e-mail vérifié.")
            normalized_email = str(claims_email).strip().lower()
            if normalized_email != invitation["email_normalized"]:
                raise HTTPException(403, "Cette invitation ne correspond pas à l'adresse du compte connecté.")
            allowed = await conn.fetchval(
                "SELECT beta_user_slot_available($1,$2)", normalized_email, settings.beta_max_users)
            if not allowed:
                raise HTTPException(409, f"Limite temporaire de {settings.beta_max_users} utilisateurs atteinte pour la bêta.")
            user = await conn.fetchrow("""
              INSERT INTO users(oidc_issuer,oidc_subject,email,status)
              VALUES($1,$2,$3,'ACTIVE')
              ON CONFLICT(oidc_issuer,oidc_subject) DO UPDATE SET email=EXCLUDED.email
              WHERE users.status='ACTIVE'
              RETURNING id
            """, principal.issuer, principal.subject, normalized_email)
            if not user:
                raise HTTPException(403, "Compte désactivé.")
            org_id = str(invitation["organization_id"])
            await conn.execute("SELECT set_config('app.current_org_id',$1,true)", org_id)
            # Serialize acceptances for the same organization/user, including the
            # no-existing-row case where SELECT ... FOR UPDATE cannot take a row lock.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1::text || ':' || $2::text, 0))",
                org_id, user["id"])
            existing_membership = await conn.fetchrow("""
              SELECT status FROM memberships
              WHERE organization_id=$1::uuid AND user_id=$2::uuid FOR UPDATE
            """, org_id, user["id"])
            if existing_membership and existing_membership["status"] == "ACTIVE":
                raise HTTPException(409, "Ce compte dispose déjà d'un accès actif à cette organisation. L'invitation ne peut pas modifier son rôle.")
            membership_status = "INVITED" if settings.private_instance_mode else "ACTIVE"
            await conn.execute("""
              INSERT INTO memberships(organization_id,user_id,role,status)
              VALUES($1::uuid,$2::uuid,$3,$4)
              ON CONFLICT(organization_id,user_id) DO UPDATE SET role=EXCLUDED.role,status=EXCLUDED.status
            """, org_id, user["id"], invitation["role"], membership_status)
            await conn.execute("UPDATE invitations SET status='ACCEPTED' WHERE id=$1", invitation["id"])
            await conn.execute("""
              INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
              VALUES($1::uuid,$2::uuid,'INVITATION_ACCEPTED','invitation',$3::uuid)
            """, org_id, user["id"], invitation["id"])
    return {"status": "PENDING_APPROVAL" if settings.private_instance_mode else "ACTIVE",
            "organization_id": str(invitation["organization_id"]), "role": invitation["role"]}

@app.get("/api/v1/platform/private-members")
async def private_instance_members(platform=Depends(require_platform_admin)):
    if not settings.private_instance_mode:
        raise HTTPException(404, "Cette fonction est réservée à l'instance privée.")
    rows = await get_platform_admin_pool().fetch(
        "SELECT * FROM private_instance_pending_members($1::uuid)", platform["user_id"])
    return {"members": [{
        "organization_id": str(r["organization_id"]), "user_id": str(r["user_id"]),
        "email": r["email"], "role": r["role"], "status": r["membership_status"],
        "created_at": r["created_at"]
    } for r in rows]}

@app.patch("/api/v1/platform/private-members/{organization_id}/{user_id}")
async def private_instance_set_member(organization_id: str, user_id: str, payload: dict,
                                     platform=Depends(require_platform_admin)):
    if not settings.private_instance_mode:
        raise HTTPException(404, "Cette fonction est réservée à l'instance privée.")
    try:
        org_id, member_id = str(UUID(organization_id)), str(UUID(user_id))
    except ValueError:
        raise HTTPException(422, "Identifiant invalide.")
    status = payload.get("status") if isinstance(payload, dict) else None
    if status not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
        raise HTTPException(422, "Statut attendu : ACTIVE, SUSPENDED ou REVOKED.")
    try:
        changed = await get_platform_admin_pool().fetchval(
            "SELECT private_instance_set_member_status($1::uuid,$2::uuid,$3::uuid,$4)",
            platform["user_id"], org_id, member_id, status)
    except Exception as exc:
        if "private instance seat limit reached" in str(exc):
            raise HTTPException(409, "Les 10 comptes sont déjà actifs. Suspendez un compte avant d'en activer un autre.")
        raise
    if not changed:
        raise HTTPException(404, "Compte introuvable.")
    return {"organization_id": org_id, "user_id": member_id, "status": status}

@app.get("/api/v1/platform/organizations")
async def platform_list_organizations(platform=Depends(require_platform_admin)):
    """Cross-tenant directory exposed only through a DBA-owned guarded SQL function."""
    rows = await get_platform_admin_pool().fetch(
        "SELECT * FROM platform_admin_list_organizations($1::uuid)", platform["user_id"])
    return [{
        "id": str(r["id"]), "slug": r["slug"], "legal_name": r["legal_name"],
        "display_name": r["display_name"], "status": r["organization_status"],
        "plan_code": r["plan_code"], "subscription_status": r["subscription_status"],
        "active_users": r["active_users"], "pending_invitations": r["pending_invitations"],
        "created_at": r["created_at"], "current_period_end": r["current_period_end"],
        "free_access_until": r["free_access_until"]
    } for r in rows]


@app.patch("/api/v1/platform/organizations/{organization_id}/status")
async def platform_set_organization_status(organization_id: str, payload: dict,
        platform=Depends(require_platform_admin)):
    try:
        org_id = str(UUID(organization_id))
    except ValueError:
        raise HTTPException(422, "Identifiant d'organisation invalide.")
    status = payload.get("status") if isinstance(payload, dict) else None
    if status not in ("ACTIVE", "SUSPENDED"):
        raise HTTPException(422, "État demandé invalide.")
    changed = await get_platform_admin_pool().fetchval(
        "SELECT platform_admin_set_organization_status($1::uuid,$2::uuid,$3)",
        platform["user_id"], org_id, status)
    if not changed:
        raise HTTPException(404, "Organisation introuvable.")
    return {"organization_id": org_id, "status": status}


@app.post("/api/v1/platform/organizations", status_code=201)
async def create_organization(payload: OrganizationCreate, platform=Depends(require_platform_admin)):
    """Organization creation is performed by a guarded SECURITY DEFINER function."""
    org_id = str(uuid4())
    async with get_platform_admin_pool().acquire() as conn:
        async with conn.transaction():
            try:
                await conn.fetchval(
                    "SELECT platform_admin_create_organization("
                    "$1::uuid,$2::uuid,$3,$4,$5,$6)",
                    platform["user_id"], org_id, payload.slug, payload.legal_name,
                    payload.display_name, settings.private_instance_mode,
                )
            except Exception as exc:
                message = str(exc).lower()
                if "unique" in message or "duplicate" in message:
                    raise HTTPException(409, "Cet identifiant d'organisation est déjà utilisé.")
                if "private instance is limited to one organization" in message:
                    raise HTTPException(409, "L'instance privée est limitée à une seule organisation syndicale.")
                raise
    return {"id": org_id, "slug": payload.slug, "display_name": payload.display_name,
            "founding_plan": "FOUNDING_FREE", "creator_role": "ORG_ADMIN"}

@app.patch("/api/v1/organizations/me/members/{user_id}/role", dependencies=[Depends(require_syndicate_subscription)])
async def update_member_role(user_id: str, payload: MemberRoleUpdate, ctx: TenantContext = Depends(require_org_admin)):
    role = payload.role
    if settings.private_instance_mode:
        if not await ctx.conn.fetchval("SELECT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=$1::uuid)", ctx.user_id):
            raise HTTPException(403, "Seul l'administrateur désigné peut gérer les rôles.")
        if role == "ORG_ADMIN":
            raise HTTPException(422, "Aucun second administrateur n'est autorisé sur cette instance privée.")
    if role not in {"ORG_ADMIN", "LEGAL_EDITOR", "MEMBER"}:
        raise HTTPException(422, "Rôle invalide.")
    await ctx.conn.fetchrow("SELECT id FROM organizations WHERE id=$1::uuid FOR UPDATE", ctx.organization_id)
    target = await ctx.conn.fetchrow(
        "SELECT id,role,status FROM memberships WHERE organization_id=$1::uuid AND user_id=$2::uuid",
        ctx.organization_id, user_id)
    if not target or target["status"] != "ACTIVE":
        raise HTTPException(404, "Adhésion active introuvable.")
    if target["role"] == "ORG_ADMIN" and role != "ORG_ADMIN":
        count = await ctx.conn.fetchval(
            "SELECT count(*) FROM memberships WHERE organization_id=$1::uuid AND role='ORG_ADMIN' AND status='ACTIVE'",
            ctx.organization_id)
        if count <= 1:
            raise HTTPException(409, "Impossible de retirer le dernier administrateur de l'organisation.")
    await ctx.conn.execute(
        "UPDATE memberships SET role=$3 WHERE organization_id=$1::uuid AND user_id=$2::uuid",
        ctx.organization_id, user_id, role)
    await ctx.conn.execute("""INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id,metadata)
      VALUES($1::uuid,$2::uuid,'MEMBERSHIP_ROLE_CHANGED','membership',$3::uuid,jsonb_build_object('role',$4))""",
      ctx.organization_id, ctx.user_id, user_id, role)
    return {"user_id": user_id, "role": role, "status": "ACTIVE"}

@app.delete("/api/v1/organizations/me/members/{user_id}", status_code=204, dependencies=[Depends(require_syndicate_subscription)])
async def revoke_member(user_id: str, ctx: TenantContext=Depends(require_org_admin)):
    if settings.private_instance_mode and not await ctx.conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM platform_admins WHERE user_id=$1::uuid)", ctx.user_id):
        raise HTTPException(403, "Seul l'administrateur désigné peut révoquer les comptes.")
    # Verrouillage de la ligne organisation pour empêcher deux révocations concurrentes
    # de supprimer simultanément les deux derniers administrateurs.
    await ctx.conn.fetchrow("SELECT id FROM organizations WHERE id=$1::uuid FOR UPDATE", ctx.organization_id)
    target = await ctx.conn.fetchrow(
        "SELECT id,role,status FROM memberships WHERE organization_id=$1::uuid AND user_id=$2::uuid",
        ctx.organization_id,user_id)
    if not target:
        raise HTTPException(404,"Adhésion introuvable.")
    if target["role"] == "ORG_ADMIN" and target["status"] == "ACTIVE":
        count = await ctx.conn.fetchval(
            "SELECT count(*) FROM memberships WHERE organization_id=$1::uuid AND role='ORG_ADMIN' AND status='ACTIVE'",
            ctx.organization_id)
        if count <= 1:
            raise HTTPException(409,"Impossible de révoquer le dernier administrateur.")
    await ctx.conn.execute(
        "UPDATE memberships SET status='REVOKED' WHERE organization_id=$1::uuid AND user_id=$2::uuid",
        ctx.organization_id,user_id)
    await ctx.conn.execute(
        """INSERT INTO audit_events(organization_id,actor_user_id,event_type,target_type,target_id)
           VALUES($1::uuid,$2::uuid,'MEMBERSHIP_REVOKED','membership',$3::uuid)""",
        ctx.organization_id,ctx.user_id,user_id)
    return Response(status_code=204)

@app.get("/api/v1/admin/health")
async def admin_health(ctx:TenantContext=Depends(require_org_admin)):
    return {"organization_id":ctx.organization_id,"status":"ok"}
