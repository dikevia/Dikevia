from datetime import date

from app.cst_qualification import (
    CST_TOPIC_RULES,
    assess_cst_agenda_request,
    assess_fs_nine_month_trigger,
    calculate_fs_inspector_request_deadlines,
    calculate_cst_meeting_deadlines,
    calculate_cst_meeting_deadlines,
    qualify_cst_topic,
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
