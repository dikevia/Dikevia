from datetime import date

from app.cst_qualification import calculate_cst_meeting_deadlines, qualify_cst_topic
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
