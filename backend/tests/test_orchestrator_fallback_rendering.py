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

    assert any("\\nSources retrouvées" in value for value in string_values)
    assert any("\\nAucune conclusion juridique" in value for value in string_values)
    assert not any("\\\\nSources retrouvées" in value for value in string_values)
    assert not any("\\\\nAucune conclusion juridique" in value for value in string_values)
