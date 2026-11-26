from app.fpt_scope import _matched_topic_families, is_topic_relevant_source


def test_hierarchical_report_question_keeps_file_and_disciplinary_sources_only():
    question = "Mon chef a fait un rapport contre moi, puis-je le contester ?"
    file_source = {
        "title": "Communication du dossier individuel",
        "text": "L'agent peut demander la communication des pièces de son dossier individuel.",
    }
    discipline_source = {
        "title": "Garanties de la procédure disciplinaire",
        "text": "Le fonctionnaire poursuivi a droit à la communication intégrale de son dossier.",
    }
    unrelated = {
        "title": "Organisation du Conseil supérieur de la fonction publique territoriale",
        "text": "Le conseil se réunit quatre fois par an.",
    }
    assert "REPORT_HIERARCHICAL_CONTESTATION" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, file_source) is True
    assert is_topic_relevant_source(question, discipline_source) is True
    assert is_topic_relevant_source(question, unrelated) is False


def test_bereavement_question_rejects_unrelated_leave_and_cgfp_sources():
    question = "Un agent demande une autorisation d'absence après le décès de son grand-père."
    unrelated = [
        {"title": "Congé de longue durée", "text": "Dispositions relatives au congé de longue durée pour raison de santé."},
        {"title": "Autorisation spéciale d'absence syndicale", "text": "Dispositions relatives aux absences liées à l'exercice du droit syndical."},
    ]
    relevant = {
        "title": "Autorisation d'absence pour décès d'un membre de la famille",
        "text": "Les autorisations d'absence pour décès d'un proche et les justificatifs du lien familial doivent être examinés selon les dispositions applicables.",
    }
    assert "FAMILY_BEREAVEMENT" in _matched_topic_families(question)
    assert all(is_topic_relevant_source(question, source) is False for source in unrelated)
    assert is_topic_relevant_source(question, relevant) is True


def test_union_assistance_question_rejects_generic_union_administration():
    question = "Un agent convoqué par sa hiérarchie peut-il bénéficier d'un accompagnement syndical ?"
    unrelated = {
        "title": "Autorisations spéciales d'absence syndicales",
        "text": "Modalités des absences accordées pour congrès et réunions statutaires.",
    }
    relevant = {
        "title": "Garanties disciplinaires et assistance du fonctionnaire",
        "text": "Dans la procédure disciplinaire, le fonctionnaire peut être assisté par un défenseur de son choix.",
    }
    assert "UNION_ASSISTANCE" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, unrelated) is False
    assert is_topic_relevant_source(question, relevant) is True


def test_aggression_question_keeps_functional_protection_but_rejects_unrelated_discipline():
    question = "Un agent a été agressé par un usager et son chef refuse de déclarer l'incident. Quels sont ses droits ?"
    relevant = {
        "title": "Protection fonctionnelle des agents victimes d'une agression",
        "text": "La protection fonctionnelle concerne les agents victimes de violences ou d'agressions.",
    }
    unrelated = {
        "title": "Rapport disciplinaire",
        "text": "Le rapport établi par le supérieur hiérarchique peut être versé au dossier disciplinaire.",
    }
    assert "AGGRESSION_AGENT_PROTECTION" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, relevant) is True
    assert is_topic_relevant_source(question, unrelated) is False
