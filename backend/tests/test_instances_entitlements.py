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


def test_cap_refusal_of_titularisation_is_distinguished_from_generic_stage_questions():
    result = prepare_instance("CAP", "Refus de titularisation après stage")
    assert any(item["code"] == "refus_titularisation" for item in result["points"])
    assert not any(item["code"] == "stage_licenciement" for item in result["points"])


def test_cap_individual_referral_mentions_current_r263_10_scope():
    result = prepare_instance("CAP", "Refus de télétravail")
    point = next(item for item in result["points"] if item["code"] == "individual_decision_on_request")
    joined = " ".join(point["questions"])
    assert "R. 263-10" in joined
    assert "limitativement énumérés" in joined


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


def test_ccp_discipline_does_not_trigger_for_first_group_sanctions():
    result = prepare_instance("CCP", "Sanction disciplinaire : avertissement")
    assert not any(item["code"] == "discipline" for item in result["points"])


def test_cap_discipline_does_not_trigger_for_first_group_sanctions():
    result = prepare_instance("CAP", "Sanction disciplinaire : blâme du premier groupe")
    assert not any(item["code"] == "discipline" for item in result["points"])


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


def test_ccp_union_mandate_nonrenewal_matches_natural_wording():
    result = prepare_instance(
        "CCP",
        "Non-renouvellement d'un agent contractuel investi d'un mandat syndical",
    )
    assert any(item["code"] == "union_mandate_nonrenewal" for item in result["points"])

