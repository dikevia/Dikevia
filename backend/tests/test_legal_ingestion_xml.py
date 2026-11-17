import pytest

from app.legal_ingestion import parse_circulaires_xml


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
