"""Real PostgreSQL tests for the private-instance membership functions.

Run against a disposable database after schema.sql, runtime grants, migrations
010-016, and the RLS role setup. These tests are skipped without admin, runtime,
and platform-admin URLs; CI configures them on a fresh PostgreSQL service.
"""
import asyncio
import os
import uuid

import pytest

ADMIN_URL = os.getenv("TEST_DATABASE_ADMIN_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_URL")
PLATFORM_ADMIN_URL = os.getenv("TEST_PLATFORM_ADMIN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not (ADMIN_URL and RUNTIME_URL and PLATFORM_ADMIN_URL),
    reason="PostgreSQL test URLs not configured",
)


async def _run_private_membership_scenario():
    import asyncpg

    organization_id = uuid.uuid4()
    platform_admin_id = uuid.uuid4()
    active_user_ids = [uuid.uuid4() for _ in range(8)]
    invited_user_ids = [uuid.uuid4() for _ in range(2)]
    all_user_ids = [platform_admin_id, *active_user_ids, *invited_user_ids]
    admin = await asyncpg.connect(ADMIN_URL)
    runtime_a = await asyncpg.connect(RUNTIME_URL)
    runtime_b = await asyncpg.connect(RUNTIME_URL)
    platform_a = await asyncpg.connect(PLATFORM_ADMIN_URL)
    platform_b = await asyncpg.connect(PLATFORM_ADMIN_URL)
    try:
        # This test requires the disposable CI database to start without
        # pre-existing active memberships because the quota is instance-wide.
        active_before = await admin.fetchval(
            "SELECT count(*) FROM memberships WHERE status='ACTIVE'"
        )
        assert active_before == 0

        async with admin.transaction():
            await admin.execute(
                "INSERT INTO organizations(id,slug,legal_name,display_name) "
                "VALUES($1,$2,'Private test','Private test')",
                organization_id,
                "private-" + organization_id.hex[:16],
            )
            await admin.executemany(
                "INSERT INTO users(id,oidc_issuer,oidc_subject,email,status) "
                "VALUES($1,'https://private-test.invalid',$2,$3,'ACTIVE')",
                [
                    (
                        user_id,
                        "subject-" + user_id.hex,
                        f"{user_id.hex}@private-test.invalid",
                    )
                    for user_id in all_user_ids
                ],
            )
            await admin.execute(
                "INSERT INTO platform_admins(user_id) VALUES($1)",
                platform_admin_id,
            )
            await admin.execute(
                "INSERT INTO memberships(organization_id,user_id,role,status) "
                "VALUES($1,$2,'ORG_ADMIN','ACTIVE')",
                organization_id,
                platform_admin_id,
            )
            await admin.executemany(
                "INSERT INTO memberships(organization_id,user_id,role,status) "
                "VALUES($1,$2,'MEMBER',$3)",
                [
                    (organization_id, user_id, "ACTIVE")
                    for user_id in active_user_ids
                ]
                + [
                    (organization_id, user_id, "INVITED")
                    for user_id in invited_user_ids
                ],
            )

        members = await platform_a.fetch(
            "SELECT user_id,membership_status "
            "FROM private_instance_pending_members($1::uuid)",
            platform_admin_id,
        )
        assert len(members) == 11
        assert sum(row["membership_status"] == "ACTIVE" for row in members) == 9
        assert sum(row["membership_status"] == "INVITED" for row in members) == 2

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await runtime_a.fetch(
                "SELECT * FROM private_instance_pending_members($1::uuid)",
                uuid.uuid4(),
            )

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await runtime_a.fetchval(
                "SELECT private_instance_set_member_status("
                "$1::uuid,$2::uuid,$3::uuid,'ACTIVE')",
                platform_admin_id, organization_id, invited_user_ids[0],
            )

        async def activate(conn, user_id):
            return await conn.fetchval(
                "SELECT private_instance_set_member_status("
                "$1::uuid,$2::uuid,$3::uuid,'ACTIVE')",
                platform_admin_id,
                organization_id,
                user_id,
            )

        results = await asyncio.gather(
            activate(platform_a, invited_user_ids[0]),
            activate(platform_b, invited_user_ids[1]),
            return_exceptions=True,
        )
        assert sum(result is True for result in results) == 1
        failures = [result for result in results if isinstance(result, BaseException)]
        assert len(failures) == 1
        assert isinstance(failures[0], asyncpg.CheckViolationError)
        assert await admin.fetchval(
            "SELECT count(*) FROM memberships WHERE status='ACTIVE'"
        ) == 10

        remaining_invited = None
        for user_id in invited_user_ids:
            status = await admin.fetchval(
                "SELECT status FROM memberships "
                "WHERE organization_id=$1::uuid AND user_id=$2::uuid",
                organization_id,
                user_id,
            )
            if status == "INVITED":
                remaining_invited = user_id
                break
        assert remaining_invited is not None
        suspended_user = active_user_ids[0]
        assert await platform_a.fetchval(
            "SELECT private_instance_set_member_status("
            "$1::uuid,$2::uuid,$3::uuid,'SUSPENDED')",
            platform_admin_id,
            organization_id,
            suspended_user,
        )
        assert await activate(platform_a, remaining_invited)
        assert await admin.fetchval(
            "SELECT count(*) FROM memberships WHERE status='ACTIVE'"
        ) == 10
        assert await admin.fetchval(
            "SELECT status FROM memberships "
            "WHERE organization_id=$1::uuid AND user_id=$2::uuid",
            organization_id,
            suspended_user,
        ) == "SUSPENDED"
        assert await admin.fetchval(
            "SELECT count(*) FROM audit_events "
            "WHERE organization_id=$1::uuid "
            "AND event_type IN ('PRIVATE_MEMBER_APPROVED','PRIVATE_MEMBER_SUSPENDED')",
            organization_id,
        ) == 3
    finally:
        await runtime_a.close()
        await runtime_b.close()
        await platform_a.close()
        await platform_b.close()
        async with admin.transaction():
            await admin.execute(
                "DELETE FROM platform_admins WHERE user_id=ANY($1::uuid[])",
                all_user_ids,
            )
            await admin.execute(
                "DELETE FROM organizations WHERE id=$1::uuid",
                organization_id,
            )
            await admin.execute(
                "DELETE FROM users WHERE id=ANY($1::uuid[])",
                all_user_ids,
            )
        await admin.close()


def test_private_membership_cap_serializes_concurrent_approvals():
    asyncio.run(_run_private_membership_scenario())
