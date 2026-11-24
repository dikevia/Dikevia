from datetime import date

import pytest

from app.local_corpus import search_local_documents


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self.rows


def local_row(**overrides):
    row = {
        "id": "00000000-0000-0000-0000-000000000123",
        "title": "Délibération sur le temps de travail",
        "document_type": "DELIBERATION",
        "official_number": "DEL-2024-12",
        "official_url": None,
        "adopted_at": date(2023, 12, 15),
        "published_at": date(2023, 12, 20),
        "effective_from": date(2024, 1, 1),
        "effective_to": None,
        "validation_status": "VERIFIED_APPLICABLE",
        "sha256": "a" * 64,
        "extracted_sha256": "a" * 64,
        "extraction_status": "EXTRACTED",
        "collectivity_name": "Ville de Saint-Étienne",
        "collectivity_code": "VILLE_SAINT_ETIENNE",
        "relevance": 0.8,
        "excerpt": "Extrait contrôlé de la délibération.",
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_local_search_is_tenant_scoped_clean_and_validated():
    conn = FakeConn([local_row()])
    results = await search_local_documents(
        conn, "00000000-0000-0000-0000-000000000001",
        "VILLE_SAINT_ETIENNE", "temps de travail", date(2024, 6, 1)
    )
    assert len(results) == 1
    assert results[0]["source_type"] == "LOCAL_DOCUMENT"
    assert results[0]["temporal_status"] == "VERIFIED_APPLICABLE"
    assert results[0]["citation_integrity"]["valid"] is True
    sql, args = conn.calls[0]
    assert "dt.organization_id=$1::uuid" in sql
    assert "d.scan_status='CLEAN'" in sql
    assert "dv.scan_status='CLEAN'" in sql
    assert args[0] == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_local_search_marks_unverified_and_out_of_date_documents_unusable():
    conn = FakeConn([
        local_row(validation_status="COLLECTED_UNVERIFIED"),
        local_row(id="00000000-0000-0000-0000-000000000124",
                  effective_to=date(2023, 12, 31)),
    ])
    results = await search_local_documents(
        conn, "00000000-0000-0000-0000-000000000001",
        "VILLE_SAINT_ETIENNE", "temps de travail", date(2024, 6, 1)
    )
    assert results[0]["temporal_status"] == "LOCAL_VALIDATION_INCOMPLETE"
    assert results[1]["temporal_status"] == "NOT_APPLICABLE_ON_REQUESTED_DATE"


@pytest.mark.asyncio
async def test_local_search_does_not_mix_local_documents_into_national_employer():
    conn = FakeConn([local_row()])
    results = await search_local_documents(
        conn, "00000000-0000-0000-0000-000000000001",
        "NATIONAL", "temps de travail", date(2024, 6, 1)
    )
    assert results == []
    assert conn.calls == []


@pytest.mark.asyncio
async def test_local_search_refuses_hash_mismatch():
    conn = FakeConn([local_row(extracted_sha256="b" * 64)])
    results = await search_local_documents(
        conn, "00000000-0000-0000-0000-000000000001",
        "VILLE_SAINT_ETIENNE", "temps de travail", date(2024, 6, 1)
    )
    assert results[0]["citation_integrity"]["valid"] is False



def test_local_document_temporal_status_can_be_checked_at_multiple_period_dates():
    from app.local_corpus import local_document_temporal_status

    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    assert local_document_temporal_status(
        start, end, "VERIFIED_HISTORICAL", date(2024, 6, 30)
    ) == "VERIFIED_APPLICABLE"
    assert local_document_temporal_status(
        start, end, "VERIFIED_HISTORICAL", date(2025, 1, 1)
    ) == "NOT_APPLICABLE_ON_REQUESTED_DATE"
    assert local_document_temporal_status(
        None, end, "VERIFIED_APPLICABLE", date(2024, 6, 30)
    ) == "TEMPORAL_SCOPE_INCOMPLETE"


@pytest.mark.asyncio
async def test_local_search_strips_ts_headline_markup_from_evidence_excerpt():
    conn = FakeConn([
        local_row(excerpt="Extrait <b>contrôlé</b> de la <B>délibération</B>."),
    ])
    results = await search_local_documents(
        conn, "00000000-0000-0000-0000-000000000001",
        "VILLE_SAINT_ETIENNE", "temps de travail", date(2024, 6, 1)
    )
    assert results[0]["excerpt"] == "Extrait contrôlé de la délibération."
    assert results[0]["text"] == results[0]["excerpt"]
