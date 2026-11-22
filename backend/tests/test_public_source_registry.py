from __future__ import annotations

import json
from pathlib import Path

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
