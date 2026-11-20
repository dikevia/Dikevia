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


def test_ihts_decree_2002_60_is_only_an_fpt_reference_when_its_subject_is_verified():
    result = classify_public_service_scope({
        "source_type": "LEGIFRANCE_LODA",
        "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
        "full_text": (
            "Le décret fixe les modalités des indemnités horaires pour travaux supplémentaires "
            "et constitue une référence à vérifier avec le décret 91-875 et la délibération locale."
        ),
    })
    assert result["scope"] == "FPT_REFERENCE"
    assert result["analysis_eligible"] is True

    unrelated_fpe = classify_public_service_scope({
        "source_type": "LEGIFRANCE_LODA",
        "title": "Décret n° 2002-60",
        "full_text": "Les personnels civils de l'État et des administrations centrales.",
    })
    assert unrelated_fpe["scope"] == "FPE"
    assert unrelated_fpe["analysis_eligible"] is False


def test_decree_91_875_with_territorial_scope_is_eligible_for_fpt():
    result = classify_public_service_scope({
        "source_type": "LEGIFRANCE_LODA",
        "title": "Décret n° 91-875 relatif au régime indemnitaire des collectivités territoriales",
        "full_text": (
            "Les fonctionnaires territoriaux et les agents des collectivités territoriales "
            "peuvent bénéficier des indemnités dans les conditions prévues par les textes."
        ),
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True


def test_ihts_filter_rejects_unrelated_article_mentioning_decree_2001_623():
    from app.fpt_scope import is_ihts_relevant_source

    source = {
        "source_type": "LEGIFRANCE_API",
        "article": "R431-3",
        "title": "Code général de la fonction publique — article R431-3",
        "text": (
            "Les périodes d'astreintes mentionnées à l'article 5 du décret "
            "n° 2001-623 du 12 juillet 2001 ne constituent pas du télétravail."
        ),
    }
    assert is_ihts_relevant_source("On me paie pas mes heures supplémentaires.", source) is False


def test_ihts_filter_keeps_the_ihts_decrees():
    from app.fpt_scope import is_ihts_relevant_source

    assert is_ihts_relevant_source(
        "On me paie pas mes heures supplémentaires.",
        {
            "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
            "text": "Indemnités horaires pour travaux supplémentaires.",
        },
    ) is True
    assert is_ihts_relevant_source(
        "On me paie pas mes heures supplémentaires.",
        {
            "title": "Décret n° 91-875 relatif au régime indemnitaire des collectivités territoriales",
            "text": "Fonctionnaires territoriaux et collectivités territoriales.",
        },
    ) is True
