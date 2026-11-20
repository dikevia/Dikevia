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
