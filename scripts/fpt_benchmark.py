#!/usr/bin/env python3
"""Offline evaluator for the Dikévia 100-question FPT legal benchmark.

This tool never calls Dikévia, an AI provider, Légifrance/PISTE, Render, or Neon.
It validates supplied JSON, prepares a human-review sheet, and aggregates reviews.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_IDS = [f"Q{i:03d}" for i in range(1, 101)]
REQUIRED_QUESTION_FIELDS = {
    "id", "category_id", "category", "action_type", "estimated_credits", "question", "expected_criteria"
}
DIMENSIONS = (
    "exactitude_juridique",
    "actualite_juridique",
    "perimetre_fpt",
    "exhaustivite",
    "sources_et_citations",
    "prudence_et_abstention",
    "precision_factuelle",
)
SEVERITY = {"conforme", "mineur", "majeur", "critique"}


def load_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Impossible de lire {path}: {exc}") from exc


def questions_from(data: Any) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("questions")
    if not isinstance(data, list):
        raise ValueError("Le jeu doit être un objet JSON contenant benchmark_name, total_questions, categories et questions.")
    if any(not isinstance(item, dict) for item in data):
        raise ValueError("Chaque question doit être un objet JSON.")
    return data


def validate_dataset(path: str) -> list[dict]:
    data = load_json(path)\n    if not isinstance(data, dict) or data.get("benchmark_name") != "FPT_Juridique_100_Questions" or data.get("total_questions") != 100:\n        raise ValueError("Métadonnées invalides : benchmark_name ou total_questions.")\n    questions = questions_from(data)
    ids = [q.get("id") for q in questions]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    missing = [x for x in EXPECTED_IDS if x not in ids]
    unexpected = [x for x in ids if x not in EXPECTED_IDS]
    malformed = [
        {"id": q.get("id"), "missing_fields": sorted(REQUIRED_QUESTION_FIELDS - q.keys())}
        for q in questions if REQUIRED_QUESTION_FIELDS - q.keys()
    ]
    categories = data.get("categories", [])\n    category_counts = {cat.get("id"): 0 for cat in categories if isinstance(cat, dict)}\n    for q in questions:\n        if q.get("category_id") in category_counts:\n            category_counts[q["category_id"]] += 1\n    bad_categories = {cat.get("id"): {"declared": cat.get("count"), "actual": category_counts.get(cat.get("id"), 0)} for cat in categories if not isinstance(cat, dict) or category_counts.get(cat.get("id"), 0) != cat.get("count")}\n    if duplicates or missing or unexpected or malformed or len(questions) != 100 or len(categories) != 5 or bad_categories:
        raise ValueError(json.dumps({
            "question_count": len(questions), "duplicates": duplicates,
            "missing_ids": missing, "unexpected_ids": unexpected,
            "malformed_questions": malformed, "category_counts": bad_categories,
        }, ensure_ascii=False, indent=2))
    return questions


def prepare_review(dataset_path: str, responses_path: str, output_path: str) -> None:
    questions = validate_dataset(dataset_path)
    responses = load_json(responses_path)
    if isinstance(responses, dict):
        responses = responses.get("responses")
    if not isinstance(responses, list):
        raise ValueError("Les réponses doivent être une liste JSON ou un objet {responses:[...]}.")
    by_id = {r.get("id"): r for r in responses if isinstance(r, dict)}
    if len(by_id) != len(responses):
        raise ValueError("Identifiants de réponses dupliqués ou réponse mal formée.")
    expected = set(EXPECTED_IDS)
    if set(by_id) != expected:
        raise ValueError(json.dumps({
            "missing_response_ids": sorted(expected - set(by_id)),
            "unexpected_response_ids": sorted(set(by_id) - expected),
        }, ensure_ascii=False, indent=2))
    review = []
    for q in questions:
        r = by_id[q["id"]]
        review.append({
            "id": q["id"],
            "category_id": q["category_id"],\n            "category": q["category"],\n            "action_type": q["action_type"],\n            "estimated_credits": q["estimated_credits"],
            "question": q["question"],
            "criteres_attendus": q["expected_criteria"],
            "reponse_dikevia": r.get("answer", ""),
            "sources_dikevia": r.get("sources", []),
            "statut_verification": r.get("verification_status"),
            "evaluations": {dimension: None for dimension in DIMENSIONS},
            "severite": None,
            "constats": [],
            "correction_attendue": "",
            "sources_officielles_de_controle": [],
            "date_controle": None,
        })
    Path(output_path).write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def score(dataset_path: str, responses_path: str, reviews_path: str, output_path: str) -> dict:
    questions = validate_dataset(dataset_path)
    # Ensure responses are complete even if the review sheet was edited manually.
    responses = load_json(responses_path)
    if isinstance(responses, dict):
        responses = responses.get("responses")
    response_ids = {r.get("id") for r in responses if isinstance(r, dict)}
    if response_ids != set(EXPECTED_IDS) or len(responses) != 100:
        raise ValueError("Le fichier de réponses doit contenir exactement une réponse pour chacun des Q001–Q100.")
    reviews = load_json(reviews_path)
    if not isinstance(reviews, list):
        raise ValueError("Le fichier de revue doit être une liste JSON.")
    review_by_id = {r.get("id"): r for r in reviews if isinstance(r, dict)}
    if len(review_by_id) != 100 or set(review_by_id) != set(EXPECTED_IDS):
        raise ValueError("Le fichier de revue doit contenir exactement une évaluation par question Q001–Q100.")

    totals = {d: 0 for d in DIMENSIONS}
    dimension_counts = {d: 0 for d in DIMENSIONS}
    severity_counts = {s: 0 for s in SEVERITY}
    question_scores = []
    unreviewed = []
    domain_stats: dict[str, dict[str, int]] = {}
    for q in questions:
        review = review_by_id[q["id"]]
        ratings = review.get("evaluations") or {}
        valid = True
        points = 0
        for dim in DIMENSIONS:
            value = ratings.get(dim)
            if value not in (0, 1, 2):
                valid = False
                continue
            totals[dim] += value
            dimension_counts[dim] += 1
            points += value
        severity = review.get("severite")
        if severity not in SEVERITY:
            valid = False
        else:
            severity_counts[severity] += 1
        if not valid:
            unreviewed.append(q["id"])
            continue
        question_scores.append({"id": q["id"], "score": points, "max": 14, "severity": severity})
        domain = str(q.get("category") or "Non classé")
        stat = domain_stats.setdefault(domain, {"reviewed": 0, "points": 0, "max": 0, "critical": 0, "major": 0})
        stat["reviewed"] += 1
        stat["points"] += points
        stat["max"] += 14
        stat["critical"] += severity == "critique"
        stat["major"] += severity == "majeur"

    reviewed = len(question_scores)
    result = {
        "benchmark": "Dikévia — 100 questions FPT",
        "status": "COMPLET" if reviewed == 100 else "INCOMPLET",
        "questions_total": 100,
        "questions_evaluees": reviewed,
        "questions_restantes": unreviewed,
        "score_global_percent": round(sum(x["score"] for x in question_scores) / (14 * reviewed) * 100, 2) if reviewed else None,
        "score_par_dimension_sur_2": {
            d: round(totals[d] / dimension_counts[d], 3) if dimension_counts[d] else None
            for d in DIMENSIONS
        },
        "repartition_severite": severity_counts,
        "par_domaine": domain_stats,
        "scores_question": question_scores,
        "methodologie": "Notation humaine documentée, 0=incorrect/absent, 1=partiel, 2=conforme. Le score n'est publiable que si les 100 questions sont évaluées.",
    }
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="Valide le JSON Q001–Q100")
    v.add_argument("--dataset", required=True)
    p = sub.add_parser("prepare-review", help="Construit la grille d'évaluation à partir des 100 réponses")
    p.add_argument("--dataset", required=True)
    p.add_argument("--responses", required=True)
    p.add_argument("--out", required=True)
    s = sub.add_parser("score", help="Calcule les scores à partir d'une grille entièrement annotée")
    s.add_argument("--dataset", required=True)
    s.add_argument("--responses", required=True)
    s.add_argument("--reviews", required=True)
    s.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            questions = validate_dataset(args.dataset)
            print(f"OK — {len(questions)} questions, Q001 à Q100, champs obligatoires présents.")
        elif args.command == "prepare-review":
            prepare_review(args.dataset, args.responses, args.out)
            print(f"Grille créée : {args.out}")
        else:
            result = score(args.dataset, args.responses, args.reviews, args.out)
            print(json.dumps({k: result[k] for k in ("status", "questions_evaluees", "score_global_percent", "repartition_severite")}, ensure_ascii=False, indent=2))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
