"""Real PostgreSQL tests for migration 019's global beta capacity guard.

CI supplies disposable TEST_DATABASE_ADMIN_URL and TEST_DATABASE_URL connections.
The test executes the SECURITY DEFINER function as the runtime role and exercises
its transaction-scoped advisory lock with concurrent invitation reservations.
"""
import asyncio
import os
import uuid

import pytest

ADMIN_URL = os.getenv("TEST_DATABASE_ADMIN_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not (ADMIN_URL and RUNTIME_URL),
    reason="PostgreSQL test URLs not configured",
)


async def _run_beta_capacity_scenario():
    import asyncpg

    org_id = uuid.uuid4()
    member_id = uuid.uuid4()
    platform_admin_id = uuid.uuid4()
    invited_member_id = uuid.uuid4()
    invited_by_id = member_id
    suffix = uuid.uuid4().hex
    active_email = f"active-{suffix}@example.test"
    admin_email = f"admin-{suffix}@example.test"
    pending_email = f"pending-{suffix}@example.test"
    awaiting_email = f"awaiting-{suffix}@example.test"
    admin = await asyncpg.connect(ADMIN_URL)
    runtime = await asyncpg.connect(RUNTIME_URL)
    try:
        async with admin.transaction():
            await admin.execute(
                "INSERT INTO organizations(id,slug,legal_name,display_name) "
                "VALUES($1,$2,'Beta capacity test','Beta capacity test')",
                org_id, "beta-" + org_id.hex[:16],
            )
            await admin.executemany(
                "INSERT INTO users(id,oidc_issuer,oidc_subject,email,status) "
                "VALUES($1,'https://beta-test.invalid',$2,$3,'ACTIVE')",
                [
                    (member_id, "member-" + suffix, active_email),
                    (platform_admin_id, "admin-" + suffix, admin_email),
                    (invited_member_id, "awaiting-" + suffix, awaiting_email),
                ],
            )
            await admin.execute(
                "INSERT INTO memberships(organization_id,user_id,role,status) "
                "VALUES($1,$2,'ORG_ADMIN','ACTIVE')",
                org_id, member_id,
            )
            await admin.execute(
                "INSERT INTO platform_admins(user_id) VALUES($1)",
                platform_admin_id,
            )
            # Accepted private-instance invitations create INVITED memberships.
            # They still reserve a beta slot while waiting for platform approval.
            await admin.execute(
                "INSERT INTO memberships(organization_id,user_id,role,status) "
                "VALUES($1,$2,'MEMBER','INVITED')",
                org_id, invited_member_id,
            )
            await admin.execute(
                "INSERT INTO invitations(organization_id,email_normalized,role,invited_by,status,token_hash,expires_at) "
                "VALUES($1,$2,'MEMBER',$3,'PENDING',$4,now()+interval '1 day')",
                org_id, pending_email, invited_by_id, "beta-token-" + suffix,
            )

        # The runtime role can execute the SECURITY DEFINER function without
        # direct access to the global tables it reads.
        runtime_role = await runtime.fetchrow(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert runtime_role is not None
        assert runtime_role["rolsuper"] is False
        assert runtime_role["rolbypassrls"] is False

        # The function must be SECURITY DEFINER and owned by a role that can
        # bypass tenant RLS; the application role itself must remain restricted.
        function_security = await runtime.fetchrow("""
            SELECT p.prosecdef, owner.rolsuper, owner.rolbypassrls
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_roles owner ON owner.oid=p.proowner
            WHERE n.nspname='public' AND p.proname='beta_user_slot_available'
              AND p.pronargs=2
              AND p.proargtypes='25 23'::oidvector
        """)
        assert function_security is not None
        assert function_security["prosecdef"] is True
        assert (
            function_security["rolsuper"] is True
            or function_security["rolbypassrls"] is True
        )

        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)", active_email, 3
        ) is True
        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)", admin_email, 3
        ) is True
        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)", pending_email, 3
        ) is True
        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)",
            f"new-{suffix}@example.test", 3,
        ) is False
        # INVITED memberships must count even after their invitation token was consumed.
        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)",
            f"new-after-approval-{suffix}@example.test", 4,
        ) is False

        # A zero cap explicitly disables the temporary restriction.
        assert await runtime.fetchval(
            "SELECT beta_user_slot_available($1,$2)",
            f"unlimited-{suffix}@example.test", 0,
        ) is True

        async def reserve(email: str):
            conn = await asyncpg.connect(ADMIN_URL)
            try:
                async with conn.transaction():
                    allowed = await conn.fetchval(
                        "SELECT beta_user_slot_available($1,$2)", email, 5
                    )
                    if allowed:
                        await conn.execute(
                            "INSERT INTO invitations(organization_id,email_normalized,role,invited_by,status,token_hash,expires_at) "
                            "VALUES($1,$2,'MEMBER',$3,'PENDING',$4,now()+interval '1 day')",
                            org_id, email, invited_by_id, "beta-token-" + uuid.uuid4().hex,
                        )
                    return allowed
            finally:
                await conn.close()

        outcomes = await asyncio.gather(
            reserve(f"parallel-a-{suffix}@example.test"),
            reserve(f"parallel-b-{suffix}@example.test"),
        )
        assert sum(outcomes) == 1
        assert await admin.fetchval(
            "SELECT count(*) FROM invitations "
            "WHERE organization_id=$1 AND status='PENDING' AND expires_at>now()",
            org_id,
        ) == 2
    finally:
        await runtime.close()
        async with admin.transaction():
            await admin.execute(
                "DELETE FROM invitations WHERE organization_id=$1", org_id
            )
            await admin.execute(
                "DELETE FROM platform_admins WHERE user_id=$1", platform_admin_id
            )
            await admin.execute(
                "DELETE FROM organizations WHERE id=$1", org_id
            )
            await admin.execute(
                "DELETE FROM users WHERE id=ANY($1::uuid[])",
                [member_id, platform_admin_id, invited_member_id],
            )
        await admin.close()


def test_beta_capacity_sql_and_concurrent_reservations():
    asyncio.run(_run_beta_capacity_scenario())
