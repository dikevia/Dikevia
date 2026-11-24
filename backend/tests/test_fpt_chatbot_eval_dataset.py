import json
import subprocess
import sys
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
    source_path = repository_root / "docs" / "quality" / "fpt_chatbot_eval_v1.json"
    source_cases = {
        case["id"]: case
        for case in json.loads(source_path.read_text(encoding="utf-8"))["cases"]
    }
    for case in cases:
        assert case["question"].strip()
        assert case["required_checks"]
        assert case["failure_modes"]
        assert case["gold_answer_status"].startswith("À rédiger et valider")
        source_case = source_cases[case["id"]]
        assert case["question"] == source_case["question"]
        assert case["expected_intent"] == source_case["expected_intent"]
        assert case["source_review_status"] == source_case["source_review_status"]



def test_fifteen_question_pilot_runs_through_prepare_review_and_score(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    script = repository_root / "scripts" / "fpt_benchmark.py"
    dataset = repository_root / "docs" / "quality" / "fpt_pilot_15_v1.json"
    manifest = json.loads(dataset.read_text(encoding="utf-8"))
    ids = manifest["case_ids"]

    validated = subprocess.run(
        [sys.executable, str(script), "validate", "--dataset", str(dataset)],
        capture_output=True, text=True, check=False,
    )
    assert validated.returncode == 0, validated.stderr
    assert "15 questions" in validated.stdout

    responses_path = tmp_path / "responses.json"
    responses_path.write_text(json.dumps({
        "responses": [
            {"id": case_id, "answer": "Réponse de test", "sources": [], "verification_status": "PARTIAL"}
            for case_id in ids
        ]
    }), encoding="utf-8")
    review_path = tmp_path / "review.json"
    prepared = subprocess.run(
        [sys.executable, str(script), "prepare-review", "--dataset", str(dataset),
         "--responses", str(responses_path), "--out", str(review_path)],
        capture_output=True, text=True, check=False,
    )
    assert prepared.returncode == 0, prepared.stderr
    reviews = json.loads(review_path.read_text(encoding="utf-8"))
    assert len(reviews) == 15
    assert [item["id"] for item in reviews] == ids

    for item in reviews:
        item["evaluations"] = {
            "question_understanding": 2,
            "research_coverage": 2,
            "source_relevance": 2,
            "legal_accuracy": 2,
            "synthesis_fidelity": 2,
        }
        item["question_relevance"] = True
        item["source_support"] = True
        item["severite"] = "conforme"
    annotated_path = tmp_path / "annotated.json"
    annotated_path.write_text(json.dumps(reviews), encoding="utf-8")
    report_path = tmp_path / "score.json"
    scored = subprocess.run(
        [sys.executable, str(script), "score", "--dataset", str(dataset),
         "--responses", str(responses_path), "--reviews", str(annotated_path),
         "--out", str(report_path)],
        capture_output=True, text=True, check=False,
    )
    assert scored.returncode == 0, scored.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["questions_total"] == 15
    assert report["questions_evaluees"] == 15
    assert report["status"] == "COMPLET"
    assert report["release_gate"]["status"] == "INCOMPLETE"
    assert report["release_gate"]["checks"]["gold_answers_human_validated"] is False
