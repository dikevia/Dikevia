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
    assert source["status"] == "CANDIDATE"
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

