from app.evidence_text import normalize_evidence_text


def test_normalize_evidence_text_removes_invisible_formatting_controls():
    value = "L\u200b’agent\ufeff ne\u2060 peut\u200e pas"
    assert normalize_evidence_text(value) == "L'agent ne peut pas"


def test_normalize_evidence_text_preserves_negation_accents_and_legal_content():
    value = "L’agent ne peut pas bénéficier de l’autorisation spéciale."
    assert normalize_evidence_text(value) == "L'agent ne peut pas bénéficier de l'autorisation spéciale."


def test_normalize_evidence_text_collapses_nonbreaking_and_repeated_whitespace():
    value = "Article\u00a0L. 123-4\n\tdu CGFP"
    assert normalize_evidence_text(value) == "Article L. 123-4 du CGFP"
