from app.legal_assurance import classify_legal_source


def test_version_retrieved_at_requested_date_discloses_missing_entry_into_force_status():
    source = {
        "source_type": "LEGIFRANCE_API",
        "document_kind": "CODE",
        "title": "Code général de la fonction publique",
        "temporal_status": "VERSION_RETRIEVED_AT_REQUESTED_DATE",
        "official_source": True,
    }

    result = classify_legal_source(source)

    assert result["temporal_limit"]
    assert "entrée en vigueur" in result["temporal_limit"]
    assert result["usable_for_facts_date_conclusion"] is True
