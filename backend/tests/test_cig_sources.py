from backend.app.cig_sources import (
    CIG_SOURCES,
    can_ingest_cig_content,
    cig_source_metadata,
    get_cig_source,
    validate_cig_source_url,
)


def test_catalog_has_stable_unique_ids_and_only_cig_https_urls():
    ids = [source.source_id for source in CIG_SOURCES]
    assert len(ids) == len(set(ids))
    assert all(validate_cig_source_url(source.url) for source in CIG_SOURCES)


def test_bip_and_iaj_are_never_ingested_without_written_scoped_permission():
    for source_id in ("CIG_BIP", "CIG_IAJ"):
        assert can_ingest_cig_content(source_id) is False
        assert can_ingest_cig_content(source_id, written_permission=True) is False
        assert can_ingest_cig_content(
            source_id, written_permission=True, permission_scope="Dikévia commercial RAG"
        ) is True


def test_public_visibility_does_not_grant_content_reuse():
    assert can_ingest_cig_content("CIG_MINUTE_STATUT") is False
    assert can_ingest_cig_content("CIG_INFOGRAPHIES") is False
    assert can_ingest_cig_content("CIG_SVP_PUBLIC") is False


def test_unknown_source_fails_closed():
    assert get_cig_source("UNKNOWN") is None
    assert can_ingest_cig_content("UNKNOWN", written_permission=True, permission_scope="all") is False
    assert cig_source_metadata("UNKNOWN") is None


def test_catalog_metadata_does_not_claim_content_was_ingested():
    item = cig_source_metadata("CIG_BIP")
    assert item is not None
    assert item["source_status"] == "CATALOGUED_NOT_INGESTED"
    assert item["content_policy"] == "LICENSE_REQUIRED"
    assert item["access"] == "AUTHENTICATED"


def test_url_validation_rejects_non_https_and_lookalike_hosts():
    assert validate_cig_source_url("https://www.cig929394.fr/ressources")
    assert not validate_cig_source_url("http://www.cig929394.fr/ressources")
    assert not validate_cig_source_url("https://cig929394.fr.attacker.example/")
    assert not validate_cig_source_url("https://user:pass@www.cig929394.fr/")
