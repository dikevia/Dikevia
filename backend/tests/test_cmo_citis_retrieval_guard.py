from app.fpt_scope import _matched_topic_families, is_topic_relevant_source


def test_ordinary_sick_leave_question_rejects_citis_source():
    question = (
        "Quelles sont les règles du congé de maladie ordinaire, "
        "notamment le jour de carence et le maintien de rémunération ?"
    )
    source = {
        "title": "Code général de la fonction publique — article L822-21",
        "article": "L822-21",
        "text": (
            "Le fonctionnaire en activité a droit à un congé pour invalidité "
            "temporaire imputable au service lorsque son incapacité temporaire "
            "de travail est consécutive à un accident reconnu imputable au service."
        ),
    }
    assert "ORDINARY_SICK_LEAVE" in _matched_topic_families(question)
    assert "CITIS" in _matched_topic_families(source["text"])
    assert is_topic_relevant_source(question, source) is False


def test_citis_question_keeps_citis_source():
    question = (
        "Quelles sont les conditions du congé pour invalidité temporaire "
        "imputable au service (CITIS) ?"
    )
    source = {
        "title": "Code général de la fonction publique — article L822-21",
        "article": "L822-21",
        "text": (
            "Le fonctionnaire a droit à un congé pour invalidité temporaire "
            "imputable au service après un accident reconnu imputable au service."
        ),
    }
    assert "CITIS" in _matched_topic_families(question)
    assert is_topic_relevant_source(question, source) is True


def test_ordinary_sick_leave_keeps_ordinary_sick_leave_source():
    question = "Quelles sont les règles du congé de maladie ordinaire et du jour de carence ?"
    source = {
        "title": "Congé de maladie du fonctionnaire",
        "text": (
            "Le fonctionnaire peut bénéficier d'un congé de maladie ordinaire. "
            "Le jour de carence s'applique selon les conditions prévues par les textes."
        ),
    }
    assert is_topic_relevant_source(question, source) is True


def test_generic_sick_leave_question_still_keeps_relevant_sick_leave_source():
    question = "Quels sont mes droits concernant un congé maladie ?"
    source = {
        "title": "Congé de maladie des fonctionnaires territoriaux",
        "text": "Dispositions relatives au congé de maladie et aux agents territoriaux.",
    }
    assert is_topic_relevant_source(question, source) is True
