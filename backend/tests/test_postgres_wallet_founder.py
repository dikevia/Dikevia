"""Real PostgreSQL tests for tenant credit wallet and verified-identity founder rights."""
import asyncio
import os
import uuid

import pytest

ADMIN_URL = os.getenv("TEST_DATABASE_ADMIN_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_URL")
PLATFORM_ADMIN_URL = os.getenv("TEST_PLATFORM_ADMIN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not (ADMIN_URL and RUNTIME_URL and PLATFORM_ADMIN_URL),
    reason="Disposable PostgreSQL admin, runtime and platform-admin URLs are required",
)


async def _run_wallet_founder_scenario():
    import asyncpg

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    issuer = "https://issuer.test"
    subject = "verified-founder-" + user_id.hex
    other_subject = "ordinary-user-" + other_user_id.hex
    wallet_key = "ci-wallet-" + uuid.uuid4().hex
    debit_key = "ci-debit-" + uuid.uuid4().hex
    admin = await asyncpg.connect(ADMIN_URL)
    runtime = await asyncpg.connect(RUNTIME_URL)
    platform = await asyncpg.connect(PLATFORM_ADMIN_URL)

    try:
        async with admin.transaction():
            await admin.execute(
                "INSERT INTO organizations(id,slug,legal_name,display_name) VALUES($1,$2,'CI wallet','CI wallet')",
                org_id, "ci-wallet-" + org_id.hex[:12],
            )
            await admin.execute(
                """INSERT INTO users(id,oidc_issuer,oidc_subject,email,status)
                   VALUES($1,$2,$3,$4,'ACTIVE'),($5,$2,$6,$7,'ACTIVE')""",
                user_id, issuer, subject, "founder-ci@example.test",
                other_user_id, other_subject, "ordinary-ci@example.test",
            )
            await admin.execute(
                """INSERT INTO memberships(organization_id,user_id,role,status)
                   VALUES($1,$2,'ORG_ADMIN','ACTIVE'),($1,$3,'MEMBER','ACTIVE')""",
                org_id, user_id, other_user_id,
            )
            await admin.execute("INSERT INTO platform_admins(user_id) VALUES($1)", user_id)

        granted_user = await platform.fetchval(
            "SELECT platform_admin_grant_founder_entitlement($1,$2,$3)",
            user_id, user_id, "Verified founder account permanent premium access",
        )
        assert granted_user == user_id
        entitlements = await platform.fetch(
            "SELECT user_id,note,revoked_at FROM platform_admin_list_founder_entitlements($1)",
            user_id,
        )
        assert len(entitlements) == 1 and entitlements[0]["user_id"] == user_id
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await platform.fetch("SELECT user_id FROM platform_founder_entitlements")

        first_grant = await platform.fetchrow(
            """SELECT * FROM wallet_admin_grant_entry(
                $1,$2,100,'MONTHLY_ALLOCATION',$3,'CI initial allocation'
            )""",
            user_id, org_id, wallet_key,
        )
        assert first_grant["applied"] is True
        assert first_grant["current_balance"] == 100
        replay_grant = await platform.fetchrow(
            """SELECT * FROM wallet_admin_grant_entry(
                $1,$2,100,'MONTHLY_ALLOCATION',$3,'CI initial allocation'
            )""",
            user_id, org_id, wallet_key,
        )
        assert replay_grant["applied"] is False
        assert replay_grant["ledger_entry_id"] == first_grant["ledger_entry_id"]
        with pytest.raises(asyncpg.InvalidParameterValueError):
            await platform.fetchrow(
                """SELECT * FROM wallet_admin_grant_entry(
                    $1,$2,99,'MONTHLY_ALLOCATION',$3,'Changed allocation'
                )""",
                user_id, org_id, wallet_key,
            )

        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_id))
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id))
            await runtime.execute("SELECT set_config('app.oidc_issuer',$1,true)", issuer)
            await runtime.execute("SELECT set_config('app.oidc_subject',$1,true)", subject)

            assert await runtime.fetchval(
                """SELECT EXISTS(
                    SELECT 1 FROM platform_founder_entitlements
                    WHERE user_id=$1 AND revoked_at IS NULL
                )""",
                user_id,
            ) is True

            debit = await runtime.fetchrow(
                "SELECT * FROM wallet_apply_entry($1,-30,'USAGE_DEBIT',$2,'CI usage')",
                org_id, debit_key,
            )
            assert debit["applied"] is True and debit["current_balance"] == 70
            replay_debit = await runtime.fetchrow(
                "SELECT * FROM wallet_apply_entry($1,-30,'USAGE_DEBIT',$2,'CI usage')",
                org_id, debit_key,
            )
            assert replay_debit["applied"] is False
            assert replay_debit["ledger_entry_id"] == debit["ledger_entry_id"]
            insufficient = await runtime.fetchrow(
                "SELECT * FROM wallet_apply_entry($1,-100,'USAGE_DEBIT',$2,'Insufficient balance')",
                org_id, "ci-reject-" + uuid.uuid4().hex,
            )
            assert insufficient["applied"] is False
            assert insufficient["current_balance"] == 70
            with pytest.raises(asyncpg.InvalidParameterValueError):
                await runtime.fetchrow(
                    "SELECT * FROM wallet_apply_entry($1,50,'USAGE_DEBIT',$2,'Positive debit forgery')",
                    org_id, "ci-positive-" + uuid.uuid4().hex,
                )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.fetchrow(
                    """SELECT * FROM wallet_admin_grant_entry(
                        $1,$2,50,'MONTHLY_ALLOCATION',$3,'Forged runtime grant'
                    )""",
                    user_id, org_id, "ci-forged-" + uuid.uuid4().hex,
                )
            assert await runtime.fetchval(
                "SELECT balance FROM credit_accounts WHERE organization_id=$1", org_id
            ) == 70
            assert await runtime.fetchval(
                "SELECT count(*) FROM credit_ledger_entries WHERE organization_id=$1", org_id
            ) == 2

            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(other_user_id))
            await runtime.execute("SELECT set_config('app.oidc_subject',$1,true)", other_subject)
            assert await runtime.fetchval(
                "SELECT count(*) FROM platform_founder_entitlements"
            ) == 0
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await runtime.fetchval(
                    "SELECT platform_admin_grant_founder_entitlement($1,$2,$3)",
                    user_id, other_user_id, "Forged runtime founder grant",
                )

        assert await platform.fetchval(
            "SELECT platform_admin_revoke_founder_entitlement($1,$2)", user_id, user_id
        ) is True
        assert await platform.fetchval(
            "SELECT platform_admin_revoke_founder_entitlement($1,$2)", user_id, user_id
        ) is False

        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_id))
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_id))
            await runtime.execute("SELECT set_config('app.oidc_issuer',$1,true)", issuer)
            await runtime.execute("SELECT set_config('app.oidc_subject',$1,true)", subject)
            assert await runtime.fetchval(
                """SELECT EXISTS(
                    SELECT 1 FROM platform_founder_entitlements
                    WHERE user_id=$1 AND revoked_at IS NULL
                )""",
                user_id,
            ) is False
    finally:
        await runtime.close()
        await platform.close()
        async with admin.transaction():
            await admin.execute("DELETE FROM platform_audit_events WHERE actor_user_id=$1", user_id)
            await admin.execute("DELETE FROM platform_admins WHERE user_id=$1", user_id)
            await admin.execute("DELETE FROM organizations WHERE id=$1", org_id)
            await admin.execute("DELETE FROM users WHERE id IN ($1,$2)", user_id, other_user_id)
        await admin.close()


def test_postgresql_wallet_and_founder_entitlements_are_isolated_and_atomic():
    asyncio.run(_run_wallet_founder_scenario())
