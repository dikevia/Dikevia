"""Offline evaluation corpus for natural-language FPT legal query planning.

These cases measure retrieval routing only. They do not certify source relevance,
legal applicability, or the correctness of a final legal answer.
"""
import pytest

from app.legal_search_plan import build_official_search_queries


# Everyday and formal formulations representative of FPT agent/union questions.
# The expected marker must appear in at least one focused query (not necessarily
# the user's first, wording-preserving query).
FPT_RETRIEVAL_CASES = [
    (
        "On me paie pas mes heures sup.",
        ("IHTS", "décret 2002-60"),
    ),
    (
        "La mairie ne veut pas renouveler mon CDD.",
        ("agents contractuels", "décret 88-145"),
    ),
    (
        "J'ai pris un blâme et je veux contester.",
        ("discipline fonction publique territoriale", "droits défense"),
    ),
    (
        "Mon ASA syndicale est refusée.",
        ("CGFP livre II", "droit syndical"),
    ),
    (
        "Je subis un harcèlement moral dans mon service.",
        ("harcèlement moral", "agent public territorial"),
    ),
    (
        "La collectivité refuse ma protection fonctionnelle.",
        ("protection fonctionnelle", "agent territorial"),
    ),
    (
        "Mon CITIS après un accident de service est refusé.",
        ("CITIS agent territorial", "décret 87-602"),
    ),
    (
        "Ma collectivité ne verse plus mon IFSE.",
        ("régime indemnitaire", "délibération locale"),
    ),
    (
        "Dans mon service on n'est pas assez nombreux.",
        ("decret 85-603", "charge de travail"),
    ),
    (
        "Je suis titulaire, ma collectivité veut me virer.",
        ("radiation des cadres", "cessation definitive de fonctions"),
    ),
    (
        "Comment fonctionne l'annualisation et les RTT ?",
        ("décret 2001-623", "cycles"),
    ),
    (
        "Et pour les contractuels ?",
        ("décret 88-145", "agents contractuels territoriaux"),
    ),
]


@pytest.mark.parametrize("question, expected_markers", FPT_RETRIEVAL_CASES)
def test_natural_language_fpt_corpus_reaches_expected_research_axis(
    question, expected_markers
):
    queries = build_official_search_queries(question)

    assert queries
    assert queries[0].startswith(question)
    assert len(queries) <= 3
    assert len(queries) == len(set(queries))
    assert all(len(query) <= 500 for query in queries)
    joined = " ".join(queries).casefold()
    for marker in expected_markers:
        assert marker.casefold() in joined


def test_compound_question_retains_two_independent_legal_topics():
    question = (
        "Mon ASA syndicale est refusée et je fais aussi l'objet "
        "d'une sanction disciplinaire."
    )
    queries = build_official_search_queries(question)

    assert len(queries) == 3
    assert "droit syndical" in queries[1].casefold()
    assert "discipline fonction publique territoriale" in queries[2].casefold()


def test_unrecognized_everyday_question_stays_in_fpt_scope_without_inventing_topic():
    question = "Mon chef me convoque sans explication."
    queries = build_official_search_queries(question)

    assert len(queries) == 3
    assert queries[0].startswith(question)
    assert "fonction publique territoriale" in queries[0]
    assert "CGFP" in queries[1]
    assert "jurisprudence administrative" in queries[2]
    # No unsupported assumption that a summons is disciplinary or abusive.
    assert "harcèlement moral" not in " ".join(queries).casefold()
    assert "sanction disciplinaire" not in " ".join(queries).casefold()


def test_exact_article_request_remains_a_single_exact_retrieval_query():
    question = "Que prévoit l'article L123-4 du CGFP ?"
    assert build_official_search_queries(question) == [question]


# Coverage gaps found by reviewing the repository's 100-case FPT evaluation set.
ADDITIONAL_FPT_CASES = [
    ("Mon supérieur peut-il refuser mes congés annuels ?", "décret 85-1250"),
    ("Comment fonctionne le compte épargne-temps dans ma collectivité ?", "décret 2004-878"),
    ("Qui me rémunère pendant un congé de maladie ordinaire ?", "congé maladie ordinaire"),
    ("Mon avancement d'échelon peut-il être retardé ?", "CGFP livre V"),
    ("Le CST doit-il être consulté avant une réorganisation ?", "décret 2021-571"),
    ("Puis-je demander le télétravail pour raison médicale ?", "décret 2016-151"),
    ("Comment signaler un danger grave et imminent ?", "droit de retrait"),
    ("Puis-je demander une disponibilité pour suivre mon conjoint ?", "mobilité fonctionnaires territoriaux"),
    ("Quels sont mes droits si mon poste est supprimé ?", "suppression emploi"),
    ("Puis-je cumuler une activité indépendante avec mon emploi territorial ?", "décret 2020-69"),
    ("Que faire si ma collectivité ne répond pas à ma demande ?", "CRPA"),
]


@pytest.mark.parametrize("question, expected_marker", ADDITIONAL_FPT_CASES)
def test_missing_fpt_domains_have_dedicated_research_axes(question, expected_marker):
    queries = build_official_search_queries(question)
    assert len(queries) == 3
    assert expected_marker.casefold() in " ".join(queries).casefold()


def test_cst_questions_are_not_misrouted_as_union_rights_questions():
    queries = build_official_search_queries(
        "Le comité social territorial doit-il être consulté avant une réorganisation ?"
    )
    joined = " ".join(queries).casefold()
    assert "décret 2021-571" in joined
    assert "droit syndical" not in joined
    assert "autorisations speciales absence syndicale" not in joined


def test_threat_by_service_user_reaches_functional_protection_research():
    queries = build_official_search_queries(
        "Un usager m'a menacé pendant mon service : puis-je demander la protection fonctionnelle ?"
    )
    assert "protection fonctionnelle agent territorial" in " ".join(queries).casefold()


def test_all_100_business_evaluation_questions_have_bounded_fpt_retrieval_queries():
    import json
    from pathlib import Path

    repository_root = Path(__file__).resolve().parents[2]
    dataset_path = repository_root / "docs" / "quality" / "fpt_chatbot_eval_v1.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    assert dataset["case_count"] == 100
    for case in dataset["cases"]:
        queries = build_official_search_queries(case["question"])
        assert queries, case["id"]
        assert queries[0].startswith(case["question"]), case["id"]
        assert len(queries) <= 3, case["id"]
        assert len(queries) == len(set(queries)), case["id"]
        assert all(len(query) <= 500 for query in queries), case["id"]
        assert "code du travail" not in " ".join(queries).casefold(), case["id"]


@pytest.mark.parametrize(
    "question, expected_marker",
    [
        ("Mon chef me demande de rester après mon horaire sans validation écrite.", "IHTS"),
        ("Puis-je être rappelé pendant mes congés annuels ?", "décret 85-1250"),
        ("Un usager m'a menacé pendant mon service.", "protection fonctionnelle"),
        ("La collectivité doit-elle protéger un agent victime de harcèlement ?", "protection fonctionnelle"),
        ("Mon employeur doit-il enquêter après un signalement de harcèlement ?", "protection fonctionnelle"),
        ("Puis-je obtenir réparation après une agression au travail ?", "protection fonctionnelle"),
        ("Je suis poursuivi pénalement pour des faits liés au service.", "protection fonctionnelle"),
    ],
)
def test_additional_everyday_fpt_formulations_reach_relevant_sources(
    question, expected_marker
):
    queries = build_official_search_queries(question)
    assert expected_marker.casefold() in " ".join(queries).casefold()


@pytest.mark.parametrize(
    "question, expected_marker",
    [
        ("Puis-je distribuer un tract syndical dans les locaux ?", "CGFP livre II"),
        ("Un agent contractuel peut-il exercer un mandat syndical ?", "CGFP livre II"),
        ("Je suis convoqué à un entretien disciplinaire.", "discipline fonction publique territoriale"),
        ("La suspension de fonctions est-elle déjà une sanction ?", "droits défense"),
        ("Peut-on me sanctionner pour avoir refusé un ordre manifestement illégal ?", "discipline fonction publique territoriale"),
        ("Mon administration peut-elle demander le motif médical détaillé de mon arrêt ?", "secret médical"),
        ("Que devient mon solde de congés si je quitte la collectivité ?", "décret 85-1250"),
        ("Mon employeur peut-il modifier mes missions sans changer mon grade ?", "CGFP livre V"),
        ("Une baisse de primes peut-elle accompagner un changement d'affectation ?", "régime indemnitaire"),
        ("Puis-je refuser un poste si les conditions de sécurité sont dangereuses ?", "décret 85-603"),
        ("Puis-je être sanctionné après avoir signalé des risques psychosociaux ?", "droit de retrait"),
    ],
)
def test_fpt_domain_aliases_keep_specific_retrieval_context(question, expected_marker):
    queries = build_official_search_queries(question)
    assert expected_marker.casefold() in " ".join(queries).casefold()
