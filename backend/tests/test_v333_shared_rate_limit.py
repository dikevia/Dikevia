from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_local_compliance_review_shares_chat_rate_limit_before_document_or_corpus_reads():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    route = main.split('@app.post("/api/v1/legal/compliance/review/{document_id}")', 1)[1]
    route = route.split('@app.get("/api/v1/platform/legal-corpus/freshness")', 1)[0]
    limiter = route.index("consume_chat_request(")
    document_read = route.index("local = await ctx.conn.fetchrow")
    national_search = route.index("search_legal_corpus(ctx.conn, query")
    assert limiter < document_read < national_search
    assert "settings.chat_rate_limit_per_minute" in route
    assert "status_code=429" in route
    assert '"Retry-After"' in route


def test_chat_and_local_compliance_use_the_same_rate_limit_bucket():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    chat = main.split('@app.post("/api/v1/chat/ask"', 1)[1]
    compliance = main.split('@app.post("/api/v1/legal/compliance/review/{document_id}")', 1)[1]
    assert "consume_chat_request(" in chat
    assert "consume_chat_request(" in compliance
