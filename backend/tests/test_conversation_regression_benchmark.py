from __future__ import annotations

import json
from pathlib import Path

from app.legal_qualification import build_contextual_research_question


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "docs" / "quality" / "conversation_regression_v1.json"


def test_conversation_regression_fixture_has_twenty_unique_cases():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = data["cases"]
    ids = [case["id"] for case in cases]
    assert len(cases) == 20
    assert len(ids) == len(set(ids))


def test_conversation_regression_cases_preserve_or_reset_context_as_expected():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    failures = []
    for case in data["cases"]:
        actual = build_contextual_research_question(
            case["question"],
            case.get("prior_user_questions", []),
            case.get("prior_assistant_messages", []),
        )
        if case["inherit"]:
            fragment = case["topic_fragment"]
            if fragment.lower() not in actual.lower():
                failures.append(f'{case["id"]}: contexte attendu "{fragment}", obtenu "{actual}"')
        elif actual != case["question"]:
            failures.append(f'{case["id"]}: nouvelle question polluée par le contexte : "{actual}"')
    assert not failures, "\\n".join(failures)
