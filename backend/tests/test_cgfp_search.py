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
        ("Quels sont les droits à congé maladie ?", "maladie_ordinaire"),
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


def test_code_research_budget_preserves_priority_without_exceeding_limit():
    from app.orchestrator import _build_code_research_queries

    axes = [f"axe juridique {number}" for number in range(1, 7)]
    exact_articles = [f"article L{number}" for number in range(1, 7)]
    result = _build_code_research_queries(axes, exact_articles, max_queries=5)
    assert result == axes[:5]
    assert len(result) <= 5
    assert not any(query in result for query in exact_articles)

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

def test_cgfp_article_discovery_forwards_the_selected_versant(monkeypatch):
    from app import orchestrator

    seen = []
    def eligible(article_ref, target_versant="FPT"):
        seen.append((article_ref, target_versant))
        return True

    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", eligible)
    found = {"results": [
        {"article": "L823-1", "matched_concepts": ["temps partiel thérapeutique"]}
    ]}

    assert orchestrator._cgfp_article_discovery_queries(found, "FPE") == ["article L823-1"]
    assert seen == [("L823-1", "FPE")]

    seen.clear()
    assert orchestrator._cgfp_article_discovery_queries(found, "FPH") == ["article L823-1"]
    assert seen == [("L823-1", "FPH")]


def test_snapshot_fallback_is_used_when_live_cgfp_hits_are_off_topic(monkeypatch):
    from app import orchestrator

    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda *_args: True)
    monkeypatch.setattr(
        orchestrator, "_source_relevant_to_any_research_axis",
        lambda _queries, source: source.get("relevant") is True,
    )
    found = {"results": [{"article": "L822-21", "relevant": True}]}

    assert orchestrator.should_use_cgfp_snapshot_fallback(
        None, found, ["axe CITIS"], target_versant="FPT",
        live_sources=[{"relevant": False, "analysis_eligible": True}],
    )


def test_snapshot_fallback_is_not_used_when_live_cgfp_covers_an_axis(monkeypatch):
    from app import orchestrator

    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda *_args: True)
    monkeypatch.setattr(
        orchestrator, "_source_relevant_to_any_research_axis",
        lambda _queries, source: source.get("relevant") is True,
    )
    found = {"results": [{"article": "L822-21", "relevant": True}]}

    assert not orchestrator.should_use_cgfp_snapshot_fallback(
        None, found, ["axe CITIS"], target_versant="FPT",
        live_sources=[{"relevant": True, "analysis_eligible": True}],
    )


@pytest.mark.parametrize(
    ("versant", "expected"),
    [
        ("FPE", "fonction publique de l'État"),
        ("FPH", "fonction publique hospitalière"),
    ],
)
def test_non_fpt_fallback_search_does_not_inherit_fpt_templates(versant, expected):
    from app.orchestrator import _build_versant_fallback_research

    queries, axes = _build_versant_fallback_research(
        "Quelles sont les règles de congés annuels ?", versant,
    )
    assert queries == [f"Quelles sont les règles de congés annuels ? {expected}"]
    assert axes == queries
    assert all("décret 85-1250" not in query for query in queries)
    assert all("fonction publique territoriale" not in query for query in queries)


def test_fpt_fallback_search_keeps_territorial_topic_expansion():
    from app.orchestrator import _build_versant_fallback_research

    queries, axes = _build_versant_fallback_research(
        "Quelles sont les règles de congés annuels ?", "FPT",
    )
    assert queries
    # One focused topic does not create a mandatory multi-axis evidence contract.
    assert axes == []
    assert any("décret 85-1250" in query for query in queries)


def test_cgfp_retrieval_expands_common_health_terms_without_reclassifying_them():
    from app.cgfp_relevance import _expand_legal_query, _matching_topics

    question = "Je voudrais reprendre à mi-temps après un accident du travail."
    expanded = _expand_legal_query(question)
    assert "temps partiel pour raison therapeutique" in expanded
    assert "accident de service" in expanded

    topics = {item["key"] for item in _matching_topics(question)}
    assert topics == {"citis", "temps_partiel_therapeutique"}


def test_cgfp_retrieval_alias_preserves_original_user_wording():
    from app.cgfp_relevance import _expand_legal_query

    question = "Mon médecin parle de mi-temps thérapeutique."
    expanded = _expand_legal_query(question)
    assert question in expanded
    assert "temps partiel pour raison therapeutique" in expanded


def test_accident_du_travail_alias_is_only_a_search_route():
    from app.cgfp_relevance import _expand_legal_query, _matching_topics

    question = "Mon accident du travail est-il reconnu ?"
    assert "accident de service" in _expand_legal_query(question)
    assert "citis" in {item["key"] for item in _matching_topics(question)}

def test_cgfp_article_discovery_verifies_unanchored_lexical_candidates_live(monkeypatch):
    from app import orchestrator

    monkeypatch.setattr(orchestrator, "_cgfp_article_fpt_eligible", lambda *_args: True)
    found = {"results": [{
        "article": "L823-1",
        "matched_concepts": [],
        "relevance_label": "Correspondance lexicale — pertinence à vérifier",
    }]}

    assert orchestrator._cgfp_article_discovery_queries(found) == ["article L823-1"]



def test_public_service_referentiel_expands_agent_vocabulary_without_activating_citations():
    from app.cgfp_relevance import _expand_legal_query

    citis = _expand_legal_query("Mon accident du travail et mon CITIS")
    assert "congé pour invalidité temporaire imputable au service" in citis
    assert "accident de trajet" in citis
    assert "L822-21" not in citis
    assert "87-602" not in citis

    cnfpt = _expand_legal_query("Je souhaite faire évoluer mon emploi-type et ma fiche de poste")
    assert "métier" in cnfpt
    assert "compétence" in cnfpt
    assert "poste de travail" in cnfpt

    tpt = _expand_legal_query("Mon médecin recommande un TPT")
    assert "quotité de travail thérapeutique" in tpt
    assert "réadaptation professionnelle" in tpt


def test_public_service_referentiel_has_provenance_and_unverified_reference_leads():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "app" / "fp_lexical_referentiel.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_ids = {item["id"] for item in payload["sources"]}
    assert {"service_public_fp", "dgafp_tpt_2026", "cnfpt_glossaire_metiers_2026",
            "cnfpt_repertoire", "dgcl_portail", "cig_pc", "legifrance_cgfp"} <= source_ids
    assert len(payload["entries"]) >= 20
    assert all(entry["reference_validation"] == "UNVERIFIED_LEAD_ONLY"
               for entry in payload["entries"])



def test_cgfp_text_cleanup_removes_running_headers_and_only_trailing_navigation():
    from app.cgfp import clean_cgfp_article_text

    raw = (
        "Premier alinéa juridique.\n"
        "Code général de la fonction publique - Dernière modification le 31 octobre 2026 - Document généré le 13 novembre 2026\n"
        "Chapitre Ier : Dispositions générales\n"
        "Deuxième alinéa juridique.\n"
        "Titre II : Dispositions suivantes"
    )
    cleaned = clean_cgfp_article_text(raw)
    assert "Premier alinéa juridique." in cleaned
    assert "Deuxième alinéa juridique." in cleaned
    assert "Dernière modification" not in cleaned
    assert "Titre II : Dispositions suivantes" not in cleaned
    assert "Chapitre Ier : Dispositions générales" in cleaned


def test_snapshot_citation_integrity_rejects_missing_or_invalid_page_metadata():
    from app.cgfp import get_cgfp_article
    from app.legal_validation import validate_snapshot_citation

    article = get_cgfp_article("L4")
    citation = {
        "source_id": article["source_id"],
        "article": "L4",
        "excerpt": article["text"][:300],
    }
    assert validate_snapshot_citation(citation, article)["valid"] is False

    malformed_article = {
        **article,
        "page_start": "not-a-page",
        "page_end": None,
    }
    report = validate_snapshot_citation({
        **citation, "page_start": "not-a-page", "page_end": None,
    }, malformed_article)
    assert report["valid"] is False
    assert report["checks"]["pdf_page_range"] is False


def test_snapshot_citation_integrity_handles_non_mapping_payloads():
    from app.legal_validation import validate_snapshot_citation

    result = validate_snapshot_citation(None, "not-an-article")
    assert result["valid"] is False
    assert result["checks"]["source_identity"] is False
    assert result["checks"]["pdf_page_range"] is False
