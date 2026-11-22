"""Real PostgreSQL RLS tests.

Run only against a disposable test database after `database/schema.sql`,
`database/grant_runtime_permissions.sql`, and migrations 010/011/012/013/014 have been applied. Required env:
  TEST_DATABASE_ADMIN_URL: migration/owner connection (fixture setup/cleanup)
  TEST_DATABASE_URL: non-owner runtime connection (RLS assertions)

These tests are deliberately skipped when URLs are absent; static tests are
not a substitute for executing them against PostgreSQL.
"""
import asyncio
import os
import uuid
from datetime import date

import pytest

ADMIN_URL = os.getenv("TEST_DATABASE_ADMIN_URL")
RUNTIME_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not (ADMIN_URL and RUNTIME_URL), reason="PostgreSQL test URLs not configured")


async def _run_isolation_scenario():
    import asyncpg

    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    user_a, user_b, user_a2 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    coll_a, coll_b = uuid.uuid4(), uuid.uuid4()
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()
    token_a, token_b = "hash-a-" + uuid.uuid4().hex, "hash-b-" + uuid.uuid4().hex
    usage_request_id = uuid.uuid4()
    admin = await asyncpg.connect(ADMIN_URL)
    runtime = await asyncpg.connect(RUNTIME_URL)
    try:
        runtime_role = await runtime.fetchrow(
            "SELECT r.rolsuper, r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user"
        )
        assert runtime_role is not None
        assert runtime_role["rolsuper"] is False
        assert runtime_role["rolbypassrls"] is False
        admin_role = await admin.fetchrow(
            "SELECT r.rolsuper, r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user"
        )
        assert admin_role is not None and (admin_role["rolsuper"] or admin_role["rolbypassrls"])

        async with admin.transaction():
            await admin.execute("INSERT INTO organizations(id,slug,legal_name,display_name) VALUES($1,$2,$3,$4),($5,$6,$7,$8)",
                org_a, "rls-a-"+org_a.hex[:10], "Org A", "Org A", org_b, "rls-b-"+org_b.hex[:10], "Org B", "Org B")
            await admin.execute("INSERT INTO users(id,oidc_issuer,oidc_subject,email,status) VALUES($1,'https://issuer.test',$2,$3,'ACTIVE'),($4,'https://issuer.test',$5,$6,'ACTIVE')",
                user_a, "sub-a-"+user_a.hex, "a@example.test", user_b, "sub-b-"+user_b.hex, "b@example.test")
            await admin.execute("INSERT INTO users(id,oidc_issuer,oidc_subject,email,status) VALUES($1,'https://issuer.test',$2,$3,'ACTIVE')", user_a2, "sub-a2-"+user_a2.hex, "a2@example.test")
            await admin.execute("INSERT INTO memberships(organization_id,user_id,role,status) VALUES($1,$2,'ORG_ADMIN','ACTIVE'),($3,$4,'ORG_ADMIN','ACTIVE'),($1,$5,'MEMBER','ACTIVE')", org_a,user_a,org_b,user_b,user_a2)
            conversation_a, conversation_a2 = uuid.uuid4(), uuid.uuid4()
            await admin.execute("INSERT INTO chat_conversations(id,organization_id,user_id,title) VALUES($1,$2,$3,'Conversation A'),($4,$2,$5,'Conversation A2')", conversation_a,org_a,user_a,conversation_a2,user_a2)
            await admin.execute("INSERT INTO chat_messages(organization_id,conversation_id,user_id,role,content) VALUES($1,$2,$3,'user','Question privée A'),($1,$4,$5,'user','Question privée A2')", org_a,conversation_a,user_a,conversation_a2,user_a2)
            await admin.execute("INSERT INTO legal_dossiers(organization_id,conversation_id,user_id,content) VALUES($1,$2,$3,'{\"title\":\"Dossier A\"}'::jsonb),($1,$4,$5,'{\"title\":\"Dossier A2\"}'::jsonb)", org_a,conversation_a,user_a,conversation_a2,user_a2)
            await admin.execute("INSERT INTO collectivities(id,organization_id,code,name) VALUES($1,$2,'TEST','Test A'),($3,$4,'TEST','Test B')", coll_a,org_a,coll_b,org_b)
            await admin.execute("INSERT INTO documents(id,organization_id,collectivity_id,title,document_type,validation_status) VALUES($1,$2,$3,'Doc A','REGULATION','COLLECTED_UNVERIFIED'),($4,$5,$6,'Doc B','REGULATION','COLLECTED_UNVERIFIED')", doc_a,org_a,coll_a,doc_b,org_b,coll_b)
            await admin.execute("INSERT INTO document_versions(organization_id,document_id,version_number,sha256) VALUES($1,$2,1,$3),($4,$5,1,$6)", org_a,doc_a,"a"*64,org_b,doc_b,"b"*64)
            await admin.execute("INSERT INTO document_text(organization_id,document_id,version_number,sha256,extracted_text,extraction_status) VALUES($1,$2,1,$3,'texte confidentiel organisation A','EXTRACTED'),($4,$5,1,$6,'texte confidentiel organisation B','EXTRACTED')", org_a,doc_a,"a"*64,org_b,doc_b,"b"*64)
            await admin.execute("INSERT INTO invitations(organization_id,email_normalized,role,invited_by,status,token_hash,expires_at) VALUES($1,'a@example.test','MEMBER',$2,'PENDING',$3,now()+interval '1 day'),($4,'b@example.test','MEMBER',$5,'PENDING',$6,now()+interval '1 day')", org_a,user_a,token_a,org_b,user_b,token_b)
            await admin.execute("INSERT INTO organization_settings(organization_id) VALUES($1),($2)", org_a, org_b)
            await admin.execute("INSERT INTO audit_events(organization_id,event_type) VALUES($1,'SEED_A'),($2,'SEED_B')", org_a, org_b)
            await admin.execute("""INSERT INTO stripe_invoice_records(stripe_invoice_id,organization_id,invoice_number,status,currency,amount_due,amount_paid)
                VALUES($1,$2,'INV-A','paid','eur',1500,1500),($3,$4,'INV-B','paid','eur',8000,8000)""",
                "in_test_"+uuid.uuid4().hex, org_a, "in_test_"+uuid.uuid4().hex, org_b)

        # Tenant A sees only its own documents and cannot update tenant B's row.
        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_a))
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_a))
            from app.rate_limit import consume_chat_request
            first = await consume_chat_request(runtime, str(org_a), str(user_a), 2)
            second = await consume_chat_request(runtime, str(org_a), str(user_a), 2)
            third = await consume_chat_request(runtime, str(org_a), str(user_a), 2)
            assert first.allowed and second.allowed and not third.allowed
            assert third.request_count == 3
            await runtime.execute("""INSERT INTO ai_usage_events(
                request_id,organization_id,user_id,provider,model,prompt_tokens,
                completion_tokens,total_tokens,outcome)
                VALUES($1,$2,$3,'openai_compatible','test-model',100,25,125,'ANSWERED')""",
                usage_request_id, org_a, user_a)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute("""INSERT INTO ai_usage_events(
                        request_id,organization_id,user_id,provider,model,outcome)
                        VALUES($1,$2,$3,'openai_compatible','test-model','ANSWERED')""",
                        uuid.uuid4(), org_b, user_b)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.fetch("SELECT request_id FROM ai_usage_events")
            conversations = await runtime.fetch("SELECT id,title FROM chat_conversations")
            assert {r["id"] for r in conversations} == {conversation_a}
            own_messages = await runtime.fetch("SELECT content FROM chat_messages")
            assert [r["content"] for r in own_messages] == ["Question privée A"]
            own_dossiers = await runtime.fetch("SELECT content->>'title' AS title FROM legal_dossiers")
            assert [r["title"] for r in own_dossiers] == ["Dossier A"]
            # A different user in the same tenant cannot read or mutate this owner's records.
            assert await runtime.fetch("SELECT id FROM chat_messages") != []
            assert await runtime.fetchval("SELECT count(*) FROM chat_messages WHERE conversation_id=$1", conversation_a2) == 0
            assert await runtime.fetchval("SELECT count(*) FROM chat_conversations WHERE id=$1", conversation_a2) == 0
            assert await runtime.execute("UPDATE chat_conversations SET title='forged' WHERE id=$1", conversation_a2) == "UPDATE 0"
            assert await runtime.execute("DELETE FROM chat_messages WHERE conversation_id=$1", conversation_a2) == "DELETE 0"
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute("INSERT INTO legal_dossiers(organization_id,conversation_id,user_id,content) VALUES($1,$2,$3,'{}'::jsonb)", org_a,conversation_a2,user_a)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute("INSERT INTO chat_messages(organization_id,conversation_id,user_id,role,content) VALUES($1,$2,$3,'user','tentative de falsification')", org_a,conversation_a2,user_a)
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_a2))
            second_user_conversations = await runtime.fetch("SELECT id FROM chat_conversations")
            assert {r["id"] for r in second_user_conversations} == {conversation_a2}
            second_user_dossiers = await runtime.fetch("SELECT content->>'title' AS title FROM legal_dossiers")
            assert [r["title"] for r in second_user_dossiers] == ["Dossier A2"]
            second_user_messages = await runtime.fetch("SELECT content FROM chat_messages")
            assert [r["content"] for r in second_user_messages] == ["Question privée A2"]
            assert await runtime.fetchval("SELECT count(*) FROM chat_messages WHERE conversation_id=$1", conversation_a) == 0
            assert await runtime.fetchval("SELECT count(*) FROM legal_dossiers WHERE conversation_id=$1", conversation_a) == 0
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_a))
            rows = await runtime.fetch("SELECT id,title FROM documents ORDER BY title")
            assert {r['id'] for r in rows} == {doc_a}
            hidden = await runtime.fetchval("SELECT count(*) FROM documents WHERE id=$1", doc_b)
            assert hidden == 0
            own_versions = await runtime.fetch("SELECT document_id,version_number FROM document_versions")
            assert {(r["document_id"], r["version_number"]) for r in own_versions} == {(doc_a, 1)}
            assert await runtime.fetchval("SELECT count(*) FROM document_versions WHERE document_id=$1", doc_b) == 0
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute(
                        "INSERT INTO document_versions(organization_id,document_id,version_number,sha256) VALUES($1,$2,2,$3)",
                        org_b, doc_b, "d"*64,
                    )
            indexed = await runtime.fetch("SELECT document_id,extracted_text FROM document_text")
            assert {r["document_id"] for r in indexed} == {doc_a}
            assert "organisation B" not in indexed[0]["extracted_text"]
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute("INSERT INTO document_text(organization_id,document_id,version_number,sha256,extracted_text,extraction_status) VALUES($1,$2,1,$3,'forged','EXTRACTED')", org_b,doc_b,"c"*64)
            membership_orgs = await runtime.fetch("SELECT organization_id FROM memberships")
            assert {r["organization_id"] for r in membership_orgs} == {org_a}
            setting_orgs = await runtime.fetch("SELECT organization_id FROM organization_settings")
            assert {r["organization_id"] for r in setting_orgs} == {org_a}
            # Audit history is intentionally write-only for the runtime API role.
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.fetch("SELECT organization_id FROM audit_events")
            invoice_rows = await runtime.fetch("SELECT organization_id,amount_paid FROM stripe_invoice_records")
            assert len(invoice_rows) == 1 and invoice_rows[0]["organization_id"] == org_a
            foreign_invoice = await runtime.fetchval("SELECT count(*) FROM stripe_invoice_records WHERE organization_id=$1", org_b)
            assert foreign_invoice == 0
            # INSERT is granted for audit events, but a forged foreign tenant key
            # must be rejected by the RLS WITH CHECK policy.
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with runtime.transaction():
                    await runtime.execute(
                        "INSERT INTO audit_events(organization_id,event_type) VALUES($1,'RLS_FORGED_TENANT')",
                        org_b,
                    )
            # The rate-limit ledger is invisible across tenant boundaries.
            await runtime.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_b))
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_b))
            foreign_bucket_count = await runtime.fetchval("SELECT count(*) FROM chat_rate_limit_buckets")
            assert foreign_bucket_count == 0
            own_bucket = await consume_chat_request(runtime, str(org_b), str(user_b), 2)

        # The owner can delete their conversation; database cascades remove messages and dossier.
        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_a))
            await runtime.execute("SELECT set_config('app.current_user_id',$1,true)", str(user_a))
            assert await runtime.execute("DELETE FROM chat_conversations WHERE id=$1", conversation_a) == "DELETE 1"

        cascade_counts = await admin.fetchrow(
            """SELECT
                (SELECT count(*) FROM chat_messages WHERE conversation_id=$1) AS messages,
                (SELECT count(*) FROM legal_dossiers WHERE conversation_id=$1) AS dossiers""",
            conversation_a)
        assert cascade_counts["messages"] == 0
        assert cascade_counts["dossiers"] == 0

        usage_row = await admin.fetchrow(
            "SELECT organization_id,user_id,prompt_tokens,completion_tokens,total_tokens FROM ai_usage_events WHERE request_id=$1",
            usage_request_id)
        assert usage_row is not None
        assert usage_row["organization_id"] == org_a and usage_row["user_id"] == user_a
        assert (usage_row["prompt_tokens"],usage_row["completion_tokens"],usage_row["total_tokens"]) == (100,25,125)

        # No tenant context means no tenant data.
        async with runtime.transaction():
            rows = await runtime.fetch("SELECT id FROM documents")
            assert rows == []

        # A verified identity context exposes only that identity, not the global directory.
        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.oidc_issuer','https://issuer.test',true)")
            await runtime.execute("SELECT set_config('app.oidc_subject',$1,true)", "sub-a-"+user_a.hex)
            users = await runtime.fetch("SELECT id FROM users")
            assert {r['id'] for r in users} == {user_a}
            admins = await runtime.fetch("SELECT user_id FROM platform_admins")
            assert admins == []

        # The invitation lookup exception is bound to one exact hash only.
        async with runtime.transaction():
            await runtime.execute("SELECT set_config('app.invitation_token_hash',$1,true)", token_a)
            invitations = await runtime.fetch("SELECT token_hash FROM invitations")
            assert {r['token_hash'] for r in invitations} == {token_a}
    finally:
        await runtime.close()
        # Admin URL should be a disposable test DB owner/superuser so it can
        # remove fixture rows even when FORCE ROW LEVEL SECURITY is enabled.
        async with admin.transaction():
            await admin.execute("DELETE FROM organizations WHERE id IN ($1,$2)", org_a, org_b)
            await admin.execute("DELETE FROM users WHERE id IN ($1,$2,$3)", user_a, user_b, user_a2)
        await admin.close()


def test_postgresql_rls_isolation_between_two_organizations():
    asyncio.run(_run_isolation_scenario())


async def _run_concurrent_tenant_isolation_scenario(tenant_count: int = 12):
    """Exercise simultaneous tenant-scoped reads with one DB connection per tenant."""
    import asyncpg

    org_ids = [uuid.uuid4() for _ in range(tenant_count)]
    user_ids = [uuid.uuid4() for _ in range(tenant_count)]
    collectivity_ids = [uuid.uuid4() for _ in range(tenant_count)]
    document_ids = [uuid.uuid4() for _ in range(tenant_count)]
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        async with admin.transaction():
            await admin.executemany(
                "INSERT INTO organizations(id,slug,legal_name,display_name) VALUES($1,$2,$3,$4)",
                [(org_ids[i], f"parallel-{org_ids[i].hex[:12]}", f"Syndicat {i}", f"Syndicat {i}") for i in range(tenant_count)],
            )
            await admin.executemany(
                "INSERT INTO users(id,oidc_issuer,oidc_subject,email,status) VALUES($1,'https://parallel-issuer.test',$2,$3,'ACTIVE')",
                [(user_ids[i], f"sub-{user_ids[i].hex}", f"parallel-{i}@example.test") for i in range(tenant_count)],
            )
            await admin.executemany(
                "INSERT INTO memberships(organization_id,user_id,role,status) VALUES($1,$2,'ORG_ADMIN','ACTIVE')",
                list(zip(org_ids, user_ids)),
            )
            await admin.executemany(
                "INSERT INTO collectivities(id,organization_id,code,name) VALUES($1,$2,'TEST','Collectivité test')",
                list(zip(collectivity_ids, org_ids)),
            )
            await admin.executemany(
                "INSERT INTO documents(id,organization_id,collectivity_id,title,document_type,validation_status) VALUES($1,$2,$3,$4,'REGULATION','COLLECTED_UNVERIFIED')",
                [(document_ids[i], org_ids[i], collectivity_ids[i], f"Document privé {i}") for i in range(tenant_count)],
            )

        async def assert_one_tenant(index: int):
            conn = await asyncpg.connect(RUNTIME_URL)
            try:
                async with conn.transaction():
                    await conn.execute("SELECT set_config('app.current_org_id',$1,true)", str(org_ids[index]))
                    rows = await conn.fetch("SELECT id,organization_id FROM documents")
                    assert {row["id"] for row in rows} == {document_ids[index]}
                    assert {row["organization_id"] for row in rows} == {org_ids[index]}
                    foreign_count = await conn.fetchval(
                        "SELECT count(*) FROM documents WHERE id=$1", document_ids[(index + 1) % tenant_count]
                    )
                    assert foreign_count == 0
            finally:
                await conn.close()

        await asyncio.gather(*(assert_one_tenant(i) for i in range(tenant_count)))
    finally:
        async with admin.transaction():
            await admin.execute("DELETE FROM organizations WHERE id=ANY($1::uuid[])", org_ids)
            await admin.execute("DELETE FROM users WHERE id=ANY($1::uuid[])", user_ids)
        await admin.close()


def test_postgresql_rls_concurrent_isolation_across_twelve_organizations():
    asyncio.run(_run_concurrent_tenant_isolation_scenario())


async def _run_administrative_case_law_search_sql_scenario():
    import asyncpg
    from app.legal_corpus import search_legal_corpus, upsert_legal_document

    source_id = "CI_ADMIN_CASELAW_" + uuid.uuid4().hex
    version_key = "ci-version-" + uuid.uuid4().hex
    paragraphs = [
        (
            "Le Conseil d'État examine les conditions de travail d'un agent territorial. "
            "La durée du temps de travail et l'organisation du service sont discutées. "
            "Les pièces du dossier décrivent les fonctions exercées par l'agent public. "
        ) * 3
        for _ in range(28)
    ]
    paragraphs.append(
        "MARQUEUR_FINAL_DECISION_CI Ce dernier passage du texte intégral ne reprend "
        "pas les termes de la requête et permet de vérifier l'ajout du véritable "
        "dernier fragment de la décision."
    )
    full_text = "\\n".join(paragraphs)
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        item = {
            "source_type": "OTHER_OFFICIAL",
            "source_id": source_id,
            "title": "Décision administrative de test — agent territorial et temps de travail",
            "document_kind": "ADMIN_CASELAW",
            "official_number": "CI-" + uuid.uuid4().hex[:12],
            "jurisdiction": "Conseil d'État",
            "publisher": "Justice administrative",
            "official_url": "https://opendata.justice-administrative.fr/",
            "signature_date": date(2025, 2, 10),
            "status": "UNKNOWN",
            "source_status": "OFFICIAL_XML_IMPORTED",
            "raw_metadata": {
                "source_license": "Licence Ouverte version 2.0",
                "publication_code": "C",
                "source_xml_sha256": "a" * 64,
                "solution": "Décision de test",
            },
            "full_text": full_text,
            "version_key": version_key,
            "version_status": "UNKNOWN",
            "raw_version_payload": {"integration_test": True},
        }
        # Importing the same official decision twice must update the same
        # document/version and replace, not duplicate, its indexed chunks.
        await upsert_legal_document(admin, item)
        await upsert_legal_document(admin, item)
        persisted = await admin.fetchrow("""
            SELECT count(DISTINCT d.id) AS documents,
                   count(DISTINCT v.id) AS versions,
                   count(c.id) AS chunks
            FROM legal_documents d
            LEFT JOIN legal_document_versions v ON v.document_id=d.id
            LEFT JOIN legal_chunks c ON c.version_id=v.id
            WHERE d.source_type='OTHER_OFFICIAL' AND d.source_id=$1
        """, source_id)
        from app.legal_corpus import split_text
        assert persisted["documents"] == 1
        assert persisted["versions"] == 1
        assert persisted["chunks"] == len(split_text(full_text))

        results = await search_legal_corpus(
            admin, "agent territorial temps de travail", date(2026, 11, 21), limit=6,
        )
        item = next(result for result in results if result["source_id"] == source_id)
        assert item["document_kind"] == "ADMIN_CASELAW"
        assert item["temporal_status"] == "DECISION_AVAILABLE_BY_REQUESTED_DATE"
        assert item["citation_integrity"]["text_hash_verified"] is True
        assert item["citation_integrity"]["valid"] is True
        assert item["retrieval_scope"] == (
            "TOP_RELEVANT_PASSAGE_AND_FINAL_CHUNK_FROM_HASH_VERIFIED_FULL_TEXT"
        )
        assert "MARQUEUR_FINAL_DECISION_CI" in item["excerpt"]
    finally:
        await admin.execute(
            "DELETE FROM legal_documents WHERE source_type='OTHER_OFFICIAL' AND source_id=$1",
            source_id,
        )
        await admin.close()


def test_postgresql_executes_administrative_case_law_search_cte():
    asyncio.run(_run_administrative_case_law_search_sql_scenario())


async def _run_service_public_guidance_corpus_scenario():
    import asyncpg
    from app.legal_corpus import search_legal_corpus, upsert_legal_document

    source_id = "CI_SERVICE_PUBLIC_" + uuid.uuid4().hex
    admin = await asyncpg.connect(ADMIN_URL)
    try:
        full_text = (
            "Le temps partiel pour raison thérapeutique permet à un agent public "
            "de reprendre ou de maintenir son activité dans des conditions adaptées. "
            "La présente fiche décrit les démarches administratives et les règles "
            "générales applicables selon le versant de la fonction publique."
        )
        await upsert_legal_document(admin, {
            "source_type": "SERVICE_PUBLIC_PART",
            "source_id": source_id,
            "title": "Temps partiel thérapeutique — fiche administrative de test",
            "document_kind": "ADMIN_GUIDANCE",
            "publisher": "Service-Public.gouv.fr / DILA",
            "official_url": "https://www.service-public.gouv.fr/particuliers/vosdroits/F12345",
            "status": "UNKNOWN",
            "source_status": "IMPORTED_UNVERIFIED",
            "raw_metadata": {
                "corpus_role": "ADMINISTRATIVE_GUIDANCE_NOT_PRIMARY_LEGAL_AUTHORITY",
                "license": "fr-lo",
                "attribution": "Service-Public.gouv.fr / DILA",
            },
            "full_text": full_text,
            "version_key": "ci-" + uuid.uuid4().hex,
            "version_status": "UNKNOWN",
            "valid_from": None,
            "valid_to": None,
            "raw_version_payload": {"integration_test": True},
        })
        results = await search_legal_corpus(
            admin, "temps partiel thérapeutique agent public", date(2026, 11, 22), limit=10,
        )
        item = next(result for result in results if result["source_id"] == source_id)
        assert item["document_kind"] == "ADMIN_GUIDANCE"
        assert item["source_status"] == "IMPORTED_UNVERIFIED"
        assert item["official_source"] is False
        assert item["temporal_status"] == "TEMPORAL_SCOPE_INCOMPLETE"
        assert item["official_url"].endswith("/F12345")
        assert item["citation_integrity"]["text_hash_verified"] is True
        assert item["citation_integrity"]["valid"] is True
    finally:
        await admin.execute(
            "DELETE FROM legal_documents WHERE source_type='SERVICE_PUBLIC_PART' AND source_id=$1",
            source_id,
        )
        await admin.close()


def test_postgresql_indexes_service_public_guidance_without_promoting_it_to_law():
    asyncio.run(_run_service_public_guidance_corpus_scenario())
