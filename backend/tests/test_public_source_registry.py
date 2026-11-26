from __future__ import annotations

import json
from pathlib import Path

from app.legal_corpus import safe_official_url

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "corpus_national" / "sources" / "registry.json"


def test_user_provided_public_source_domains_are_registered():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source_ids = {source["id"] for source in registry["sources"]}
    expected = {
        "service-public-part", "cnfpt", "wikiterritorial-cnfpt",
        "cig-petite-couronne", "cig-grande-couronne",
        "cdg-35", "cdg-44", "cdg-59", "cdg-69",
        "dgafp", "dgcl", "info-gouv",
    }
    assert expected <= source_ids


def test_document_seeds_have_explicit_ingestion_status_and_known_source():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source_ids = {source["id"] for source in registry["sources"]}
    seeds = registry["document_seeds"]
    assert seeds
    assert len({item["id"] for item in seeds}) == len(seeds)
    for item in seeds:
        assert item["source_id"] in source_ids
        assert item["url"].startswith("https://")
        assert item["status"] in {"CANDIDATE", "ACCESS_REVIEWED", "REUSE_APPROVED", "SUSPENDED"}
        assert item["content_status"] in {"NOT_COLLECTED", "EXTRACTED_NOT_IMPORTED"}
        assert item["reuse_status"] in {"REVIEW_REQUIRED", "REUSE_APPROVED", "APPROVED"}
        if item["status"] == "SUSPENDED":
            assert item["content_status"] == "NOT_COLLECTED"
            assert item["reuse_status"] == "REVIEW_REQUIRED"
        if item["content_status"] == "EXTRACTED_NOT_IMPORTED":
            assert item["status"] in {"ACCESS_REVIEWED", "REUSE_APPROVED"}
            assert item["reuse_status"] in {"REVIEW_REQUIRED", "REUSE_APPROVED", "APPROVED"}
            assert item.get("download_sha256")
            assert item.get("text_sha256")
            assert item.get("collected_at")
            if item.get("format") == "PDF":
                assert item.get("page_count", 0) > 0
            else:
                assert item.get("character_count", 0) > 0


def test_administrative_justice_open_data_is_registered_as_primary_case_law():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["id"] == "justice-administrative-opendata")
    assert source["authority_level"] == "PRIMARY_LEGAL"
    assert source["status"] == "ACCESS_REVIEWED"
    assert source["dataset_url"].startswith("https://opendata.justice-administrative.fr/")
    assert "archives xml zip mensuelles" in source["collection_mode"].casefold()
    assert "profilage" in source["reuse"]
    assert "numéro" in source["reuse"]

def test_reuse_approved_public_source_hosts_are_preserved_for_citations():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    restricted_or_non_public_hosts = {"espace-echanges.cdg35.bzh"}
    approved = [
        source for source in registry["sources"]
        if source.get("status") == "REUSE_APPROVED"
    ]
    assert approved
    for source in approved:
        for host in source.get("domains", []):
            if host in restricted_or_non_public_hosts:
                continue
            assert safe_official_url(f"https://{host}/"), (
                f"Host approved in source registry is missing from legal URL allowlist: {host}"
            )



def test_sig_info_gouv_pages_are_explicitly_reuse_approved_and_scoped():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    source = next(item for item in registry["sources"] if item["id"] == "info-gouv")
    seeds = [item for item in registry["document_seeds"] if item["source_id"] == "info-gouv"]
    expected = {
        "sig-missions-2026",
        "sig-charte-etat-marque",
        "sig-charte-accessibilite-communication",
        "sig-charte-usage-responsable-ia-2026",
    }
    assert source["authority_level"] == "OFFICIAL_ADMIN_GUIDANCE"
    assert source["status"] == "REUSE_APPROVED"
    assert source["reuse_authorization"]["status"] == "SOURCE_TERMS_CONFIRMED"
    assert "Etalab 2.0" in source["reuse"]
    assert {item["id"] for item in seeds} == expected
    assert all(item["status"] == "REUSE_APPROVED" for item in seeds)
    assert all(item["reuse_status"] == "REUSE_APPROVED" for item in seeds)
    assert all(item["url"].startswith("https://www.info.gouv.fr/") for item in seeds)
    for seed_id in ("sig-missions-2026", "sig-charte-etat-marque"):
        note = next(item for item in seeds if item["id"] == seed_id)["collection_note"]
        assert "HTTP 403" in note
        assert "n'est pas collecté ni extrait dans le corpus" in note
        assert "aperçu indexé ne remplace pas une extraction contrôlée" in note


def test_sig_info_gouv_guidance_cannot_become_primary_legal_evidence():
    from app.legal_assurance import classify_legal_source

    result = classify_legal_source({
        "source_type": "INSTITUTIONAL_GUIDANCE",
        "document_kind": "ADMIN_GUIDANCE",
        "publisher": "Service d'information du Gouvernement (SIG)",
        "source_status": "IMPORTED_UNVERIFIED",
        "status": "UNKNOWN",
        "raw_metadata": {
            "authority_level": "OFFICIAL_ADMIN_GUIDANCE",
            "source_registry_status": "REUSE_APPROVED",
            "legal_validation_status": "NOT_VERIFIED",
        },
    })
    assert result["authority_level"] == "OFFICIAL_ADMIN_GUIDANCE"
    assert result["publisher_type"] == "PUBLIC_ADMINISTRATION"
    assert result["normative"] is False
    assert result["claim_eligible"] is False
