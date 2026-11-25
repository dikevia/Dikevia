from scripts.audit_staging_reference_provenance import audit_references


def test_audit_accepts_source_reference_id_without_claiming_legifrance_identity():
    result = audit_references("F12345", [
        {
            "source_reference_id": "R57657",
            "type": "internal",
            "libelle": "Référence Service-Public interne",
        }
    ])

    assert result["references"] == 1
    assert result["missing_source_reference_id"] == 0
    assert result["mislabelled_legifrance_id"] == 0
    assert result["errors"] == []


def test_audit_rejects_internal_id_mislabelled_as_legifrance():
    result = audit_references("F12345", [
        {
            "id_legifrance": "R57657",
            "type": "internal",
            "libelle": "Référence Service-Public interne",
        }
    ])

    assert result["missing_source_reference_id"] == 1
    assert result["mislabelled_legifrance_id"] == 1
    assert "F12345[0]:source_reference_id_missing" in result["errors"]
    assert "F12345[0]:id_legifrance_not_recognized" in result["errors"]


def test_audit_accepts_recognized_legifrance_id_only_with_matching_source_id():
    result = audit_references("F12345", [
        {
            "source_reference_id": "LEGIARTI000000000001",
            "id_legifrance": "LEGIARTI000000000001",
            "type": "article",
            "libelle": "Article officiel",
        }
    ])

    assert result["errors"] == []


def test_audit_rejects_mismatched_provenance_even_when_both_ids_look_valid():
    result = audit_references("F12345", [
        {
            "source_reference_id": "LEGIARTI000000000001",
            "id_legifrance": "LEGIARTI000000000002",
        }
    ])

    assert result["errors"] == ["F12345[0]:identifier_provenance_mismatch"]


def test_audit_flags_malformed_reference_entries():
    result = audit_references("F12345", ["R57657", None])

    assert result["malformed_reference"] == 2
    assert len(result["errors"]) == 2
