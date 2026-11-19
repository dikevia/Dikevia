from app.article_lookup import missing_direct_article_reference


def _source(source_type, article, *, valid=True, content_kind="FULL_TEXT"):
    return {
        "source_type": source_type,
        "article": article,
        "content_kind": content_kind,
        "citation_integrity": {"valid": valid},
    }


def test_nonexistent_article_abstains_despite_unrelated_legal_sources():
    question = "Que prévoit l'article L999-999 du CGFP ?"
    unrelated = [
        _source("CGFP_SNAPSHOT", "R134-4"),
        _source("LEGIFRANCE_LODA", "DECRET-2002-60"),
        _source("LEGIFRANCE_CETAT_FULL_TEXT", "CE-123456"),
    ]
    assert missing_direct_article_reference(question, unrelated) == "L999-999"


def test_exact_article_allows_cross_reference_with_decree_and_case_law():
    question = "Que prévoit l'article L111-1 du CGFP ?"
    sources = [
        _source("LEGIFRANCE_API", "L111-1"),
        _source("LEGIFRANCE_LODA", "DECRET-2024-123"),
        _source("LEGIFRANCE_CETAT_FULL_TEXT", "CE-123456"),
    ]
    assert missing_direct_article_reference(question, sources) is None


def test_substantive_question_mentioning_article_keeps_related_sources():
    question = "Mon employeur ne respecte pas l'article L111-1 : quels recours puis-je exercer ?"
    unrelated = [_source("CGFP_SNAPSHOT", "R134-4")]
    assert missing_direct_article_reference(question, unrelated) is None


def test_mixed_text_and_consequences_request_does_not_invent_missing_article():
    question = (
        "Que prévoit l'article L999-999 du CGFP et quelles conséquences "
        "pour un agent territorial ?"
    )
    related_but_not_exact = [
        _source("LEGIFRANCE_LODA", "DECRET-2002-60"),
        _source("LEGIFRANCE_CETAT_FULL_TEXT", "CE-123456"),
    ]
    assert missing_direct_article_reference(question, related_but_not_exact) == "L999-999"


def test_unvalidated_exact_looking_hit_does_not_satisfy_lookup():
    question = "Quel est le contenu de l'article L111-1 du CGFP ?"
    sources = [_source("CGFP_SNAPSHOT", "L111-1", valid=False)]
    assert missing_direct_article_reference(question, sources) == "L111-1"
