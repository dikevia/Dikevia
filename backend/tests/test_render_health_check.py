from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_render_readiness_probe_does_not_wait_for_postgresql():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    readiness = source.split('@app.get("/ready")', 1)[1].split(
        '@app.get("/", response_class=HTMLResponse)', 1
    )[0]

    assert "pool = get_pool()" in readiness
    assert "pool.is_closing()" in readiness
    assert 'fetchval("SELECT 1")' not in readiness
    assert "async with pool.acquire()" not in readiness
