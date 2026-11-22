from pathlib import Path

ROOT = Path(__file__).parents[2]


def _route(source: str, marker: str, next_marker: str) -> str:
    return source.split(marker, 1)[1].split(next_marker, 1)[0]


def test_privileged_piste_ingestion_validates_query_and_bounds_work_before_database_or_network():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    cases = [
        (
            '@app.post("/api/v1/platform/legal-corpus/ingest/regulatory")',
            '@app.post("/api/v1/platform/legal-corpus/ingest/administrative-case-law")',
            "La recherche réglementaire doit contenir entre 2 et 500 caractères.",
            "La limite d'import réglementaire doit être comprise entre 1 et 20.",
            "pool = get_corpus_ingest_pool()",
        ),
        (
            '@app.post("/api/v1/platform/legal-corpus/ingest/administrative-case-law")',
            '@app.post("/api/v1/platform/legal-corpus/ingest/circulaires-xml")',
            "La recherche de jurisprudence doit contenir entre 2 et 500 caractères.",
            "La limite d'import de jurisprudence doit être comprise entre 1 et 20.",
            "pool = get_corpus_ingest_pool()",
        ),
    ]
    for marker, next_marker, query_error, limit_error, first_side_effect in cases:
        route = _route(source, marker, next_marker)
        assert "if not isinstance(q, str) or len(q.strip()) < 2 or len(q) > 500:" in route
        assert "if not 1 <= limit <= 20:" in route
        assert query_error in route
        assert limit_error in route
        assert route.index(query_error) < route.index(first_side_effect)
        assert route.index(limit_error) < route.index(first_side_effect)
