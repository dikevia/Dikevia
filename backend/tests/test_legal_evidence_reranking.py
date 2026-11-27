from app.legal_assurance import rerank_legal_evidence_sources


def test_reranking_prioritizes_topical_fit_before_abstract_authority_rank():
    question = "Un agent territorial peut-il obtenir une indemnisation des heures supplémentaires non payées ?"
    sources = [
        {
            "source_id": "generic-law",
            "title": "Code général de la fonction publique",
            "text": "Dispositions générales relatives à la carrière et aux obligations des fonctionnaires.",
            "content_kind": "FULL_TEXT",
            "citation_integrity": {"valid": True},
            "legal_assurance": {"review_priority": 100},
            "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
        },
        {
            "source_id": "overtime-guidance",
            "title": "Indemnisation des heures supplémentaires dans la fonction publique territoriale",
            "excerpt": "Les heures supplémentaires effectuées par les agents territoriaux peuvent ouvrir droit à indemnisation ou repos compensateur selon les conditions applicables.",
            "content_kind": "FULL_TEXT",
            "citation_integrity": {"valid": True},
            "legal_assurance": {"review_priority": 20},
            "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
        },
    ]

    ranked = rerank_legal_evidence_sources(sources, question=question)

    assert [source["source_id"] for source in ranked] == [
        "overtime-guidance",
        "generic-law",
    ]


def test_reranking_preserves_all_sources_and_stable_order_for_equal_scores():
    first = {"source_id": "first", "title": "Document sans correspondance"}
    second = {"source_id": "second", "title": "Autre document sans correspondance"}

    ranked = rerank_legal_evidence_sources([first, second], question="Question sans lien")

    assert [source["source_id"] for source in ranked] == ["first", "second"]
    assert len(ranked) == 2


def test_reranking_does_not_promote_post_facts_case_law_over_exact_temporal_text():
    question = "Application de la règle aux heures supplémentaires en 2024"
    sources = [
        {
            "source_id": "later-case",
            "title": "Jurisprudence heures supplémentaires",
            "excerpt": "Heures supplémentaires et indemnisation des agents.",
            "temporal_status": "DECISION_POSTERIOR_TO_FACTS",
            "content_kind": "FULL_TEXT",
            "citation_integrity": {"valid": True},
            "legal_assurance": {"review_priority": 55},
        },
        {
            "source_id": "dated-text",
            "title": "Décret relatif aux heures supplémentaires des agents territoriaux",
            "excerpt": "Conditions d'indemnisation des heures supplémentaires.",
            "temporal_status": "IN_FORCE_ON_FACTS_DATE",
            "version_matches_facts_date": True,
            "content_kind": "FULL_TEXT",
            "citation_integrity": {"valid": True},
            "legal_assurance": {"review_priority": 65},
        },
    ]

    ranked = rerank_legal_evidence_sources(sources, question=question)

    assert ranked[0]["source_id"] == "dated-text"
