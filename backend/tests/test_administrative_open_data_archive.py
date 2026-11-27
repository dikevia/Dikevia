from datetime import date
import importlib.util
from pathlib import Path

import pytest

from app.legal_ingestion import administrative_open_data_archive_url, filter_administrative_open_data_items


@pytest.mark.parametrize(
    ("court", "year", "month", "expected"),
    [
        ("CE", 2026, 10, "https://opendata.justice-administrative.fr/DCE/2026/10/CE_202610.zip"),
        ("CE", 2021, 6, "https://opendata.justice-administrative.fr/DCE/2021/06/CE_202106.zip"),
        ("CAA", 2026, 9, "https://opendata.justice-administrative.fr/DCA/2026/09/CAA_202609.zip"),
        ("TA", 2026, 8, "https://opendata.justice-administrative.fr/DTA/2026/08/TA_202608.zip"),
    ],
)
def test_monthly_archive_url_uses_only_official_fixed_host(court, year, month, expected):
    assert administrative_open_data_archive_url(
        court, year, month, today=date(2026, 11, 25)
    ) == expected


@pytest.mark.parametrize(
    ("court", "year", "month"),
    [
        ("OTHER", 2026, 10),
        ("CE", 2021, 5),
        ("CAA", 2022, 2),
        ("TA", 2022, 5),
        ("TA", 2026, 13),
        ("TA", 2027, 1),
    ],
)
def test_monthly_archive_url_rejects_unknown_or_unavailable_periods(court, year, month):
    with pytest.raises(ValueError):
        administrative_open_data_archive_url(
            court, year, month, today=date(2026, 11, 25)
        )


@pytest.mark.parametrize("year, month", [(True, 1), (2026, False), (2026, 1.5)])
def test_monthly_archive_url_rejects_non_integer_date_parts(year, month):
    with pytest.raises(ValueError):
        administrative_open_data_archive_url("TA", year, month, today=date(2026, 11, 25))



def test_fpt_archive_filter_keeps_only_fpt_and_explicitly_common_decisions():
    items = [
        {"source_id": "fpt", "raw_metadata": {"public_service_scope": "FPT"}},
        {"source_id": "common", "raw_metadata": {"public_service_scope": "COMMON_PUBLIC_SERVICE"}},
        {"source_id": "fpe", "raw_metadata": {"public_service_scope": "FPE"}},
        {"source_id": "fph", "raw_metadata": {"public_service_scope": "FPH"}},
        {"source_id": "general", "raw_metadata": {"public_service_scope": "GENERAL_PUBLIC_SERVICE"}},
        {"source_id": "unknown", "raw_metadata": {}},
    ]
    selected = filter_administrative_open_data_items(items, versant="FPT")
    assert [item["source_id"] for item in selected] == ["fpt", "common"]


def test_open_data_scope_filter_rejects_unknown_versant():
    with pytest.raises(ValueError):
        filter_administrative_open_data_items([], versant="GENERAL")


def _load_archive_importer():
    script = Path(__file__).resolve().parents[2] / "scripts/import_administrative_open_data_archives.py"
    spec = importlib.util.spec_from_file_location("import_administrative_open_data_archives_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_archive_importer_month_range_is_inclusive_and_handles_year_boundary():
    module = _load_archive_importer()
    assert [x.isoformat() for x in module.month_range(date(2025, 11, 1), date(2026, 2, 1))] == [
        "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01"
    ]


def test_archive_importer_requires_dedicated_direct_ingestion_connection():
    module = _load_archive_importer()
    module.validate_ingest_dsn("postgresql://cfdt_juris_ingest:secret@db.example/neondb")
    with pytest.raises(ValueError, match="cfdt_juris_ingest"):
        module.validate_ingest_dsn("postgresql://postgres:secret@db.example/neondb")
    with pytest.raises(ValueError, match="pooler"):
        module.validate_ingest_dsn("postgresql://cfdt_juris_ingest:secret@db-pooler.example/neondb")


@pytest.mark.asyncio
async def test_archive_importer_records_source_provenance_and_only_imports_fpt_decisions(monkeypatch):
    module = _load_archive_importer()
    calls = []

    class Transaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def __init__(self):
            self.insert = None
            self.updates = []
        def transaction(self):
            return Transaction()
        async def fetchrow(self, query, *args):
            self.insert = (query, args)
            return {"id": "run-id"}
        async def execute(self, query, *args):
            self.updates.append((query, args))

    async def fake_upsert(conn, item):
        calls.append(item["source_id"])

    monkeypatch.setattr(module, "upsert_legal_document", fake_upsert)
    conn = FakeConn()
    parsed = [
        {"source_id": "fpt", "raw_metadata": {"public_service_scope": "FPT"}},
        {"source_id": "common", "raw_metadata": {"public_service_scope": "COMMON_PUBLIC_SERVICE"}},
        {"source_id": "fpe", "raw_metadata": {"public_service_scope": "FPE"}},
    ]
    result = await module.import_archive(
        conn, "CAA", date(2026, 1, 1), "CAA_202601.zip", b"PK\\x03\\x04", parsed_items=parsed
    )

    assert result == {
        "archive": "CAA_202601.zip",
        "status": "SUCCEEDED",
        "records_parsed": 3,
        "records_selected": 2,
        "records_imported": 2,
        "records_rejected": 0,
    }
    assert calls == ["fpt", "common"]
    assert "source_key" in conn.insert[0]
    assert "JUSTICE_ADMIN_OPEN_DATA" in conn.insert[0]
    assert conn.updates[0][1][1:5] == ("SUCCEEDED", 2, 2, 0)


@pytest.mark.asyncio
async def test_archive_importer_counts_rejected_fpt_items_without_losing_successful_items(monkeypatch):
    module = _load_archive_importer()

    class Transaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConn:
        def transaction(self):
            return Transaction()
        async def fetchrow(self, query, *args):
            return {"id": "run-id"}
        async def execute(self, query, *args):
            self.last_update = (query, args)

    async def fake_upsert(conn, item):
        if item["source_id"] == "bad":
            raise ValueError("source rejected")
    monkeypatch.setattr(module, "upsert_legal_document", fake_upsert)
    conn = FakeConn()
    result = await module.import_archive(
        conn, "TA", date(2026, 1, 1), "TA_202601.zip", b"PK\\x03\\x04",
        parsed_items=[
            {"source_id": "good", "raw_metadata": {"public_service_scope": "FPT"}},
            {"source_id": "bad", "raw_metadata": {"public_service_scope": "FPT"}},
        ],
    )
    assert result["status"] == "PARTIAL"
    assert result["records_imported"] == 1
    assert result["records_rejected"] == 1
    assert conn.last_update[1][1:5] == ("PARTIAL", 2, 1, 1)



@pytest.mark.asyncio
async def test_archive_importer_skips_archives_with_a_previous_successful_run():
    module = _load_archive_importer()

    class FakeConn:
        def __init__(self):
            self.query = None
            self.args = None
        async def fetchval(self, query, *args):
            self.query = query
            self.args = args
            return True

    conn = FakeConn()
    assert await module.archive_already_imported(conn, "CAA_202603.zip") is True
    assert "status='SUCCEEDED'" in conn.query
    assert conn.args == ("CAA_202603.zip",)


def test_archive_downloader_rejects_non_official_hosts_before_network_access():
    module = _load_archive_importer()
    with pytest.raises(ValueError, match="hôte officiel HTTPS"):
        module.download_archive(None, "https://example.com/archive.zip")

def test_open_data_zip_error_reports_entries_when_no_xml_is_found():
    import io
    import zipfile

    from app.legal_ingestion import parse_administrative_open_data_zip

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("README.txt", "archive metadata")
        archive.writestr("data.json", "{}")

    with pytest.raises(ValueError, match="README.txt"):
        parse_administrative_open_data_zip(payload.getvalue(), "CAA_202610.zip")

def test_open_data_zip_accepts_more_than_5000_small_xml_entries():
    import io
    import zipfile

    from app.legal_ingestion import parse_administrative_open_data_zip

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(5001):
            archive.writestr(f"decision_{index:05d}.xml", "<Decision />")

    assert parse_administrative_open_data_zip(payload.getvalue(), "TA_202610.zip") == []



def test_fpt_scope_rejects_state_employee_with_incidental_commune_reference():
    from app.legal_ingestion import _is_fpt_employment_case_law

    body = (
        "Vu la procédure suivante : la requête demande l'annulation de la décision "
        "du ministre des armées refusant la reconnaissance d'une maladie professionnelle "
        "à un fonctionnaire. La commune est seulement mentionnée dans les pièces du dossier."
    )
    assert not _is_fpt_employment_case_law(
        "Décision du Tribunal administratif n° 2303018",
        body,
        {"scope": "FPT", "analysis_eligible": True},
    )


def test_fpt_scope_accepts_local_authority_hr_decision():
    from app.legal_ingestion import _is_fpt_employment_case_law

    body = (
        "Vu la procédure suivante : Mme X demande l'annulation de la décision du maire "
        "de Montpellier par laquelle elle a été affectée sur un nouvel emploi d'agente "
        "d'accueil au sein de la police municipale."
    )
    assert _is_fpt_employment_case_law(
        "Décision du Tribunal administratif n° 2401234",
        body,
        {"scope": "FPT", "analysis_eligible": True},
    )


def test_fpt_scope_rejects_urban_planning_case_with_incidental_hr_terms():
    from app.legal_ingestion import _is_fpt_employment_case_law

    body = (
        "Vu la procédure suivante : la commune demande l'annulation d'un permis de construire. "
        "Le dossier mentionne par ailleurs un fonctionnaire et une procédure disciplinaire "
        "dans une pièce sans lien avec le litige."
    )
    assert not _is_fpt_employment_case_law(
        "Décision de la cour administrative d'appel",
        body,
        {"scope": "FPT", "analysis_eligible": True},
    )
