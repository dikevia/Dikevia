import io
import zipfile

import pytest

from app.legal_ingestion import parse_administrative_open_data_zip, parse_circulaires_xml


def test_parse_circulaires_xml_extracts_basic_metadata():
    xml = b"""<ROOT>
      <CIRCULAIRE>
        <ID>ABC-2026-001</ID>
        <TITRE>Organisation du temps de travail</TITRE>
        <DATE_SIGNATURE>2026-01-15</DATE_SIGNATURE>
        <URL>https://www.legifrance.gouv.fr/circulaire/id/ABC</URL>
      </CIRCULAIRE>
    </ROOT>"""

    records = parse_circulaires_xml(xml)

    assert len(records) == 1
    assert records[0]["source_id"] == "ABC-2026-001"
    assert records[0]["title"] == "Organisation du temps de travail"
    assert records[0]["signature_date"].isoformat() == "2026-01-15"
    assert records[0]["official_url"] == "https://www.legifrance.gouv.fr/circulaire/id/ABC"
    assert records[0]["source_status"] == "IMPORTED_UNVERIFIED"


def test_parse_circulaires_xml_rejects_dtd_and_entity_declarations():
    xml = b"""<!DOCTYPE ROOT [
      <!ENTITY injected "contenu externe">
    ]>
    <ROOT><CIRCULAIRE><ID>1</ID><TITRE>&injected;</TITRE></CIRCULAIRE></ROOT>"""

    with pytest.raises(ValueError, match="DTD/ENTITY"):
        parse_circulaires_xml(xml)


def test_parse_circulaires_xml_rejects_malformed_xml():
    with pytest.raises(ValueError, match="invalide"):
        parse_circulaires_xml(b"<ROOT><CIRCULAIRE>")


def test_parse_circulaires_xml_rejects_empty_or_oversized_input():
    with pytest.raises(ValueError, match="vide ou dépasse"):
        parse_circulaires_xml(b"")
    with pytest.raises(ValueError, match="vide ou dépasse"):
        parse_circulaires_xml(b" " * (50 * 1024 * 1024 + 1))


def test_administrative_open_data_zip_keeps_only_relevant_fpt_employment_decisions():
    xml = """<Decision>
      <Identification>TA_202611_0001</Identification>
      <Date_Mise_Jour>2026-11-20</Date_Mise_Jour>
      <Code_Juridiction>TA38</Code_Juridiction>
      <Nom_Juridiction>Tribunal administratif de Grenoble</Nom_Juridiction>
      <Numero_Dossier>2601234</Numero_Dossier>
      <Date_Lecture>2026-11-18</Date_Lecture>
      <Numero_ECLI>ECLI:FR:TA:2026:2601234</Numero_ECLI>
      <Type_Decision>Décision</Type_Decision>
      <Code_Publication>C</Code_Publication>
      <Formation_Jugement>2e chambre</Formation_Jugement>
      <Texte_Integral><P>La commune a pris une sanction disciplinaire à l'encontre d'un agent territorial relevant de la fonction publique territoriale. L'intéressé conteste la procédure et les garanties statutaires applicables à sa situation.</P></Texte_Integral>
    </Decision>"""
    xml = xml.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("TA_202611_0001.xml", xml)
    records = parse_administrative_open_data_zip(buffer.getvalue(), "TA_202611.zip")
    assert len(records) == 1
    record = records[0]
    assert record["document_kind"] == "ADMIN_CASELAW"
    assert record["source_status"] == "OFFICIAL_XML_IMPORTED"
    assert record["signature_date"].isoformat() == "2026-11-18"
    assert record["jurisdiction"] == "Tribunal administratif de Grenoble"
    assert record["raw_metadata"]["ecli"] == "ECLI:FR:TA:2026:2601234"
    assert record["raw_metadata"]["source_archive"] == "TA_202611.zip"
    assert record["raw_metadata"]["source_xml_sha256"]
    assert "sanction disciplinaire" in record["full_text"]


def test_administrative_open_data_zip_rejects_non_fpt_or_non_hr_decisions():
    xml = """<Decision>
      <Identification>TA_202611_0002</Identification>
      <Nom_Juridiction>Tribunal administratif de Grenoble</Nom_Juridiction>
      <Numero_Dossier>2601235</Numero_Dossier>
      <Date_Lecture>2026-11-18</Date_Lecture>
      <Texte_Integral><P>La commune a adopté un plan local d'urbanisme et conteste une autorisation de construire délivrée à un promoteur privé.</P></Texte_Integral>
    </Decision>"""
    xml = xml.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("TA_202611_0002.xml", xml)
    assert parse_administrative_open_data_zip(buffer.getvalue(), "TA_202611.zip") == []
