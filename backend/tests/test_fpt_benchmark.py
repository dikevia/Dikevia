from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("fpt_benchmark", ROOT / "scripts" / "fpt_benchmark.py")
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def _dataset():
    categories = [
        {"id": f"cat-{i}", "name": f"Category {i}", "count": 20}
        for i in range(1, 6)
    ]
    questions = []
    for i in range(1, 101):
        category = (i - 1) // 20 + 1
        questions.append({
            "id": f"FPT-{i:03d}",
            "category_id": f"cat-{category}",
            "category": f"Category {category}",
            "action_type": "standard_rag_qa",
            "estimated_credits": 1,
            "question": f"Question {i}",
            "expected_criteria": ["legal basis", "conditions"],
        })
    return {
        "benchmark_name": "FPT_Juridique_100_Questions",
        "domain": "Fonction Publique Territoriale (FPT)",
        "total_questions": 100,
        "categories": categories,
        "questions": questions,
    }


def test_validate_dataset_accepts_canonical_100_question_ids(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(_dataset()), encoding="utf-8")
    questions = benchmark.validate_dataset(str(path))
    assert len(questions) == 100
    assert questions[0]["id"] == "FPT-001"
    assert questions[-1]["id"] == "FPT-100"


def test_validate_dataset_rejects_duplicate_and_missing_ids(tmp_path):
    data = _dataset()
    data["questions"][-1]["id"] = "FPT-001"
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        benchmark.validate_dataset(str(path))
    except ValueError as exc:
        assert "duplicates" in str(exc)
        assert "missing_ids" in str(exc)
    else:
        raise AssertionError("Invalid dataset unexpectedly accepted")


def test_prepare_review_and_score_require_all_100_real_answers_and_reviews(tmp_path):
    dataset_path = tmp_path / "questions.json"
    responses_path = tmp_path / "responses.json"
    review_path = tmp_path / "review.json"
    results_path = tmp_path / "results.json"
    dataset_path.write_text(json.dumps(_dataset()), encoding="utf-8")
    responses = [
        {"id": f"FPT-{i:03d}", "answer": f"Answer {i}", "sources": [], "verification_status": "verified"}
        for i in range(1, 101)
    ]
    responses_path.write_text(json.dumps({"responses": responses}), encoding="utf-8")
    benchmark.prepare_review(str(dataset_path), str(responses_path), str(review_path))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert len(review) == 100
    assert review[0]["evaluations"]["exactitude_juridique"] is None

    for item in review:
        item["evaluations"] = {dimension: 2 for dimension in benchmark.DIMENSIONS}
        item["severite"] = "conforme"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    result = benchmark.score(
        str(dataset_path), str(responses_path), str(review_path), str(results_path)
    )
    assert result["status"] == "COMPLET"
    assert result["questions_evaluees"] == 100
    assert result["score_global_percent"] == 100.0
    assert sum(item["reviewed"] for item in result["par_domaine"].values()) == 100


def test_validate_repository_quality_benchmark_schema():
    dataset_path = ROOT / "docs" / "quality" / "fpt_chatbot_eval_v1.json"
    questions = benchmark.validate_dataset(str(dataset_path))
    assert len(questions) == 100
    assert questions[0]["id"] == "FPT-001"
    assert questions[0]["expected_failure_modes"]
    assert "Intention attendue" in questions[0]["expected_criteria"][0]
