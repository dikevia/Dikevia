import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "database" / "migrations" / "020_ai_usage_outcome_contract.sql"


def _outcomes_emitted_by_application():
    emitted = set()
    for relative_path in ("app/main.py", "app/orchestrator.py"):
        source = (ROOT / "backend" / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "outcome":
                        emitted.update(
                            child.value for child in ast.walk(value)
                            if isinstance(child, ast.Constant)
                            and isinstance(child.value, str)
                            and re.fullmatch(r"[A-Z][A-Z0-9_]*", child.value)
                        )
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                is_outcome_assignment = any(
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value == "outcome"
                    for target in targets
                )
                if is_outcome_assignment:
                    value = node.value
                    emitted.update(
                        child.value for child in ast.walk(value)
                        if isinstance(child, ast.Constant)
                        and isinstance(child.value, str)
                        and re.fullmatch(r"[A-Z][A-Z0-9_]*", child.value)
                    )
    return emitted


def test_database_outcome_constraint_accepts_every_application_state():
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"CHECK\\s*\\(\\s*outcome\\s+IN\\s*\\((.*?)\\)\\s*\\)", sql, re.I | re.S)
    assert match, "Migration must define an explicit allow-list for outcome."
    allowed = set(re.findall(r"'([A-Z][A-Z0-9_]*)'", match.group(1)))
    emitted = _outcomes_emitted_by_application()

    assert emitted, "No application outcome states were discovered."
    assert emitted <= allowed, f"Database rejects application outcomes: {sorted(emitted - allowed)}"
    assert "ALTER COLUMN outcome TYPE varchar(80)" in sql
