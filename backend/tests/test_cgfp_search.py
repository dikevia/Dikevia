from app.cgfp import search_cgfp
from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest
import pytest

def test_cgfp_exact_article_reference_returns_article_and_page():
    result = search_cgfp("Article L4", limit=5)
    assert result["results"]
    assert result["results"][0]["article"] == "L4"
    assert result["results"][0]["page_start"] == 1
    assert "fonctionnaires territoriaux" in result["results"][0]["excerpt"]

def test_cgfp_keyword_search_returns_relevant_content():
    result = search_cgfp("temps de travail durée annuelle", limit=8)
    assert result["results"]
    assert all(item["source_id"] == "FR-CGFP-2026-10-31" for item in result["results"])

def test_cgfp_results_are_explicitly_unverified_snapshot():
    result = search_cgfp("congé maladie", limit=3)
    assert result["source"]["verification_status"] == "SNAPSHOT_NOT_LIVE_VERIFIED"

@pytest.mark.asyncio
async def test_orchestrator_never_claims_full_legal_verification_from_snapshot():
    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Que prévoit le code sur les fonctionnaires territoriaux ?"),
        "00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert response.sources
    assert any("Légifrance" in item for item in response.missing_information)

def test_cgfp_article_endpoint_service_returns_full_article_text():
    from app.cgfp import get_cgfp_article
    article = get_cgfp_article(" l4 ")
    assert article is not None
    assert article["article"] == "L4"
    assert "fonctionnaires territoriaux" in article["text"]
    assert article["verification_status"] == "SNAPSHOT_NOT_LIVE_VERIFIED"

def test_cgfp_article_lookup_rejects_invalid_reference():
    from app.cgfp import get_cgfp_article
    assert get_cgfp_article("L4/../secret") is None

def test_cgfp_search_uses_relevance_ranking_and_returns_bounded_excerpt():
    result = search_cgfp("congé maladie fonctionnaire", limit=5)
    assert result["results"]
    assert len(result["results"]) <= 5
    assert all(len(item["excerpt"]) <= 1802 for item in result["results"])

def test_cgfp_article_lookup_unknown_reference_returns_none():
    from app.cgfp import get_cgfp_article
    assert get_cgfp_article("L99999999") is None


def test_snapshot_citation_integrity_accepts_exact_article_excerpt():
    from app.cgfp import get_cgfp_article
    from app.legal_validation import validate_snapshot_citation
    article = get_cgfp_article("L4")
    citation = {"source_id": article["source_id"], "article": "L4",
                "page_start": article["page_start"], "page_end": article["page_end"],
                "excerpt": article["text"][:300]}
    report = validate_snapshot_citation(citation, article)
    assert report["valid"] is True
    assert report["verification_scope"] == "snapshot_document_integrity_only"


def test_snapshot_citation_integrity_rejects_forged_page_or_excerpt():
    from app.cgfp import get_cgfp_article
    from app.legal_validation import validate_snapshot_citation
    article = get_cgfp_article("L4")
    citation = {"source_id": article["source_id"], "article": "L4",
                "page_start": 999, "page_end": 999, "excerpt": "Texte inventé"}
    report = validate_snapshot_citation(citation, article)
    assert report["valid"] is False
    assert report["checks"]["pdf_page_range"] is False
    assert report["checks"]["excerpt_matches_full_text"] is False


def test_facts_date_requires_strict_iso_format():
    from app.legal_validation import parse_facts_date
    assert str(parse_facts_date("2024-01-31")) == "2024-01-31"
    import pytest
    with pytest.raises(ValueError):
        parse_facts_date("31/01/2024")


@pytest.mark.asyncio
async def test_orchestrator_rejects_ambiguous_facts_date():
    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", facts_date="31/01/2024",
                   question="Quels sont les droits à congé maladie ?"),
        "00000000-0000-0000-0000-000000000001")
    assert response.verification_status == "NON_VERIFIE"
    assert "AAAA-MM-JJ" in response.missing_information[0]


def test_cgfp_explicit_reference_never_falls_back_to_unrelated_articles():
    from app.cgfp_relevance import search_cgfp as search_ranked_cgfp

    result = search_ranked_cgfp(
        "Que prévoit l'article L999-999 du Code général de la fonction publique ? "
        "Donne-moi son contenu et ses conséquences juridiques.",
        limit=8,
    )
    assert result["search_mode"] == "reference_directe"
    assert result["requested_reference"] == "L999-999"
    assert result["reference_found_in_snapshot"] is False
    assert result["results"] == []


def test_cgfp_explicit_existing_reference_returns_only_that_article():
    from app.cgfp_relevance import search_cgfp as search_ranked_cgfp

    result = search_ranked_cgfp(
        "Que prévoit l'article L4 du Code général de la fonction publique "
        "pour les fonctionnaires territoriaux ?",
        limit=8,
    )
    assert result["search_mode"] == "reference_directe"
    assert result["requested_reference"] == "L4"
    assert result["reference_found_in_snapshot"] is True
    assert [item["article"] for item in result["results"]] == ["L4"]



def test_snapshot_fallback_is_used_when_live_cgfp_is_unavailable():
    from app.orchestrator import should_use_cgfp_snapshot_fallback

    found = {"results": [{
        "article": "L134-5",
        "source_id": "FR-CGFP-2026-10-31",
        "excerpt": "Protection fonctionnelle",
    }]}
    assert should_use_cgfp_snapshot_fallback(
        "La recherche officielle CGFP a échoué.", found,
        "Mon employeur refuse ma protection fonctionnelle",
    )


def test_snapshot_fallback_is_not_used_when_live_cgfp_is_available():
    from app.orchestrator import should_use_cgfp_snapshot_fallback

    found = {"results": [{
        "article": "L134-5",
        "source_id": "FR-CGFP-2026-10-31",
        "excerpt": "Protection fonctionnelle",
    }]}
    assert not should_use_cgfp_snapshot_fallback(
        None, found, "Mon employeur refuse ma protection fonctionnelle",
    )


def test_snapshot_fallback_rejects_irrelevant_hits_for_overtime():
    from app.orchestrator import should_use_cgfp_snapshot_fallback

    found = {"results": [{
        "article": "R422-96",
        "source_id": "FR-CGFP-2026-10-31",
        "excerpt": "Crédit d'heures supplémentaires pour prévenir une inaptitude.",
    }]}
    assert not should_use_cgfp_snapshot_fallback(
        "Recherche CGFP indisponible.", found,
        "On ne me paie pas mes heures supplémentaires",
    )



def test_cgfp_concept_router_covers_major_fpt_code_subjects():
    from app.cgfp_relevance import _matching_topics

    cases = [
        ("Mon agent de maîtrise m'a fait une évaluation annuelle à charge, puis-je la contester ?",
         "carriere_avancement_evaluation"),
        ("Mon supérieur m'impose le secret professionnel.", "droits_obligations_deontologie"),
        ("Comment se passe ma titularisation après le stage ?", "recrutement_stage_titularisation"),
        ("Ma collectivité refuse ma promotion interne.", "carriere_avancement_evaluation"),
        ("Puis-je être muté dans une autre collectivité ?", "mobilite_positions_statutaires"),
        ("Mon employeur refuse ma formation CNFPT.", "formation_professionnelle"),
        ("Mon congé parental est refusé.", "conges_absences_familiales"),
        ("Le service de médecine préventive n'intervient pas.", "sante_securite_prevention"),
        ("Mon employeur peut-il m'interdire de faire grève ?", "greve_dialogue_social_representativite"),
        ("Je souhaite démissionner de la fonction publique territoriale.", "cessation_fonctions_retraite"),
        ("Je subis une discrimination au travail.", "egalite_discrimination"),
        ("Mon ASA syndicale est refusée.", "droits_syndicaux_dialogue_social"),
    ]
    for question, expected_topic in cases:
        assert expected_topic in {topic["key"] for topic in _matching_topics(question)}


def test_cgfp_retrieval_keeps_overtime_as_a_specific_topic():
    from app.cgfp_relevance import _matching_topics

    topics = {topic["key"] for topic in _matching_topics(
        "Je suis contractuel et mes heures supplémentaires ne sont pas payées."
    )}
    assert topics == {"heures_supplementaires_ihts"}



def test_cgfp_index_snapshot_is_explicitly_a_dated_discovery_source():
    from app.cgfp import load_index

    source = load_index()
    assert source["source_id"] == "FR-CGFP-2026-10-31"
    assert source["verification_status"] == "SNAPSHOT_NOT_LIVE_VERIFIED"
    assert source["article_count"] == len(source["articles"])
    assert source["articles"]
    assert all(
        item.get("article") and item.get("text")
        and item.get("page_start", 0) >= 1
        and item.get("page_end", 0) >= item.get("page_start", 0)
        for item in source["articles"]
    )


def test_cgfp_live_article_discovery_keeps_up_to_six_relevant_subtopics(monkeypatch):
    import app.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda _ref: True)
    found = {"results": [
        {"article": f"L{number}", "matched_concepts": ["topic"]}
        for number in range(1, 9)
    ]}
    assert orchestrator._cgfp_article_discovery_queries(found) == [
        f"article L{number}" for number in range(1, 7)
    ]


def test_code_research_budget_never_drops_a_recognized_subquestion():
    from app.orchestrator import _build_code_research_queries

    axes = [f"axe juridique {number}" for number in range(1, 7)]
    exact_articles = [f"article L{number}" for number in range(1, 7)]
    result = _build_code_research_queries(axes, exact_articles, max_queries=5)
    assert result == axes

    result_with_spare_capacity = _build_code_research_queries(
        axes[:3], exact_articles, max_queries=5
    )
    assert result_with_spare_capacity == [
        *axes[:3], "article L1", "article L2"
    ]


def test_cgfp_topic_anchors_rank_but_do_not_suppress_lexical_candidates(monkeypatch):
    from app.cgfp_relevance import search_cgfp as search_ranked_cgfp

    monkeypatch.setattr(
        "app.cgfp_relevance.lexical_search",
        lambda query, limit=20: {
            "source": {"source_id": "test"},
            "results": [
                {"article": "L714-4", "score": 2.0, "excerpt": "Régime indemnitaire des agents territoriaux."},
                {"article": "L714-5", "score": 1.5, "excerpt": "Conditions d'exercice des fonctions."},
            ],
        },
    )
    monkeypatch.setattr(
        "app.cgfp_relevance.get_cgfp_article",
        lambda ref: {
            "text": (
                "Régime indemnitaire des agents territoriaux."
                if ref == "L714-4" else "Conditions d'exercice des fonctions."
            )
        },
    )

    result = search_ranked_cgfp("Je remplace un collègue et demande ses primes")

    assert {item["article"] for item in result["results"]} == {"L714-4", "L714-5"}
    contextual = next(item for item in result["results"] if item["article"] == "L714-5")
    assert contextual["relevance_label"].startswith("Correspondance lexicale")



def test_citis_query_uses_focused_health_topic():
    from app.cgfp_relevance import _matching_topics

    topics = {item["key"] for item in _matching_topics(
        "Je suis en CITIS après un accident de service reconnu imputable."
    )}
    assert topics == {"citis"}


def test_therapeutic_part_time_query_uses_focused_health_topic():
    from app.cgfp_relevance import _matching_topics

    topics = {item["key"] for item in _matching_topics(
        "Mon médecin préconise un temps partiel thérapeutique après mon arrêt."
    )}
    assert topics == {"temps_partiel_therapeutique"}


def test_citis_retrieval_surfaces_its_core_cgfp_provisions():
    from app.cgfp_relevance import search_cgfp as search_ranked_cgfp

    result = search_ranked_cgfp(
        "Je suis en CITIS après un accident reconnu imputable au service. "
        "Quels sont mes droits au congé, au maintien du traitement et à la reprise ?",
        limit=20,
    )
    refs = {item["article"] for item in result["results"]}
    assert {"L822-21", "L822-22", "L822-23"} & refs


def test_therapeutic_part_time_retrieval_surfaces_its_core_cgfp_provisions():
    from app.cgfp_relevance import search_cgfp as search_ranked_cgfp

    result = search_ranked_cgfp(
        "Après un arrêt maladie, mon médecin préconise un temps partiel "
        "pour raison thérapeutique. Quels sont les droits au maintien de l'emploi "
        "et à la rémunération ?",
        limit=20,
    )
    refs = {item["article"] for item in result["results"]}
    assert {"L823-1", "L823-2", "L823-4", "L823-5"} & refs



def test_code_research_budget_preserves_axes_and_reserves_three_exact_article_lookups():
    from app.orchestrator import _build_code_research_queries

    axes = [f"axe juridique {number}" for number in range(1, 6)]
    exact_articles = [f"article L823-{number}" for number in range(1, 7)]
    result = _build_code_research_queries(
        axes, exact_articles, max_queries=8
    )
    assert result == [*axes, *exact_articles[:3]]


def test_cgfp_tokenizer_normalizes_french_plural_forms_without_corrupting_invariants():
    from app.cgfp import tokenize

    assert tokenize("régimes indemnitaires primes") == [
        "regime", "indemnitaire", "prime"
    ]
    assert tokenize("régime indemnitaire prime") == [
        "regime", "indemnitaire", "prime"
    ]
    assert "temps" in tokenize("temps de travail")
    assert "prix" in tokenize("prix des prestations")


def test_cgfp_article_discovery_can_be_scoped_to_fpe(monkeypatch):
    from app import orchestrator

    monkeypatch.setattr(
        orchestrator,
        "get_cgfp_article",
        lambda _article: {
            "text": "Les agents de la fonction publique de l'État bénéficient de cette disposition."
        },
    )
    assert orchestrator._cgfp_article_fpt_eligible("L123-4", "FPE") is True
    assert orchestrator._cgfp_article_fpt_eligible("L123-4", "FPT") is False
