import json
from pathlib import Path


def test_fpt_chatbot_evaluation_dataset_has_100_unique_cases_and_explicit_review_status():
    repository_root = Path(__file__).resolve().parents[2]
    dataset_path = repository_root / "docs" / "quality" / "fpt_chatbot_eval_v1.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    cases = dataset["cases"]
    assert dataset["case_count"] == 100
    assert len(cases) == 100
    assert len({case["id"] for case in cases}) == 100
    assert len({case["question"] for case in cases}) == 100
    assert len({case["category"] for case in cases}) == 10

    for case in cases:
        assert case["question"].strip()
        assert case["expected_intent"].strip()
        assert case["required_checks"]
        assert case["failure_modes"]
        assert case["gold_answer_status"].startswith("À rédiger et valider")

    assert "pas des réponses juridiques certifiées" in dataset["important_limit"]
    assert dataset["release_gate"]["no_critical_failures"] is True


def test_fifteen_question_pilot_manifest_is_reproducible_and_covers_all_ten_families():
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = repository_root / "docs" / "quality" / "fpt_pilot_15_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    cases = manifest["cases"]
    ids = manifest["case_ids"]
    assert len(cases) == 15
    assert len(ids) == 15
    assert len(set(ids)) == 15
    assert [case["id"] for case in cases] == ids
    assert len({case["category"] for case in cases}) == 10
    assert manifest["execution_protocol"]["authenticated_session_count"] == 1
    assert manifest["execution_protocol"]["questions_count"] == 15
    assert manifest["release_gate"]["status"] == "NOT_EVALUATED"
    assert manifest["release_gate"]["gold_answers"] == "HUMAN_VALIDATION_REQUIRED"
    for case in cases:
        assert case["question"].strip()
        assert case["required_checks"]
        assert case["failure_modes"]
        assert case["gold_answer_status"].startswith("À rédiger et valider")
