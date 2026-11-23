from app.fpt_scope import classify_public_service_scope


def test_explicit_fpt_source_is_eligible():
    result = classify_public_service_scope({
        "title": "Fonction publique territoriale",
        "text": "Les agents territoriaux et les collectivités territoriales sont concernés.",
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True


def test_generic_public_service_wording_is_context_only_without_fpt_proof():
    result = classify_public_service_scope({
        "title": "Code général de la fonction publique",
        "text": "Le présent texte concerne les agents publics et les fonctionnaires.",
    })
    assert result["scope"] == "GENERAL_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


def test_explicit_three_branch_scope_is_eligible_for_fpt_analysis():
    result = classify_public_service_scope({
        "title": "Dispositions communes aux trois versants",
        "text": (
            "Les règles concernent les trois versants de la fonction publique : "
            "la fonction publique de l'État, territoriale et hospitalière."
        ),
    })
    assert result["scope"] == "COMMON_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is True


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

def test_staffing_question_rejects_unrelated_code_articles():
    from app.fpt_scope import is_topic_relevant_source

    question = "Ma direction ne renforce pas des équipes en manque de personnel."
    unrelated = {
        "title": "Code général de la fonction publique — article R326-26",
        "excerpt": "La formation est dispensée par un organisme extérieur.",
    }
    relevant = {
        "title": "Prévention des risques professionnels",
        "excerpt": "L'autorité territoriale organise la prévention et l'évaluation des risques professionnels.",
    }
    assert is_topic_relevant_source(question, unrelated) is False
    assert is_topic_relevant_source(question, relevant) is True


def test_titular_termination_question_rejects_unrelated_cst_articles():
    from app.fpt_scope import is_topic_relevant_source

    question = "Je suis titulaire, ma collectivité peut-elle me virer ?"
    unrelated = {
        "title": "Code général de la fonction publique — article R252-44",
        "excerpt": "Chaque titulaire dispose de deux suppléants au comité social.",
    }
    relevant = {
        "title": "Cessation définitive de fonctions",
        "excerpt": "La radiation des cadres met fin à la qualité de fonctionnaire.",
    }
    assert is_topic_relevant_source(question, unrelated) is False
    assert is_topic_relevant_source(question, relevant) is True

def test_staffing_question_keeps_relevant_hygiene_and_preventive_medicine_sources():
    from app.fpt_scope import is_topic_relevant_source

    question = "Ma direction ne renforce pas des équipes en manque de personnel."
    hygiene_source = {
        "title": "Hygiène et sécurité au travail",
        "excerpt": "Les règles d'hygiène et de sécurité protègent les agents territoriaux.",
    }
    preventive_medicine_source = {
        "title": "Médecine préventive",
        "excerpt": "Le service de médecine préventive conseille l'autorité territoriale.",
    }
    assert is_topic_relevant_source(question, hygiene_source) is True
    assert is_topic_relevant_source(question, preventive_medicine_source) is True


def test_titular_query_activates_strict_relevance_filter_without_false_positive_on_cst_titular():
    from app.fpt_scope import is_topic_relevant_source

    question = "Je suis titulaire, ma collectivité peut-elle me virer ?"
    unrelated = {
        "title": "Code général de la fonction publique — article R252-44",
        "excerpt": "Chaque titulaire dispose de deux suppléants au comité social.",
    }
    assert is_topic_relevant_source(question, unrelated) is False



def test_plain_language_phrasing_activates_the_same_strict_relevance_filter():
    from app.fpt_scope import is_topic_relevant_source

    unrelated = {
        "title": "Code général de la fonction publique — article R326-26",
        "excerpt": "La formation est dispensée par un organisme extérieur.",
    }
    assert is_topic_relevant_source(
        "Dans mon service on n'est pas assez nombreux.", unrelated
    ) is False
    assert is_topic_relevant_source(
        "Ma collectivité veut me mettre dehors.", unrelated
    ) is False



def test_fpe_title_is_not_overridden_by_incidental_fpt_reference_in_body():
    result = classify_public_service_scope({
        "title": "Décret relatif à la fonction publique de l'État",
        "text": (
            "Les agents de l'État sont concernés. Le texte mentionne également "
            "les collectivités territoriales à titre de comparaison."
        ),
    })
    assert result["scope"] == "FPE"
    assert result["analysis_eligible"] is False


def test_fph_title_is_not_overridden_by_incidental_fpt_reference_in_body():
    result = classify_public_service_scope({
        "title": "Dispositions relatives à la fonction publique hospitalière",
        "text": (
            "Les personnels hospitaliers sont concernés. Une référence aux "
            "agents territoriaux figure dans une disposition de coordination."
        ),
    })
    assert result["scope"] == "FPH"
    assert result["analysis_eligible"] is False


def test_mixed_versant_body_without_primary_scope_is_not_assumed_fpt():
    result = classify_public_service_scope({
        "title": "Dispositions communes aux agents publics",
        "text": (
            "Les fonctionnaires territoriaux et les agents de l'État "
            "sont mentionnés dans des dispositions distinctes."
        ),
    })
    assert result["scope"] == "OUT_OF_SCOPE_OR_UNCONFIRMED"
    assert result["analysis_eligible"] is False


def test_explicit_fpt_title_can_contain_cross_versant_reference():
    result = classify_public_service_scope({
        "title": "Décret relatif à la fonction publique territoriale",
        "text": (
            "Les fonctionnaires territoriaux sont concernés. Une disposition "
            "renvoie, pour comparaison, aux agents de l'État."
        ),
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True

def test_single_generic_public_service_marker_is_not_enough_even_for_context():
    result = classify_public_service_scope({
        "title": "Document administratif",
        "text": "Le texte concerne les agents publics.",
    })
    assert result["scope"] == "GENERAL_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is False
    assert result["claim_eligible"] is False

def test_annual_evaluation_question_rejects_clearly_unrelated_topics():
    from app.fpt_scope import is_topic_relevant_source

    question = "Mon agent de maîtrise m'as fait une évaluation annuelle à charge, puis-je la contester ?"
    unrelated = {
        "title": "Protection fonctionnelle",
        "excerpt": "L'agent public bénéficie d'une protection contre les menaces et violences.",
    }
    relevant = {
        "title": "Appréciation de la valeur professionnelle",
        "excerpt": "L'entretien professionnel annuel donne lieu à un compte rendu d'évaluation.",
    }
    cross_cutting = {
        "title": "Recours administratif",
        "excerpt": "La décision administrative peut faire l'objet d'un recours préalable.",
    }

    assert is_topic_relevant_source(question, unrelated) is False
    assert is_topic_relevant_source(question, relevant) is True
    # Unrecognized procedural material remains eligible for review; the
    # topic guard must not discard potentially cross-cutting appeal provisions.
    assert is_topic_relevant_source(question, cross_cutting) is True



def test_cgfp_article_l521_3_is_classified_as_territorial():
    source = {
        "title": "Code général de la fonction publique — article L521-3",
        "text": (
            "Le compte rendu concernant un fonctionnaire territorial en fonction "
            "dans une collectivité ou un établissement mentionné à l'article L. 4 "
            "est visé par l'autorité territoriale."
        ),
        "document_kind": "CODE",
    }
    scope = classify_public_service_scope(source)
    assert scope["scope"] == "FPT"
    assert scope["analysis_eligible"] is True


def test_cgfp_permanent_contractual_employment_articles_are_classified_as_fpt():
    for article in ("L332-8", "L332-9", "L332-10", "L332-11", "L332-12", "L332-13", "L332-14"):
        result = classify_public_service_scope({
            "title": f"Code général de la fonction publique — article {article}",
            "article": article,
            "text": "Dispositions relatives aux agents contractuels recrutés sur un emploi permanent.",
            "document_kind": "CODE",
        })
        assert result["scope"] == "FPT"
        assert result["analysis_eligible"] is True



def test_citis_articles_remain_context_only_without_branch_implementation_proof():
    for number in range(18, 24):
        article = f"L822-{number}"
        result = classify_public_service_scope({
            "title": f"Code général de la fonction publique — article {article}",
            "article": article,
            "text": "Le fonctionnaire bénéficie des dispositions prévues au présent chapitre.",
            "document_kind": "CODE",
        })
        assert result["scope"] == "GENERAL_PUBLIC_SERVICE"
        assert result["analysis_eligible"] is True
        assert result["claim_eligible"] is False


def test_live_cgfp_tpt_articles_are_common_claim_evidence_but_snapshot_is_not():
    for number in range(1, 7):
        article = f"L823-{number}"
        common = {
            "title": f"Code général de la fonction publique — article {article}",
            "article": article,
            "text": "Le fonctionnaire bénéficie des dispositions prévues au présent chapitre.",
            "document_kind": "CODE",
        }
        snapshot = classify_public_service_scope({
            **common, "source_type": "CGFP_SNAPSHOT",
        }, target_versant="FPT")
        assert snapshot["scope"] == "COMMON_PUBLIC_SERVICE"
        assert snapshot["analysis_eligible"] is True
        assert snapshot["claim_eligible"] is False

        for versant in ("FPT", "FPE", "FPH"):
            live = classify_public_service_scope({
                **common, "source_type": "LEGIFRANCE_API",
            }, target_versant=versant)
            assert live["scope"] == "COMMON_PUBLIC_SERVICE"
            assert live["analysis_eligible"] is True
            assert live["claim_eligible"] is True


def test_public_service_scope_is_eligible_only_for_the_selected_versant():
    fpe = {
        "title": "Décret relatif à la fonction publique de l'État",
        "text": "Les agents de la fonction publique de l'État sont concernés.",
    }
    fph = {
        "title": "Décret relatif à la fonction publique hospitalière",
        "text": "Les personnels de la fonction publique hospitalière sont concernés.",
    }
    for target in ("FPT", "FPH"):
        assert classify_public_service_scope(fpe, target_versant=target)["analysis_eligible"] is False
    assert classify_public_service_scope(fpe, target_versant="FPE")["analysis_eligible"] is True
    for target in ("FPT", "FPE"):
        assert classify_public_service_scope(fph, target_versant=target)["analysis_eligible"] is False
    assert classify_public_service_scope(fph, target_versant="FPH")["analysis_eligible"] is True


def test_explicitly_common_public_service_rule_remains_available_to_each_versant():
    source = {
        "title": "Dispositions communes aux trois versants de la fonction publique",
        "text": "Les agents des trois versants de la fonction publique bénéficient de cette garantie.",
    }
    for target in ("FPT", "FPE", "FPH"):
        result = classify_public_service_scope(source, target_versant=target)
        assert result["scope"] == "COMMON_PUBLIC_SERVICE"
        assert result["analysis_eligible"] is True
        assert result["claim_eligible"] is True


def test_official_fpe_and_fph_contractual_decrees_are_classified_by_their_own_scope():
    fpe_decree = {
        "title": "Décret n° 86-83 du 17 janvier 1986 relatif aux dispositions générales applicables aux agents contractuels de l'État",
        "text": "Les dispositions du présent décret s'appliquent aux agents contractuels de l'État.",
    }
    fph_decree = {
        "title": "Décret n° 91-155 du 6 février 1991 relatif aux agents contractuels des établissements mentionnés à l'article 2 de la loi n° 86-33",
        "text": "Le présent décret concerne les agents contractuels hospitaliers.",
    }
    assert classify_public_service_scope(fpe_decree, target_versant="FPE")["analysis_eligible"] is True
    assert classify_public_service_scope(fpe_decree, target_versant="FPT")["analysis_eligible"] is False
    assert classify_public_service_scope(fph_decree, target_versant="FPH")["analysis_eligible"] is True
    assert classify_public_service_scope(fph_decree, target_versant="FPE")["analysis_eligible"] is False

def test_fpt_ihts_reference_marker_cannot_override_an_fpe_or_fph_title():
    fpe_source = {
        "title": "Décret relatif aux agents de la fonction publique de l'État",
        "text": (
            "Les agents de l'État sont concernés. Le texte cite le décret n° 2002-60 "
            "relatif aux indemnités horaires pour travaux supplémentaires à titre de comparaison."
        ),
    }
    fph_source = {
        "title": "Décret relatif aux personnels de la fonction publique hospitalière",
        "text": (
            "Les personnels hospitaliers sont concernés. Le texte cite le décret n° 2002-60 "
            "relatif aux indemnités horaires pour travaux supplémentaires à titre de comparaison."
        ),
    }

    assert classify_public_service_scope(fpe_source, "FPE")["scope"] == "FPE"
    assert classify_public_service_scope(fpe_source, "FPE")["analysis_eligible"] is True
    assert classify_public_service_scope(fpe_source, "FPT")["analysis_eligible"] is False

    assert classify_public_service_scope(fph_source, "FPH")["scope"] == "FPH"
    assert classify_public_service_scope(fph_source, "FPH")["analysis_eligible"] is True
    assert classify_public_service_scope(fph_source, "FPT")["analysis_eligible"] is False


def test_ihts_reference_remains_fpt_only_after_title_scope_precedence():
    source = {
        "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
        "text": "Le régime est utilisé dans le cadre indemnitaire territorial.",
    }
    fpt = classify_public_service_scope(source, "FPT")
    fpe = classify_public_service_scope(source, "FPE")
    fph = classify_public_service_scope(source, "FPH")

    assert fpt["scope"] == "FPT_REFERENCE"
    assert fpt["analysis_eligible"] is True
    assert fpe["analysis_eligible"] is False
    assert fph["analysis_eligible"] is False

def test_incidental_ihts_citation_does_not_reclassify_a_mixed_scope_source():
    result = classify_public_service_scope({
        "title": "Note de service sur les régimes indemnitaires des agents publics",
        "text": (
            "Le décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires "
            "est cité à titre de comparaison. Le document mentionne les agents territoriaux "
            "et les agents de l'État dans des parties distinctes."
        ),
    })
    assert result["scope"] == "OUT_OF_SCOPE_OR_UNCONFIRMED"
    assert result["analysis_eligible"] is False

def test_unrelated_source_cannot_claim_common_tpt_scope_from_article_number_alone():
    result = classify_public_service_scope({
        "source_type": "LEGIFRANCE_API",
        "title": "Décret relatif à un régime de santé particulier",
        "article": "L823-4",
        "text": "Le fonctionnaire perçoit sa rémunération dans les conditions prévues.",
    }, target_versant="FPT")
    assert result["scope"] != "COMMON_PUBLIC_SERVICE"
    assert result.get("claim_eligible") is not True



def test_fpe_source_is_eligible_only_for_fpe_target():
    source = {
        "title": "Décret relatif à la fonction publique de l'État",
        "text": "Les agents de l'État et les administrations centrales sont concernés.",
    }
    fpe = classify_public_service_scope(source, target_versant="FPE")
    fpt = classify_public_service_scope(source, target_versant="FPT")
    fph = classify_public_service_scope(source, target_versant="FPH")

    assert fpe["scope"] == "FPE"
    assert fpe["analysis_eligible"] is True
    assert fpt["analysis_eligible"] is False
    assert fph["analysis_eligible"] is False


def test_fph_source_is_eligible_only_for_fph_target():
    source = {
        "title": "Dispositions relatives à la fonction publique hospitalière",
        "text": "Les personnels hospitaliers des établissements publics de santé sont concernés.",
    }
    fph = classify_public_service_scope(source, target_versant="FPH")
    fpt = classify_public_service_scope(source, target_versant="FPT")
    fpe = classify_public_service_scope(source, target_versant="FPE")

    assert fph["scope"] == "FPH"
    assert fph["analysis_eligible"] is True
    assert fpt["analysis_eligible"] is False
    assert fpe["analysis_eligible"] is False


def test_explicit_common_scope_is_eligible_for_all_three_versants():
    source = {
        "title": "Dispositions communes aux trois versants",
        "text": (
            "Les règles concernent les trois versants de la fonction publique : "
            "la fonction publique de l'État, territoriale et hospitalière."
        ),
    }
    for versant in ("FPT", "FPE", "FPH"):
        result = classify_public_service_scope(source, target_versant=versant)
        assert result["scope"] == "COMMON_PUBLIC_SERVICE"
        assert result["analysis_eligible"] is True
        assert result["claim_eligible"] is True


def test_mixed_fpt_and_fpe_instrument_is_not_classified_as_fpt_proof():
    result = classify_public_service_scope({
        "title": "Décret relatif aux agents territoriaux et aux agents de l'État",
        "text": "Les agents territoriaux et les agents de l'État sont concernés.",
    })
    assert result["scope"] == "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE"
    assert result["analysis_eligible"] is False
    assert result["claim_eligible"] is False


def test_scope_classification_uses_relevant_excerpt_before_unrelated_full_text():
    result = classify_public_service_scope({
        "title": "Dispositions statutaires des agents",
        "excerpt": "Les agents territoriaux et les collectivités territoriales sont concernés.",
        "full_text": "Les agents de l'État et les administrations centrales sont concernés.",
    })
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True
