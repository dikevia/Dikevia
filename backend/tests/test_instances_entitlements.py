from app.entitlements import resolve_entitlements
from app.instances import prepare_instance


def test_agent_entitlement_is_chat_only_and_five_questions_daily():
    ent = resolve_entitlements("AGENT_5_QUESTIONS", "ACTIVE")
    assert ent.chatbot is True
    assert ent.syndicate_tools is False
    assert ent.daily_question_limit == 5
    assert ent.max_users == 1


def test_only_active_current_union_plans_unlock_all_features_without_daily_quota():
    for code, seats in (
        ("SYNDICAT_5_ACCES", 5),
        ("SYNDICAT_10_ACCES", 10),
        ("SYNDICAT_15_ACCES", 15),
    ):
        ent = resolve_entitlements(code, "ACTIVE")
        assert ent.chatbot is True
        assert ent.syndicate_tools is True
        assert ent.daily_question_limit is None
        assert ent.max_users == seats


def test_expired_or_legacy_plans_fail_closed_to_agent_entitlement():
    for code, status in (
        ("SYNDICAT_15_ACCES", "CANCELED"),
        ("EQUIPE_INSTANCES", "ACTIVE"),
        ("COLLECTIVITE_SYNDICATS", "ACTIVE"),
        (None, None),
    ):
        ent = resolve_entitlements(code, status)
        assert ent.syndicate_tools is False
        assert ent.daily_question_limit == 5


def test_verified_founder_keeps_full_access():
    ent = resolve_entitlements(None, None, founder=True)
    assert ent.syndicate_tools is True
    assert ent.daily_question_limit is None


def test_cst_preparation_is_a_checklist_not_a_legal_conclusion():
    result = prepare_instance("CST", "Plan de formation 2026")
    assert result["legal_conclusion"] is False
    assert result["points"][0]["code"] == "formation"
    assert result["documents_a_demander"]
    assert "ne confirme ni la compétence" in result["notice"]


def test_instance_preparation_rejects_unknown_instance_and_empty_object():
    import pytest
    with pytest.raises(ValueError):
        prepare_instance("COLLECTIVITE", "Plan de formation")
    with pytest.raises(ValueError):
        prepare_instance("CST", "  ")


def test_all_four_instances_have_a_defined_preparation_path():
    for instance, text in (
        ("CST", "Organisation du travail"),
        ("CAP", "Sanction disciplinaire"),
        ("CCP", "Non-renouvellement"),
        ("FS", "Risques psychosociaux et surcharge"),
    ):
        result = prepare_instance(instance, text)
        assert result["instance"] == instance
        assert result["points"]

def test_cap_disciplinary_referral_is_limited_to_groups_two_to_four():
    result = prepare_instance(
        "CAP",
        "Sanction disciplinaire : exclusion temporaire de quatre à quinze jours",
    )
    point = next(item for item in result["points"] if item["code"] == "discipline")
    joined = " ".join(point["questions"])
    assert "deuxième, troisième ou quatrième groupes" in joined
    assert "premier groupe" in joined
    assert "quinze jours" in joined
    assert "deux mois" in joined
    assert "un mois en cas de suspension" in joined


def test_cap_refusal_of_titularisation_is_distinguished_from_generic_stage_questions():
    result = prepare_instance("CAP", "Refus de titularisation après stage")
    assert any(item["code"] == "refus_titularisation" for item in result["points"])
    assert not any(item["code"] == "stage_licenciement" for item in result["points"])


def test_cap_individual_referral_mentions_current_r263_10_scope():
    result = prepare_instance("CAP", "Contestation du compte rendu d'entretien professionnel d'un fonctionnaire")
    point = next(item for item in result["points"] if item["code"] == "individual_decision_on_request")
    joined = " ".join(point["questions"])
    assert "R. 263-10" in joined
    assert "limitativement énumérés" in joined
    assert "quinze jours francs" in joined
    assert "dans le mois" in joined


def test_ccp_nonrenewal_does_not_assume_mandate_consultation():
    result = prepare_instance("CCP", "Non-renouvellement d'un contrat")
    point = next(item for item in result["points"] if item["code"] == "fin_contrat")
    joined = " ".join(point["questions"])
    assert "mandat syndical" in joined
    assert "ne doit pas être généralisée" in joined
    assert not any(item["code"] == "union_mandate_nonrenewal" for item in result["points"])


def test_ccp_union_mandate_nonrenewal_has_specific_referral_candidate():
    result = prepare_instance("CCP", "Non-renouvellement mandat syndical")
    assert any(item["code"] == "union_mandate_nonrenewal" for item in result["points"])


def test_ccp_disciplinary_council_inherits_procedure_deadlines_and_composition_rules():
    result = prepare_instance(
        "CCP",
        "Conseil de discipline : sanction disciplinaire, exclusion temporaire de quatre jours",
    )
    point = next(item for item in result["points"] if item["code"] == "discipline")
    joined = " ".join(point["questions"])
    assert "article 37-1" in joined
    assert "quinze jours" in joined
    assert "deux mois" in joined
    assert "magistrat administratif" in joined
    assert "article 37-4" in joined


def test_ccp_protected_agent_dismissal_checks_interview_timing_and_prior_consultation():
    result = prepare_instance(
        "CCP",
        "Licenciement après période d'essai d'un agent contractuel représentant du personnel",
    )
    point = next(item for item in result["points"] if item["code"] == "dismissal_after_trial")
    joined = " ".join(point["questions"])
    assert "cinq jours ouvrables" in joined
    assert "avant l'entretien préalable" in joined
    assert "20 %" in joined
    assert "six mois" in joined


def test_ccp_discipline_does_not_trigger_for_first_group_sanctions():
    result = prepare_instance("CCP", "Sanction disciplinaire : avertissement")
    assert not any(item["code"] == "discipline" for item in result["points"])


def test_cap_discipline_does_not_trigger_for_first_group_sanctions():
    result = prepare_instance("CAP", "Sanction disciplinaire : blâme du premier groupe")
    assert not any(item["code"] == "discipline" for item in result["points"])


def test_ccp_professional_review_referral_checks_contract_eligibility_and_deadlines():
    result = prepare_instance(
        "CCP",
        "Contestation du compte rendu d'entretien professionnel d'un agent contractuel en CDI sur emploi permanent",
    )
    point = next(item for item in result["points"] if item["code"] == "refusal_individual_decision")
    joined = " ".join(point["questions"])
    assert "emploi permanent en CDI ou en CDD de plus d'un an" in joined
    assert "contrat de projet" in joined
    assert "quinze jours francs" in joined
    assert "dans le mois" in joined


def test_ccp_individual_referral_is_separate_from_mandatory_consultation():
    result = prepare_instance("CCP", "Refus de télétravail agent contractuel")
    point = next(item for item in result["points"] if item["code"] == "refusal_individual_decision")
    joined = " ".join(point["questions"])
    assert "R. 272-21" in joined
    assert "à la demande" in point["libelle"]

def test_cap_mandatory_training_refusal_is_distinct_from_agent_requested_referral():
    result = prepare_instance("CAP", "Second refus de formation")
    point = next(item for item in result["points"] if item["code"] == "mandatory_training_refusal")
    joined = " ".join(point["questions"])
    assert "R. 263-7" in joined
    assert "R. 263-10" in joined


def test_cap_reinstatement_after_civil_disqualification_is_covered():
    result = prepare_instance("CAP", "Réintégration après privation des droits civiques")
    point = next(item for item in result["points"] if item["code"] == "reinstatement_after_civil_disqualification")
    assert "R. 263-8" in " ".join(point["questions"])


def test_cap_reclassement_ppr_tracks_medical_opinion_and_procedural_deadlines():
    result = prepare_instance(
        "CAP",
        "Période de préparation au reclassement après avis du conseil médical pour inaptitude aux fonctions du grade",
    )
    point = next(item for item in result["points"] if item["code"] == "reclassement_inaptitude")
    joined = " ".join(point["questions"])
    assert "un an" in joined
    assert "deux mois" in joined
    assert "quinze jours" in joined
    assert "trois mois" in joined
    assert "recours gracieux" in joined
    assert "CAP a-t-elle été consultée" in joined


def test_ccp_physical_unfitness_checks_article_13_specific_redeployment_path():
    result = prepare_instance(
        "CCP",
        "Licenciement pour inaptitude physique définitive d'un agent contractuel",
    )
    point = next(item for item in result["points"] if item["code"] == "physical_unfitness")
    joined = " ".join(point["questions"])
    assert "article 13 III" in joined
    assert "L. 332-8" in joined
    assert "cinq jours ouvrables" in joined
    assert "moitié du préavis" in joined
    assert "trois mois maximum" in joined
    assert "dix semaines" in joined
    assert "dossier médical" in joined


def test_ccp_dismissal_checks_notice_period_and_redeployment_exceptions():
    result = prepare_instance(
        "CCP",
        "Licenciement après période d'essai d'un agent contractuel pour suppression de poste",
    )
    point = next(item for item in result["points"] if item["code"] == "dismissal_after_trial")
    joined = " ".join(point["questions"])
    assert "huit jours" in joined
    assert "un mois" in joined
    assert "deux mois" in joined
    assert "L. 332-8" in joined
    assert "emplois de projet" in joined
    assert "cinq jours ouvrables" in joined


def test_ccp_professional_inadequacy_checks_file_access_and_procedure():
    result = prepare_instance(
        "CCP",
        "Licenciement pour insuffisance professionnelle d'un agent contractuel territorial",
    )
    point = next(item for item in result["points"] if item["code"] == "professional_inadequacy")
    joined = " ".join(point["questions"])
    assert "article 39-2" in joined
    assert "toute pièce" in joined
    assert "cinq jours ouvrables" in joined
    assert "R. 272-19" in joined
    assert "42-1" in joined
    assert "article 39-5" in joined
    assert not any(item["code"] == "discipline" for item in result["points"])


def test_ccp_unpaid_leave_non_reemployment_is_separate_from_redeployment():
    result = prepare_instance(
        "CCP",
        "Licenciement pour impossibilité de réemploi après congé sans rémunération",
    )
    point = next(item for item in result["points"] if item["code"] == "dismissal_after_unpaid_leave")
    joined = " ".join(point["questions"])
    assert "5° du I de l'article 39-3" in joined
    assert "article 33" in joined
    assert "emploi similaire" in joined
    assert "article 39-5 exclut le 5° du I" in joined
    assert "contrat de projet" in joined
    assert "article 38-2" in joined
    assert "après un an" in joined
    assert "42-1" in joined




def test_ccp_project_contract_early_termination_is_not_a_general_reemployment_case():
    result = prepare_instance(
        "CCP",
        "Licenciement pour impossibilité de réemploi après congé sans rémunération d'un agent en contrat de projet",
    )
    point = next(item for item in result["points"] if item["code"] == "dismissal_after_unpaid_leave")
    joined = " ".join(point["questions"])
    assert "contrat de projet" in joined
    assert "article 39-3" in joined
    assert "article 39-5" in joined
    assert "article 38-2" in joined


def test_ccp_ordinary_nonrenewal_uses_post_2025_article_38_1_version():
    result = prepare_instance("CCP", "Non-renouvellement d'un CDD ordinaire")
    point = next(item for item in result["points"] if item["code"] == "fin_contrat")
    joined = " ".join(point["questions"])
    assert "Depuis le 1er octobre 2025" in joined
    assert "I et II de l'article 38-1" in joined
    assert "sont abrogés" in joined
    assert "Ne pas appliquer par défaut les délais du contrat de projet" in joined


def test_ccp_project_contract_end_notice_is_not_generalized_to_all_nonrenewals():
    project = prepare_instance("CCP", "Fin de contrat de projet au terme prévu")
    point = next(item for item in project["points"] if item["code"] == "fin_contrat")
    joined = " ".join(point["questions"])
    assert "deux mois" in joined
    assert "trois mois" in joined
    assert "Ne pas étendre ces délais spécifiques à tous les CDD" in joined

    ordinary = prepare_instance("CCP", "Non-renouvellement d'un CDD ordinaire")
    ordinary_point = next(item for item in ordinary["points"] if item["code"] == "fin_contrat")
    ordinary_joined = " ".join(ordinary_point["questions"])
    assert "Ne pas appliquer par défaut les délais du contrat de projet" in ordinary_joined


def test_ccp_union_mandate_nonrenewal_matches_natural_wording():
    result = prepare_instance(
        "CCP",
        "Non-renouvellement d'un agent contractuel investi d'un mandat syndical",
    )
    assert any(item["code"] == "union_mandate_nonrenewal" for item in result["points"])

