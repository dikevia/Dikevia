from app.fpt_scope import classify_public_service_scope, is_ihts_relevant_source


def test_territorial_scope_is_eligible():
    result = classify_public_service_scope({
        "title": "Décret relatif aux agents de la fonction publique territoriale",
        "full_text": "Les collectivités territoriales et leurs établissements publics.",
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True


def test_hospital_and_state_scopes_are_excluded():
    hospital = classify_public_service_scope({
        "title": "Dispositions relatives à la fonction publique hospitalière",
        "full_text": "Les établissements publics de santé.",
    })
    state = classify_public_service_scope({
        "title": "Agents de la fonction publique de l'État",
        "full_text": "Les fonctionnaires de l'État.",
    })
    assert hospital["scope"] == "FPH" and hospital["analysis_eligible"] is False
    assert state["scope"] == "FPE" and state["analysis_eligible"] is False


def test_general_public_service_scope_needs_multiple_markers():
    eligible = classify_public_service_scope({
        "title": "Droits et obligations des fonctionnaires",
        "full_text": "Le code général de la fonction publique prévoit les garanties des agents publics.",
    })
    ambiguous = classify_public_service_scope({
        "title": "Modalités d'application d'une mesure",
        "full_text": "Dispositions diverses.",
    })
    assert eligible["scope"] == "GENERAL_PUBLIC_SERVICE"
    assert eligible["analysis_eligible"] is True
    assert ambiguous["scope"] == "SCOPE_TO_VERIFY"
    assert ambiguous["analysis_eligible"] is False


def test_ihts_reference_decree_is_eligible():
    result = classify_public_service_scope({
        "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
        "full_text": "Indemnités horaires pour travaux supplémentaires (IHTS).",
    })
    assert result["scope"] == "FPT_REFERENCE"
    assert result["analysis_eligible"] is True
    assert "délibération locale" in result["evidence"][0].lower()


def test_ihts_filter_rejects_unrelated_hour_credits():
    question = "On ne me paie pas mes heures supplémentaires"
    unrelated = [
        {"title": "CGFP R422-96", "article": "R422-96", "excerpt": "Crédit d'heures supplémentaires pour prévenir une inaptitude."},
        {"title": "CGFP L422-15", "article": "L422-15", "excerpt": "Crédit d'heures supplémentaires pour évolution professionnelle."},
        {"title": "CGFP R214-33", "article": "R214-33", "excerpt": "Crédits d'heures syndicales et compensation financière."},
    ]
    assert all(not is_ihts_relevant_source(question, item) for item in unrelated)


def test_ihts_filter_keeps_specific_regime_sources():
    question = "On ne me paie pas mes heures supplémentaires"
    relevant = [
        {"title": "Décret n° 2002-60", "excerpt": "Indemnités horaires pour travaux supplémentaires (IHTS)."},
        {"title": "Décret n° 91-875", "excerpt": "Indemnités horaires pour travaux supplémentaires."},
        {"title": "Décret n° 2001-623", "excerpt": "Organisation du temps de travail et renvoi au décret n° 2002-60."},
    ]
    assert all(is_ihts_relevant_source(question, item) for item in relevant)


def test_other_topics_are_not_filtered_by_ihts_guard():
    assert is_ihts_relevant_source(
        "Mon chef me menace",
        {"title": "CGFP L134-5", "full_text": "Protection fonctionnelle."},
    )
