import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from scripts.purge_private_conversations import (
    parse_args,
    parse_cutoff,
    run_purge,
    validate_confirmation,
)


def test_retention_cutoff_requires_explicit_timezone():
    cutoff = parse_cutoff("2026-01-01T00:00:00Z")
    assert cutoff.isoformat() == "2026-01-01T00:00:00+00:00"


def test_retention_cutoff_rejects_timezone_naive_value():
    with pytest.raises(Exception, match="fuseau horaire"):
        parse_cutoff("2026-01-01T00:00:00")


def test_retention_cutoff_rejects_invalid_iso_value():
    with pytest.raises(Exception, match="ISO-8601"):
        parse_cutoff("pas-une-date")


def test_purge_requires_two_explicit_confirmation_flags():
    with pytest.raises(ValueError, match="--confirm-delete"):
        validate_confirmation(True, False)
    with pytest.raises(ValueError, match="--execute"):
        validate_confirmation(False, True)
    validate_confirmation(False, False)
    validate_confirmation(True, True)


def test_cli_requires_explicit_cutoff():
    with pytest.raises(SystemExit) as error:
        parse_args([])
    assert error.value.code == 2


ADMIN_URL = os.getenv("TEST_DATABASE_ADMIN_URL")


@pytest.mark.skipif(not ADMIN_URL, reason="PostgreSQL admin test URL not configured")
def test_postgresql_retention_purge_dry_run_and_cascade():
    asyncio.run(_run_postgresql_retention_scenario())


async def _run_postgresql_retention_scenario():
    import asyncpg

    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_conversation_id = uuid.uuid4()
    recent_conversation_id = uuid.uuid4()
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        async with admin.transaction():
            await admin.execute(
                "INSERT INTO organizations(id,slug,legal_name,display_name) VALUES($1,$2,$3,$4)",
                organization_id, "retention-" + organization_id.hex[:12],
                "Organisation test purge", "Organisation test purge",
            )
            await admin.execute(
                """INSERT INTO users(id,oidc_issuer,oidc_subject,email,status)
                   VALUES($1,'https://retention.test',$2,$3,'ACTIVE')""",
                user_id, "subject-" + user_id.hex, "retention-" + user_id.hex + "@example.test",
            )
            await admin.execute(
                """INSERT INTO chat_conversations(id,organization_id,user_id,title,updated_at)
                   VALUES($1,$2,$3,'Conversation ancienne',now()-interval '90 days'),
                         ($4,$2,$3,'Conversation récente',now())""",
                old_conversation_id, organization_id, user_id, recent_conversation_id,
            )
            await admin.execute(
                """INSERT INTO chat_messages(organization_id,conversation_id,user_id,role,content)
                   VALUES($1,$2,$3,'user','Message à purger')""",
                organization_id, old_conversation_id, user_id,
            )
            await admin.execute(
                """INSERT INTO legal_dossiers(organization_id,conversation_id,user_id,content)
                   VALUES($1,$2,$3,'{"title":"Dossier à purger"}'::jsonb)""",
                organization_id, old_conversation_id, user_id,
            )

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        preview = await run_purge(ADMIN_URL, cutoff, execute=False)
        assert preview["mode"] == "dry_run"
        assert preview["conversations"] == 1
        assert await admin.fetchval(
            "SELECT count(*) FROM chat_conversations WHERE id=$1", old_conversation_id
        ) == 1

        result = await run_purge(ADMIN_URL, cutoff, execute=True)
        assert result["mode"] == "execute"
        assert result["conversations"] == 1
        assert await admin.fetchval(
            "SELECT count(*) FROM chat_conversations WHERE id=$1", old_conversation_id
        ) == 0
        assert await admin.fetchval(
            "SELECT count(*) FROM chat_messages WHERE conversation_id=$1", old_conversation_id
        ) == 0
        assert await admin.fetchval(
            "SELECT count(*) FROM legal_dossiers WHERE conversation_id=$1", old_conversation_id
        ) == 0
        assert await admin.fetchval(
            "SELECT count(*) FROM chat_conversations WHERE id=$1", recent_conversation_id
        ) == 1
    finally:
        async with admin.transaction():
            await admin.execute("DELETE FROM organizations WHERE id=$1", organization_id)
            await admin.execute("DELETE FROM users WHERE id=$1", user_id)
        await admin.close()
