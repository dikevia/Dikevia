from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_source_registry_records_authority_reuse_and_refresh_policy():
    migration = (ROOT / "database/migrations/032_legal_source_registry.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE legal_source_registry" in migration
    assert "ALTER TABLE legal_documents" in migration
    assert "ADD COLUMN source_key text REFERENCES legal_source_registry(source_key)" in migration
    assert "ALTER TABLE legal_ingestion_runs" in migration
    assert "'LEGIFRANCE_PISTE'" in migration
    assert "'JUSTICE_ADMIN_OPEN_DATA'" in migration
    assert "'SERVICE_PUBLIC_DATA'" in migration
    assert "'ARIANEWEB'" in migration
    assert "'DGAFP_VIGIE'" in migration
    assert "'CNFPT_WIKITERRITORIAL'" in migration
    assert "'CDG35'" in migration
    assert "'CFDT_INTERCO'" in migration
    assert "'INFO_GOUV'" in migration
    assert "'CNFPT'" in migration
    assert "'DGAFP'" in migration
    assert "'APPROVED_SEEDS_ONLY'" in migration


def test_source_registry_never_allows_automatic_full_text_from_unverified_sources():
    migration = (ROOT / "database/migrations/032_legal_source_registry.sql").read_text(encoding="utf-8")
    assert "'ARIANEWEB'" in migration
    assert "'METADATA_ONLY',false,true,false,false" in migration
    assert "'CNFPT_WIKITERRITORIAL'" in migration
    assert "'OWNER_APPROVED_PENDING_REVIEW',false,true,false,false" in migration
    assert "'LANDOT'" in migration
    assert "'GAZETTE_COMMUNES'" in migration
    assert "'LOCALtis'" in migration
    assert "'WEKA'" in migration
    assert "'DALLOZ'" in migration
    assert "'LEXISNEXIS'" in migration
    assert "'DELIBIA'" in migration
    assert "'COMMUNIA'" in migration
    assert "'KOLECTIVIA'" in migration


def test_open_licensed_official_sources_are_marked_for_controlled_automated_ingestion():
    migration = (ROOT / "database/migrations/032_legal_source_registry.sql").read_text(encoding="utf-8")
    assert "'OPEN_LICENSE',true,true,true,true,'VERIFIED'" in migration
    assert "Respecter les quotas par jeton" in migration
    assert "Licence Ouverte 2.0" in migration
    assert "SET source_key = CASE" in migration


def test_source_registry_rollback_removes_only_registry_metadata_and_links():
    rollback = (ROOT / "database/migrations/rollback/032_legal_source_registry.down.sql").read_text(encoding="utf-8")
    assert "DROP TABLE IF EXISTS legal_source_registry" in rollback
    assert "ALTER TABLE legal_documents DROP COLUMN IF EXISTS source_key" in rollback
    assert "ALTER TABLE legal_ingestion_runs DROP COLUMN IF EXISTS source_key" in rollback
    assert "DROP TABLE IF EXISTS legal_documents" not in rollback
    assert "DROP TABLE IF EXISTS legal_document_versions" not in rollback
