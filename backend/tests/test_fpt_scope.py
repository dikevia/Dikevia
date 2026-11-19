from app.fpt_scope import classify_public_service_scope


def test_explicit_fpt_source_is_eligible():
    result = classify_public_service_scope({
        "title": "Fonction publique territoriale",
        "text": "Les agents territoriaux et les collectivités territoriales sont concernés.",
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True


def test_genuinely_general_public_service_source_is_eligible():
    result = classify_public_service_scope({
        "title": "Code général de la fonction publique",
        "text": "Le présent texte concerne les agents publics et les fonctionnaires.",
    })
    assert result["scope"] == "GENERAL_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is True


def test_unclassified_source_is_not_eligible_for_fpt_analysis():
    result = classify_public_service_scope({
        "title": "Document administratif",
        "text": "Dispositions diverses sans indication de champ d'application.",
    })
    assert result["scope"] == "OUT_OF_SCOPE_OR_UNCONFIRMED"
    assert result["analysis_eligible"] is False


def test_european_union_instrument_is_out_of_scope():
    result = classify_public_service_scope({
        "title": "Directive européenne",
        "jurisdiction": "Union européenne",
        "source_type": "EU_DIRECTIVE",
        "text": "Texte relatif aux agents publics.",
    })
    assert result["scope"] == "OUT_OF_SCOPE_EUROPEAN_LAW"
    assert result["analysis_eligible"] is False


def test_fpe_and_fph_only_sources_are_not_eligible():
    fpe = classify_public_service_scope({
        "title": "Fonction publique de l'État",
        "text": "Les agents de l'État et les administrations centrales.",
    })
    fph = classify_public_service_scope({
        "title": "Fonction publique hospitalière",
        "text": "Les personnels hospitaliers des établissements publics de santé.",
    })
    assert fpe["analysis_eligible"] is False
    assert fph["analysis_eligible"] is False


def test_eu_instrument_is_excluded_from_title_even_without_jurisdiction_metadata():
    result = classify_public_service_scope({
        "title": "Règlement (UE) 2024/1234 relatif aux agents publics",
        "text": "Dispositions générales.",
    })
    assert result["scope"] == "OUT_OF_SCOPE_EUROPEAN_LAW"
    assert result["analysis_eligible"] is False


def test_french_transposition_decree_is_not_misclassified_as_eu_instrument():
    result = classify_public_service_scope({
        "title": "Décret portant transposition de la directive (UE) 2024/1234",
        "text": "Dispositions applicables aux agents de la fonction publique territoriale.",
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True


def test_european_treaty_source_family_is_out_of_scope():
    result = classify_public_service_scope({
        "title": "Convention européenne applicable aux agents publics",
        "jurisdiction": "UE",
        "document_kind": "EUROPEAN_TREATY",
        "text": "Dispositions relatives à la fonction publique.",
    })
    assert result["scope"] == "OUT_OF_SCOPE_EUROPEAN_LAW"
    assert result["analysis_eligible"] is False
