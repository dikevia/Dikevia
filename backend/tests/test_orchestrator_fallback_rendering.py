import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "backend" / "app" / "orchestrator.py"


def test_unverified_fallback_uses_real_line_breaks():
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    string_values = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert any("\nSources retrouvées" in value for value in string_values)
    assert any("\nAucune conclusion juridique" in value for value in string_values)
    assert not any("\\nSources retrouvées" in value for value in string_values)
    assert not any("\\nAucune conclusion juridique" in value for value in string_values)



def test_follow_up_context_is_used_for_generation_and_entailment():
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))
    checked_calls = {"analyze_question", "verify_claim_entailment"}
    found = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = function.id if isinstance(function, ast.Name) else None
        if name not in checked_calls:
            continue
        question_arg = next(
            (keyword.value for keyword in node.keywords if keyword.arg == "question"),
            None,
        )
        assert isinstance(question_arg, ast.Name)
        assert question_arg.id == "contextual_question"
        found.add(name)

    assert found == checked_calls


def test_orchestrator_citation_guard_fails_closed_on_malformed_sources():
    from app.orchestrator import _citation_is_valid

    assert _citation_is_valid(None) is False
    assert _citation_is_valid("not-a-source") is False
    assert _citation_is_valid({"citation_integrity": "valid"}) is False
    assert _citation_is_valid({"citation_integrity": {"valid": True}}) is True
