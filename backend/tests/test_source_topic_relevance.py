from app.fpt_scope import is_topic_relevant_source
from app.orchestrator import filter_irrelevant_sources_for_display


def test_relevant_source_for_same_legal_topic_is_kept():
    question = "Quels sont mes droits concernant un congé maladie ?"
    source = {
        "title": "Congé de maladie des fonctionnaires territoriaux",
        "text": "Dispositions relatives au congé de maladie et aux agents territoriaux. " * 4,
    }
    assert is_topic_relevant_source(question, source) is True


def test_source_from_clearly_unrelated_topic_is_rejected():
    question = "Comment sont calculées les heures supplémentaires ?"
    source = {
        "title": "Régime disciplinaire des fonctionnaires",
        "text": "Sanction disciplinaire, conseil de discipline et exclusion temporaire.",
    }
    assert is_topic_relevant_source(question, source) is False


def test_cross_cutting_or_unclassified_source_is_preserved():
    question = "Quels sont mes droits concernant un congé maladie ?"
    source = {
        "title": "Code général de la fonction publique",
        "text": "Les agents publics bénéficient des garanties prévues par les textes applicables.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_multi_topic_question_keeps_either_relevant_source_family():
    question = "Quels sont mes droits en congé maladie et sur ma rémunération ?"
    source = {
        "title": "Rémunération des agents publics",
        "text": "Dispositions relatives au traitement indiciaire et à la rémunération.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_display_filter_hides_explicitly_unrelated_topic_sources():
    sources = [
        {"source_id": "relevant", "topic_relevant": True},
        {"source_id": "unrelated", "topic_relevant": False},
        {"source_id": "legacy_ihts_filter", "ihts_relevant": False},
    ]
    assert [s["source_id"] for s in filter_irrelevant_sources_for_display(sources)] == ["relevant"]



def test_working_time_question_keeps_related_territorial_indemnity_source():
    question = "Comment sont indemnisées les heures supplémentaires ?"
    source = {
        "title": "Décret relatif au régime indemnitaire des fonctionnaires territoriaux",
        "text": "Dispositions relatives au régime indemnitaire applicable aux collectivités territoriales.",
    }
    assert is_topic_relevant_source(question, source) is True


def test_sick_leave_question_keeps_related_remuneration_source():
    question = "Comment est maintenue la rémunération pendant un congé maladie ?"
    source = {
        "title": "Règles de rémunération des agents publics",
        "text": "Dispositions relatives au traitement indiciaire et à la rémunération.",
    }
    assert is_topic_relevant_source(question, source) is True
