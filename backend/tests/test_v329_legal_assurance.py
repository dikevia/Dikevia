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


def _verified_evidence_source(**overrides):
    source = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000000000123",
        "article": "L123-4",
        "title": "Code général de la fonction publique — article L123-4",
        "text": (
            "L'autorité territoriale organise le service et veille à la protection "
            "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
        ),
        "excerpt": (
            "L'autorité territoriale organise le service et veille à la protection "
            "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
        ),
        "content_kind": "FULL_TEXT",
        "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
        "analysis_eligible": True,
        "official_source": True,
        "citation_integrity": {"valid": True},
    }
    source.update(overrides)
    return source


def _evidence_claim(text, quote, source_id="LEGIARTI000000000123"):
    return {"claims": [{"text": text, "source_id": source_id, "quote": quote}]}


def test_claim_evidence_accepts_exact_quote_from_unique_verified_official_source():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    quote = source["excerpt"]
    result = validate_claim_evidence(
        _evidence_claim("L'autorité territoriale veille à la santé et à la sécurité des agents.", quote),
        [source],
    )
    assert result["valid"] is True
    assert result["claim_count"] == 1


def test_claim_evidence_rejects_source_without_valid_citation_integrity():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(citation_integrity={"valid": False})
    result = validate_claim_evidence(
        _evidence_claim("L'autorité territoriale veille à la santé des agents.", source["excerpt"]),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_rejects_metadata_only_even_if_identifier_is_valid():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(content_kind="METADATA")
    result = validate_claim_evidence(
        _evidence_claim("L'autorité territoriale veille à la santé des agents.", source["excerpt"]),
        [source],
    )
    assert result["valid"] is False


def test_claim_evidence_rejects_explicitly_out_of_scope_sources():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(analysis_eligible=False, public_service_scope="FPH")
    result = validate_claim_evidence(
        _evidence_claim("L'autorité territoriale veille à la santé des agents.", source["excerpt"]),
        [source],
    )
    assert result["valid"] is False


def test_claim_evidence_rejects_unsupported_numeric_or_date_details():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale doit répondre sous 15 jours.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:unsupported_numeric_or_date_detail" in result["invalid_claims"]


def test_claim_evidence_rejects_a_quote_that_is_not_present_verbatim():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé des agents.",
            "L'autorité territoriale doit obligatoirement recruter de nouveaux agents.",
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:quote_not_exactly_found_in_source" in result["invalid_claims"]


def test_claim_evidence_rejects_duplicate_source_identifiers_as_ambiguous():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    duplicate = dict(source, title="Autre source")
    result = validate_claim_evidence(
        _evidence_claim("L'autorité territoriale veille à la santé des agents.", source["excerpt"]),
        [source, duplicate],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]



def test_claim_evidence_rejects_post_facts_judgment_as_standalone_support_for_conclusion():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(
        source_type="LEGIFRANCE_CETAT_FULL_TEXT",
        document_kind="ADMIN_CASELAW",
        temporal_status="DECISION_POSTERIOR_TO_FACTS",
    )
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]

def test_claim_evidence_rejects_generic_public_service_scope_without_fpt_proof():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(public_service_scope="GENERAL_PUBLIC_SERVICE")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_accepts_explicitly_common_three_branch_source():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(public_service_scope="COMMON_PUBLIC_SERVICE")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is True

def test_claim_evidence_rejects_interpretive_context_only_sources():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(reference_role="INTERPRETIVE_CONTEXT_ONLY")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]




def test_claim_evidence_rejects_a_compound_answer_that_silently_omits_an_axis():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    axis_overtime = "heures supplémentaires et IHTS"
    axis_sick_leave = "congé maladie"
    payload = _evidence_claim(
        "L'autorité territoriale veille à la santé et à la sécurité des agents.",
        source["excerpt"],
    )
    payload["claims"][0]["axis"] = axis_overtime
    result = validate_claim_evidence(
        payload, [source], required_axes=[axis_overtime, axis_sick_leave],
    )
    assert result["valid"] is False
    assert f"research_axis_not_covered:{axis_sick_leave}" in result["invalid_claims"]


def test_claim_evidence_accepts_explicit_uncovered_axis_without_inventing_a_claim():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    axis_overtime = "heures supplémentaires et IHTS"
    axis_sick_leave = "congé maladie"
    payload = _evidence_claim(
        "L'autorité territoriale veille à la santé et à la sécurité des agents.",
        source["excerpt"],
    )
    payload["claims"][0]["axis"] = axis_overtime
    payload["uncovered_axes"] = [axis_sick_leave]
    result = validate_claim_evidence(
        payload, [source], required_axes=[axis_overtime, axis_sick_leave],
    )
    assert result["valid"] is True
    assert result["uncovered_axes"] == [axis_sick_leave]


def test_claim_evidence_rejects_unknown_axis_labels():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    payload = _evidence_claim(
        "L'autorité territoriale veille à la santé et à la sécurité des agents.",
        source["excerpt"],
    )
    payload["claims"][0]["axis"] = "un sujet inventé"
    result = validate_claim_evidence(
        payload, [source], required_axes=["heures supplémentaires"],
    )
    assert result["valid"] is False
    assert "claim_0:missing_or_unknown_research_axis" in result["invalid_claims"]
