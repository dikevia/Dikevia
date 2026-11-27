from datetime import date

from app.cst_qualification import (
    CST_TOPIC_RULES,
    assess_cst_agenda_request,
    assess_fs_nine_month_trigger,
    calculate_fs_inspector_request_deadlines,
    calculate_cst_meeting_deadlines,
    assess_annual_instance_meeting_frequency,
    calculate_cst_written_request_deadline,
    qualify_cst_topic,
    qualify_fs_topic,
    assess_cst_fs_competence_routing,
)
from app.instances import prepare_instance


def test_cst_projects_are_flagged_as_consultation_candidates_not_legal_conclusions():
    result = qualify_cst_topic("Projet de suppression d'emploi")

    assert result["status"] == "CANDIDATES_FOUND"
    assert result["candidates"][0]["reference"] == "R. 253-7, 14°"
    assert result["candidates"][0]["category"] == "consultation"
    assert result["candidates"][0]["status"] == "candidate_a_verifier"
    assert result["legal_conclusion"] is False


def test_cst_rsu_project_and_annual_rsu_debate_are_not_confused():
    project = qualify_cst_topic("Projet de rapport social unique")
    debate = qualify_cst_topic("Évolution des politiques RH sur la base du RSU")

    assert any(item["category"] == "consultation" for item in project["candidates"])
    assert all(item["category"] != "debate" for item in project["candidates"])
    assert any(item["category"] == "debate" for item in debate["candidates"])
    assert all(item["category"] != "consultation" for item in debate["candidates"])


def test_cst_annual_training_report_is_a_debate_not_a_project_consultation():
    result = qualify_cst_topic("Bilan annuel du plan de formation")

    assert any(item["category"] == "debate" for item in result["candidates"])
    assert all(item["category"] != "consultation" for item in result["candidates"])


def test_cst_information_is_separated_from_consultation_and_debate():
    result = qualify_cst_topic("Actualisation de la base de données sociales")

    assert [item["category"] for item in result["candidates"]] == ["information"]
    assert result["candidates"][0]["reference"] == "R. 253-10, 2°"


def test_health_safety_routing_requires_knowledge_of_specialized_committee():
    unknown = qualify_cst_topic("Mise à jour du DUERP")
    with_fs = qualify_cst_topic("Mise à jour du DUERP", formation_specialisee_exists=True)
    without_fs = qualify_cst_topic("Mise à jour du DUERP", formation_specialisee_exists=False)

    assert unknown["health_safety_routing"] == "indetermine"
    assert with_fs["health_safety_routing"] == "formation_specialisee_a_examiner"
    assert without_fs["health_safety_routing"] == "cst_competence_sante_securite_a_examiner"
    assert all(item["legal_conclusion"] is False for item in (unknown, with_fs, without_fs))


def test_cst_meeting_deadlines_use_current_cgfp_references_and_urgency_only_changes_convocation():
    normal = calculate_cst_meeting_deadlines(date(2026, 12, 20))
    urgent = calculate_cst_meeting_deadlines(date(2026, 12, 20), urgent=True)

    assert normal["convocation_target_date"] == "2026-12-05"
    assert normal["documents_target_date"] == "2026-12-12"
    assert urgent["convocation_target_date"] == "2026-12-12"
    assert urgent["documents_target_date"] == "2026-12-12"
    assert "CGFP R. 254-38" in normal["references"]
    assert "CGFP R. 254-39" in normal["references"]


def test_cst_preparation_exposes_structured_qualification_without_changing_other_instances():
    cst = prepare_instance("CST", "Projet de plan de formation")
    cap = prepare_instance("CAP", "Sanction disciplinaire")

    assert cst["cst_qualification"]["legal_conclusion"] is False
    assert cst["cst_qualification"]["candidates"][0]["reference"] == "R. 253-7, 13°"
    assert "cst_qualification" not in cap

def test_cst_preparation_uses_declared_specialized_committee_context():
    result = prepare_instance(
        "CST",
        "Mise à jour du DUERP",
        formation_specialisee_exists=True,
    )

    assert result["cst_qualification"]["health_safety_routing"] == "formation_specialisee_a_examiner"

def test_cst_reference_catalog_covers_current_cgfp_rubric_counts():
    consultation = [item for item in CST_TOPIC_RULES if item["kind"] == "consultation"]
    debates = [item for item in CST_TOPIC_RULES if item["kind"] == "debate"]
    information = [item for item in CST_TOPIC_RULES if item["kind"] == "information"]

    assert len(consultation) == 24
    assert len(debates) == 12  # R. 253-8 annual programming + 11 R. 253-9 subjects
    assert len(information) == 4


def test_cst_instance_page_exposes_specialized_committee_context_and_candidate_output():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    source = frontend.read_text(encoding="utf-8")

    assert "formationSpecialiseeStatus" in source
    assert "formation_specialisee_exists" in source
    assert "cst_qualification" in source
    assert "Qualification indicative du sujet CST" in source



def test_cst_agenda_request_requires_half_of_titular_representatives_and_competence():
    below = assess_cst_agenda_request(
        titular_representatives=7,
        requesting_titular_representatives=3,
        requested_topic_in_competence=True,
    )
    pending = assess_cst_agenda_request(
        titular_representatives=7,
        requesting_titular_representatives=4,
        requested_topic_in_competence=None,
    )
    required = assess_cst_agenda_request(
        titular_representatives=7,
        requesting_titular_representatives=4,
        requested_topic_in_competence=True,
    )
    disputed = assess_cst_agenda_request(
        titular_representatives=8,
        requesting_titular_representatives=4,
        requested_topic_in_competence=False,
    )

    assert below["status"] == "THRESHOLD_NOT_REACHED"
    assert pending["status"] == "COMPETENCE_TO_VERIFY"
    assert required["status"] == "AGENDA_INCLUSION_REQUIRED"
    assert required["minimum_requesters"] == 4
    assert disputed["status"] == "COMPETENCE_DISPUTED"
    assert all(item["legal_conclusion"] is False for item in (below, pending, required, disputed))


def test_cst_agenda_request_rejects_invalid_representative_counts():
    import pytest

    with pytest.raises(ValueError):
        assess_cst_agenda_request(
            titular_representatives=5,
            requesting_titular_representatives=6,
            requested_topic_in_competence=True,
        )



def test_cst_agenda_request_controls_are_wired_to_instance_preparation_ui():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    source = frontend.read_text(encoding="utf-8")

    assert "cstAgendaRequestField" in source
    assert "cstTitularCount" in source
    assert "cstRequestingCount" in source
    assert "requested_topic_in_competence" in source
    assert "cst_agenda_request" in source
    assert "R. 254-43" in source



def test_cst_meeting_deadlines_normal_and_urgent():
    from datetime import date

    normal = calculate_cst_meeting_deadlines(date(2026, 12, 20))
    urgent = calculate_cst_meeting_deadlines(date(2026, 12, 20), urgent=True)

    assert normal["convocation_target_date"] == "2026-12-05"
    assert normal["documents_target_date"] == "2026-12-12"
    assert urgent["convocation_target_date"] == "2026-12-12"
    assert urgent["documents_target_date"] == "2026-12-12"


def test_fs_nine_month_trigger_requires_elapsed_period_and_half_of_titulars():
    from datetime import date

    not_elapsed = assess_fs_nine_month_trigger(
        last_meeting_date=date(2026, 1, 31),
        as_of_date=date(2026, 10, 30),
        titular_representatives=7,
        requesting_titular_representatives=4,
    )
    eligible = assess_fs_nine_month_trigger(
        last_meeting_date=date(2026, 1, 31),
        as_of_date=date(2026, 10, 31),
        titular_representatives=7,
        requesting_titular_representatives=4,
    )
    insufficient = assess_fs_nine_month_trigger(
        last_meeting_date=date(2026, 1, 31),
        as_of_date=date(2026, 10, 31),
        titular_representatives=7,
        requesting_titular_representatives=3,
    )

    assert not_elapsed["status"] == "NINE_MONTHS_NOT_REACHED"
    assert eligible["status"] == "INSPECTOR_REFERRAL_POSSIBLE"
    assert eligible["nine_month_threshold_date"] == "2026-10-31"
    assert insufficient["status"] == "REQUEST_THRESHOLD_NOT_REACHED"
    assert eligible["legal_conclusion"] is False


def test_fs_inspector_request_deadlines():
    from datetime import date

    result = calculate_fs_inspector_request_deadlines(date(2026, 11, 27))

    assert result["authority_convocation_deadline"] == "2026-12-05"
    assert result["meeting_deadline"] == "2026-12-27"
    assert result["legal_conclusion"] is False



def test_annual_meeting_frequency_distinguishes_cst_fs_and_no_fs():
    cst_with_fs = assess_annual_instance_meeting_frequency(
        instance="CST", meetings_held=2, formation_specialisee_exists=True
    )
    cst_without_fs_missing_extra = assess_annual_instance_meeting_frequency(
        instance="CST", meetings_held=2, formation_specialisee_exists=False,
        health_safety_meetings_held=0,
    )
    cst_without_fs_not_additional = assess_annual_instance_meeting_frequency(
        instance="CST", meetings_held=2, formation_specialisee_exists=False,
        health_safety_meetings_held=1,
    )
    cst_without_fs_complete = assess_annual_instance_meeting_frequency(
        instance="CST", meetings_held=3, formation_specialisee_exists=False,
        health_safety_meetings_held=1,
    )
    fs = assess_annual_instance_meeting_frequency(instance="FS", meetings_held=3)

    assert cst_with_fs["minimum_reached"] is True
    assert cst_without_fs_missing_extra["minimum_reached"] is False
    assert cst_without_fs_not_additional["minimum_reached"] is False
    assert cst_without_fs_not_additional["status"] == "MINIMUM_NOT_YET_REACHED"
    assert cst_without_fs_complete["minimum_reached"] is True
    assert cst_without_fs_complete["minimum_annual_meetings"] == 3
    assert fs["minimum_annual_meetings"] == 3
    assert fs["minimum_reached"] is True


def test_cst_written_request_requires_half_and_sets_two_month_deadline():
    from datetime import date

    required = calculate_cst_written_request_deadline(
        received_date=date(2026, 12, 31),
        titular_representatives=7,
        requesting_titular_representatives=4,
    )
    insufficient = calculate_cst_written_request_deadline(
        received_date=date(2026, 12, 31),
        titular_representatives=7,
        requesting_titular_representatives=3,
    )

    assert required["deadline_date"] == "2027-02-28"
    assert required["status"] == "MEETING_WITHIN_TWO_MONTHS_REQUIRED"
    assert insufficient["deadline_date"] is None
    assert insufficient["status"] == "REQUEST_THRESHOLD_NOT_REACHED"



def test_cst_and_fs_calendar_controls_are_wired_to_instance_ui():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    source = frontend.read_text(encoding="utf-8")

    assert "cstMeetingDate" in source
    assert "cstMeetingUrgent" in source
    assert "lastFsMeetingDate" in source
    assert "inspectorRequestReceivedDate" in source
    assert "cstWrittenRequestDate" in source
    assert "cstAnnualMeetingsHeld" in source
    assert "fsAnnualMeetingsHeld" in source
    assert "fsTitularCount" in source
    assert "fsRequestingCount" in source
    assert "fsTitularCountDirect" in source
    assert "fsRequestingCountDirect" in source
    assert "fs_titular_representatives" in source
    assert "fs_requesting_titular_representatives" in source
    assert "fsSecretaryConsulted" in source
    assert "agendaVotePointsIdentified" in source
    assert "fs_agenda_preparation" in source
    assert "agenda_convocation_check" in source
    assert "fsMeetingDate" in source
    assert "fs_nine_month_assessment" in source
    assert "inspecteur du travail" in source
    assert "cst_written_request_deadline" in source
    assert "annual_meeting_frequency" in source



def test_fs_topics_are_candidates_and_not_legal_conclusions():
    duerp = qualify_fs_topic("Mise à jour du DUERP")
    prevention = qualify_fs_topic("Programme annuel de prévention des risques professionnels (PAPRIPACT)")

    assert any(item["reference"] == "R. 253-24, 6°" for item in duerp["candidates"])
    assert any(item["reference"] == "R. 253-27" for item in prevention["candidates"])
    assert duerp["legal_conclusion"] is False
    assert prevention["legal_conclusion"] is False


def test_cst_fs_routing_without_fs_and_r25380_subsidiarity():
    without_fs = assess_cst_fs_competence_routing(formation_specialisee_exists=False)
    cst_only = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=True,
        topic_in_fs_mandatory_consultation=True,
    )

    assert without_fs["status"] == "CST_EXERCISES_FS_COMPETENCES"
    assert cst_only["status"] == "CST_SOLELY_CONSULTED"
    assert cst_only["legal_conclusion"] is False


def test_cst_r25381_substitution_requires_unexamined_fs_topic_and_half_support():
    threshold_not_met = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=False,
        topic_in_fs_mandatory_consultation=True,
        fs_consultation_already_examined=False,
        cst_evocation_initiative="PRESIDENT",
        cst_staff_representatives_total=7,
        cst_staff_representatives_supporting=3,
    )
    substituted = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=False,
        topic_in_fs_mandatory_consultation=True,
        fs_consultation_already_examined=False,
        cst_evocation_initiative="STAFF_REPRESENTATIVES",
        cst_staff_representatives_total=7,
        cst_staff_representatives_supporting=4,
    )
    already_examined = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=False,
        topic_in_fs_mandatory_consultation=True,
        fs_consultation_already_examined=True,
    )

    assert threshold_not_met["status"] == "EVOCATION_THRESHOLD_NOT_REACHED"
    assert substituted["status"] == "CST_OPINION_SUBSTITUTES_FS"
    assert already_examined["status"] == "FS_ALREADY_EXAMINED"



def test_fs_prepare_exposes_specific_consultation_candidates():
    from app.instances import prepare_instance

    result = prepare_instance("FS", "Projet de mise à jour du DUERP")

    assert result["fs_qualification"]["legal_conclusion"] is False
    assert any(
        item["reference"] == "R. 253-24, 6°"
        for item in result["fs_qualification"]["candidates"]
    )


def test_cst_fs_routing_controls_are_wired_to_frontend():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    source = frontend.read_text(encoding="utf-8")

    assert "cstFsRoutingField" in source
    assert "topicInCstCompetence" in source
    assert "topicInFsMandatory" in source
    assert "fsConsultationExamined" in source
    assert "cstEvocationInitiative" in source
    assert "cst_staff_representatives_supporting" in source
    assert "cst_fs_competence_routing" in source
    assert "fsQualificationHtml" in source



def test_cst_prepare_also_exposes_health_safety_candidates_for_articulation():
    result = prepare_instance(
        "CST",
        "Projet de mise à jour du DUERP",
        formation_specialisee_exists=False,
    )

    assert result["fs_qualification"]["legal_conclusion"] is False
    assert any(
        item["reference"] == "R. 253-24, 6°"
        for item in result["fs_qualification"]["candidates"]
    )



def test_cst_president_evocation_requires_half_agreement_and_valid_counts():
    president_allowed = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=False,
        topic_in_fs_mandatory_consultation=True,
        fs_consultation_already_examined=False,
        cst_evocation_initiative="PRESIDENT",
        cst_staff_representatives_total=8,
        cst_staff_representatives_supporting=4,
    )
    president_blocked = assess_cst_fs_competence_routing(
        formation_specialisee_exists=True,
        topic_in_cst_own_competence=False,
        topic_in_fs_mandatory_consultation=True,
        fs_consultation_already_examined=False,
        cst_evocation_initiative="PRESIDENT",
        cst_staff_representatives_total=8,
        cst_staff_representatives_supporting=3,
    )

    assert president_allowed["status"] == "CST_OPINION_SUBSTITUTES_FS"
    assert president_blocked["status"] == "EVOCATION_THRESHOLD_NOT_REACHED"
    assert "official_references" in president_allowed



def test_fs_major_work_and_new_technology_topics_are_detected_as_candidates():
    major_change = qualify_fs_topic("Projet important de modification du temps de travail")
    new_technology = qualify_fs_topic("Projet important d'introduction de nouvelles technologies")

    assert any(item["reference"] == "R. 253-25, 1°" for item in major_change["candidates"])
    assert any(item["reference"] == "R. 253-25, 2°" for item in new_technology["candidates"])
    assert major_change["legal_conclusion"] is False
    assert new_technology["legal_conclusion"] is False
