from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import import_service_public_fonction_publique as importer  # noqa: E402


def _archive() -> zipfile.ZipFile:
    payload = """<?xml version="1.0" encoding="UTF-8"?>
    <Fiche xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>Temps partiel thérapeutique dans la fonction publique</dc:title>
      <Theme ID="N19806"/>
      <FilDAriane><Niveau ID="N19806"/></FilDAriane>
      <BlocCas type="FPT"><Titre>Fonction publique territoriale</Titre><Texte>Temps partiel pour raison thérapeutique.</Texte></BlocCas>
      <Reference ID="LEGIARTI000000000001" type="article">Code général de la fonction publique</Reference>
    </Fiche>""".encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("F12345.xml", payload)
        archive.writestr("F99999.xml", payload.replace(b'N19806', b'N00000'))
        archive.writestr(
            "F100.xml",
            b'<Fiche><dc:title>Quels sont les moyens du comite social et economique (CSE) ?</dc:title>'
            b'<Theme ID="N19806"/><Texte>Les salaries elisent leur CSE dans les entreprises privees. Une mention de la fonction publique figure dans un lien connexe.</Texte></Fiche>',
        )
        archive.writestr(
            "F12346.xml",
            b'<Fiche><dc:title>Droits a conges annuels</dc:title><Theme ID="N19806"/>'
            b'<Texte>Regles de report et d indemnisation.</Texte>'
            b'<Reference ID="D85-1250" type="decret">Décret n° 85-1250 du 26 novembre 1985</Reference></Fiche>',
        )
        archive.writestr("arborescence.xml", b"<Arborescence/>")
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def test_dataset_metadata_selects_current_zip_not_schema_zip():
    metadata = {
        "resources": [
            {"format": "zip", "title": "Schémas du flux", "url": "https://example.test/schema_3.5.zip"},
            {
                "format": "xml",
                "title": "Fiches pratiques et ressources pour les particuliers",
                "description": "Archive quotidienne des fiches",
                "url": "https://example.test/vosdroits-latest.zip",
            },
        ]
    }
    resource = importer.resolve_archive_resource(metadata)
    assert resource["url"].endswith("vosdroits-latest.zip")


def test_extracts_only_function_public_fiches_and_preserves_legal_context():
    archive = _archive()
    try:
        fiches = importer.extraire_fiches_fonctionnaires(archive)
    finally:
        archive.close()

    assert len(fiches) == 2
    fiche = next(item for item in fiches if item["fiche_id"] == "F12345")
    generic_title_fiche = next(item for item in fiches if item["fiche_id"] == "F12346")
    assert generic_title_fiche["titre_courant"] == "Droits a conges annuels"
    assert fiche["titre_courant"] == "Temps partiel thérapeutique dans la fonction publique"
    assert fiche["versants_detectes"] == ["FPT"]
    assert "temps partiel pour raison thérapeutique" in fiche["contenu"].lower()
    assert fiche["references_juridiques"][0]["id_legifrance"] == "LEGIARTI000000000001"
    assert fiche["statut_validation_juridique"] == "NON_VERIFIE"


def test_build_output_keeps_source_attribution_and_download_provenance():
    result = importer.build_output([], {
        "download_url": "https://example.test/vosdroits-latest.zip",
        "filename": "vosdroits-latest.zip",
        "license": "fr-lo",
        "attribution": "Service-Public.gouv.fr / DILA",
    })
    assert result["source"]["attribution"] == "Service-Public.gouv.fr / DILA"
    assert result["source"]["download_url"].startswith("https://")
    assert "doivent être vérifiées" in result["avertissement"]
