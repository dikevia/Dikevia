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
        ("décret 85-603", "charge de travail"),
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
