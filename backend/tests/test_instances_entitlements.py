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
