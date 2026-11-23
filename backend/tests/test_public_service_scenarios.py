import json
from pathlib import Path

from app.legal_qualification import qualify_legal_question


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "public_service_scenarios.json"


def _scenarios():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_public_service_scenario_catalogue_covers_all_three_versants():
    scenarios = _scenarios()
    assert {item["versant"] for item in scenarios} == {"FPT", "FPE", "FPH"}
    assert all(item["official_sources"] for item in scenarios)
    assert all(
        item["review_status"] == "SOURCE_LOCATED_NOT_LEGAL_APPROVED"
        for item in scenarios
    )


def test_annual_leave_scenarios_route_to_the_selected_versant_without_transposition():
    for scenario in _scenarios():
        result = qualify_legal_question(
            scenario["question"],
            employer="NATIONAL",
            public_service=scenario["versant"],
        )
        assert result["public_service"] == scenario["versant"], scenario["id"]
        assert result["scope_status"] == scenario["expected_scope"], scenario["id"]
        assert result["topic"] == scenario["expected_topic"], scenario["id"]
        assert result["employer_document_scope"] == "NATIONAL_CORPUS_ONLY", scenario["id"]
        assert (
            f'{scenario["versant"]}_IMPLEMENTING_LAWS_DECREES_AND_ORDERS'
            in result["research_priorities"]
        ), scenario["id"]
