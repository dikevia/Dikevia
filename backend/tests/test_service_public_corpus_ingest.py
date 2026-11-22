from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import import_service_public_to_legal_corpus as importer  # noqa: E402


def _fiche():
    return {
        "fiche_id": "F12345",
        "titre_courant": "Temps partiel thérapeutique dans la fonction publique",
        "contenu": (
            "Cette fiche présente les règles administratives relatives au temps partiel "
            "thérapeutique dans la fonction publique. Elle décrit les démarches, les "
            "conditions générales et les références utiles sans se substituer aux textes."
        ),
        "theme_ids": ["N19806"],
        "versants_detectes": ["FPT"],
        "references_juridiques": [
            {"id_legifrance": "LEGIARTI000000000001", "type": "article",
             "libelle": "Code général de la fonction publique"}
        ],
    }


def _provenance():
    return {
        "dataset_id": "dataset-123",
        "dataset_last_update": "2026-11-21",
        "resource_id": "resource-123",
        "download_url": "https://lecomarquage.service-public.gouv.fr/vdd/3.5/part/zip/vosdroits-latest.zip",
        "filename": "vosdroits-latest.zip",
        "license": "fr-lo",
        "attribution": "Service-Public.gouv.fr / DILA",
    }


def test_service_public_fiche_maps_to_unverified_guidance_not_primary_law():
    item = importer.to_corpus_item(_fiche(), _provenance())
    assert item["source_type"] == "SERVICE_PUBLIC_PART"
    assert item["source_id"] == "F12345"
    assert item["document_kind"] == "ADMIN_GUIDANCE"
    assert item["source_status"] == "IMPORTED_UNVERIFIED"
    assert item["status"] == "UNKNOWN"
    assert item["valid_from"] is None
    assert item["valid_to"] is None
    assert item["official_url"] is None
    assert item["raw_metadata"]["attribution"] == "Service-Public.gouv.fr / DILA"
    assert item["raw_metadata"]["license"] == "fr-lo"
    assert item["raw_metadata"]["corpus_role"] == "ADMINISTRATIVE_GUIDANCE_NOT_PRIMARY_LEGAL_AUTHORITY"
    assert item["raw_metadata"]["references_juridiques"][0]["id_legifrance"] == "LEGIARTI000000000001"


def test_service_public_version_key_changes_when_content_changes():
    fiche = _fiche()
    first = importer.to_corpus_item(fiche, _provenance())
    fiche["contenu"] += " Une précision supplémentaire."
    second = importer.to_corpus_item(fiche, _provenance())
    assert first["version_key"] != second["version_key"]


def test_service_public_ingestion_requires_dedicated_role():
    importer.validate_ingest_dsn("postgresql://cfdt_juris_ingest:secret@db.example/db")
    try:
        importer.validate_ingest_dsn("postgresql://cfdt_juris_app:secret@db.example/db")
    except ValueError as exc:
        assert "cfdt_juris_ingest" in str(exc)
    else:
        raise AssertionError("Le rôle runtime ne doit pas être accepté pour l'ingestion.")


def test_service_public_import_refuses_incomplete_fiche():
    fiche = _fiche()
    fiche["contenu"] = "Trop court."
    try:
        importer.to_corpus_item(fiche, _provenance())
    except ValueError as exc:
        assert "incomplète" in str(exc)
    else:
        raise AssertionError("Une fiche incomplète ne doit pas être importée.")
