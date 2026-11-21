from app.legal_assurance import classify_legal_source, assess_source_set


def test_local_rule_is_never_treated_as_national_norm():
    result = classify_legal_source({"source_type": "LOCAL_COLLECTIVITY_DOCUMENT", "local_document_type": "REGLEMENT_TEMPS_TRAVAIL", "validation_status": "COLLECTED_UNVERIFIED"})
    assert result["source_family"] == "LOCAL_REGULATION"
    assert result["usable_for_conclusion"] is False
    assert result["review_priority"] < 65


def test_local_and_national_sources_require_comparison_not_automatic_conflict():
    result = assess_source_set([
        {"document_kind": "DECREE", "temporal_status": "IN_FORCE_ON_REQUESTED_DATE"},
        {"source_type": "LOCAL_COLLECTIVITY_DOCUMENT", "local_document_type": "DELIBERATION", "validation_status": "VERIFIED_APPLICABLE"},
    ])
    assert result["comparison_required"] is True
    assert result["status"] == "A_COMPARER"
    assert "ne prouve pas une contradiction" in result["warnings"][0]


def test_unknown_dates_are_not_usable_for_conclusions():
    result = classify_legal_source({"document_kind": "DECREE", "temporal_status": "TEMPORAL_SCOPE_INCOMPLETE"})
    assert result["usable_for_conclusion"] is False


def test_review_route_is_tenant_scoped_and_never_returns_legal_verdict():
    from pathlib import Path
    main = (Path(__file__).resolve().parents[1] / "app/main.py").read_text(encoding="utf-8")
    assert '@app.post("/api/v1/legal/compliance/review/{document_id}")' in main
    assert 'd.organization_id=$2::uuid' in main
    assert 'local["scan_status"] != "CLEAN"' in main
    assert "Aucune déclaration automatique" in main
    assert '@app.get("/api/v1/platform/legal-corpus/freshness")' in main


def test_compliance_review_consumes_ai_result_and_records_all_provider_outcomes():
    from pathlib import Path
    main = (Path(__file__).resolve().parents[1] / "app/main.py").read_text(encoding="utf-8")
    assert "candidate = extract_analysis_content(candidate_result)" in main
    assert "record_ai_usage_event(ctx.conn, ctx.organization_id, ctx.user_id, request_id, usage)" in main
    assert '"outcome": "PROVIDER_ERROR"' in main
    assert 'usage["outcome"] = "REJECTED_UNGROUNDED"' in main



def test_decision_after_facts_is_interpretive_context_not_proof_of_historical_rule():
    result = classify_legal_source({
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "temporal_status": "DECISION_POSTERIOR_TO_FACTS",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
    })
    assert result["source_family"] == "ADMIN_CASELAW"
    assert result["usable_for_conclusion"] is False
    assert result["usable_for_facts_date_conclusion"] is False
    assert result["usable_for_interpretation"] is True
    assert "pas comme preuve autonome" in result["temporal_limit"]


def test_case_law_available_by_facts_date_can_still_be_considered_for_conclusion():
    result = classify_legal_source({
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "temporal_status": "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
        "content_kind": "FULL_TEXT",
    })
    assert result["usable_for_conclusion"] is True
    assert result["usable_for_facts_date_conclusion"] is True
    assert result["usable_for_interpretation"] is True
