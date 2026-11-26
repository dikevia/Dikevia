import pytest

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
        "public_service_scope": "FPT",
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


def test_versioned_corpus_claim_requires_matching_full_text_hash_even_if_valid_flag_is_set():
    import hashlib
    from app.legal_assurance import validate_claim_evidence

    full_text = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
    )
    source = _verified_evidence_source(
        source_type="LEGIFRANCE_LODA",
        source_id="CORPUS_VERSION_12345678",
        official_source=True,
        version_id="12345678-1234-4234-8234-123456789012",
        source_version_id="LEGIARTI000000000123",
        version_key="2024-01-01",
        text_sha256=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        full_text=full_text,
        citation_integrity={"valid": True, "text_hash_verified": True},
    )
    accepted = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            "L'autorité territoriale organise le service et veille à la protection de la santé et de la sécurité des agents",
            source_id=source["source_id"],
        ),
        [source],
    )
    assert accepted["valid"] is True

    source["full_text"] = full_text + " Texte altéré."
    rejected = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            "L'autorité territoriale organise le service et veille à la protection de la santé et de la sécurité des agents",
            source_id=source["source_id"],
        ),
        [source],
    )
    assert rejected["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in rejected["invalid_claims"]


def test_versioned_corpus_rejects_selected_excerpt_not_present_in_hashed_full_text():
    import hashlib
    from app.legal_assurance import validate_claim_evidence

    full_text = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
    )
    fabricated_excerpt = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents. "
        "Elle doit accorder automatiquement une prime de 500 euros."
    )
    source = _verified_evidence_source(
        source_type="LEGIFRANCE_LODA",
        source_id="CORPUS_VERSION_87654321",
        version_id="87654321-1234-4234-8234-123456789012",
        text_sha256=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        full_text=full_text,
        excerpt=fabricated_excerpt,
        citation_integrity={"valid": True, "text_hash_verified": True},
    )
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale doit accorder automatiquement une prime de 500 euros.",
            "Elle doit accorder automatiquement une prime de 500 euros.",
            source_id=source["source_id"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_accepts_corpus_version_verified_for_historical_facts_date():
    import hashlib
    from app.legal_assurance import validate_claim_evidence

    full_text = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
    )
    source = _verified_evidence_source(
        source_type="LEGIFRANCE_LODA",
        source_id="CORPUS_VERSION_FACTS_DATE",
        version_id="12345678-1234-4234-8234-123456789012",
        text_sha256=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
        full_text=full_text,
        temporal_status="IN_FORCE_ON_FACTS_DATE",
        excerpt=full_text,
        citation_integrity={"valid": True, "text_hash_verified": True},
    )
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            "L'autorité territoriale organise le service et veille à la protection de la santé et de la sécurité des agents",
            source_id=source["source_id"],
        ),
        [source],
        facts_period={"facts_reference_date": "2024-06-01"},
    )
    assert result["valid"] is True


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


def test_claim_evidence_rejects_national_source_without_explicit_analysis_scope():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    source.pop("analysis_eligible")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé des agents.",
            source["excerpt"],
        ),
        [source],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_evidence_keeps_verified_tenant_document_without_national_scope_flag():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(
        source_type="LOCAL_DOCUMENT",
        source_id="LOCAL-DOC:123_V20240101",
        validation_status="VERIFIED_HISTORICAL",
        temporal_status="VERIFIED_APPLICABLE",
        official_source=False,
    )
    source.pop("analysis_eligible")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé des agents.",
            source["excerpt"],
            source_id=source["source_id"],
        ),
        [source],
    )
    assert result["valid"] is True
    assert result["claim_count"] == 1


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




def test_claim_evidence_allows_a_verified_partial_answer_when_an_axis_is_uncovered():
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
    assert result["valid"] is True
    assert result["partial"] is True
    assert result["claim_count"] == 1
    assert result["uncovered_axes"] == [axis_sick_leave]


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



def test_claim_evidence_keeps_verified_claims_when_other_research_axes_are_uncovered():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    claim_text = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
    )
    result = validate_claim_evidence({
        "claims": [{
            "text": claim_text,
            "source_id": source["source_id"],
            "quote": source["excerpt"],
            "axis": "maintien dans l'emploi",
        }],
        "uncovered_axes": [],
    }, [source], required_axes=["maintien dans l'emploi", "reclassement"])

    assert result["valid"] is True
    assert result["partial"] is True
    assert result["claim_count"] == 1
    assert result["uncovered_axes"] == ["reclassement"]


def test_claim_evidence_discards_only_the_unsupported_claim_when_another_is_valid():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    valid_text = (
        "L'autorité territoriale organise le service et veille à la protection "
        "de la santé et de la sécurité des agents dans les conditions prévues par les textes."
    )
    result = validate_claim_evidence({
        "claims": [
            {
                "text": valid_text,
                "source_id": source["source_id"],
                "quote": source["excerpt"],
                "axis": "santé et sécurité",
            },
            {
                "text": "La collectivité doit verser une indemnité supplémentaire.",
                "source_id": source["source_id"],
                "quote": source["excerpt"],
                "axis": "rémunération",
            },
        ],
        "uncovered_axes": [],
    }, [source], required_axes=["santé et sécurité", "rémunération"])

    assert result["valid"] is True
    assert result["claim_count"] == 1
    assert result["claims"][0]["axis"] == "santé et sécurité"
    assert result["uncovered_axes"] == ["rémunération"]
    assert "claim_1:quote_not_relevantly_aligned" in result["invalid_claims"]


def _period_claim(text):
    return {
        "claims": [{
            "text": text,
            "source_id": "LEGIARTI000000000001",
            "quote": "Les agents territoriaux bénéficient d'une protection statutaire.",
        }]
    }


def _period_source(endpoint="START"):
    return {
        "source_type": "LEGIFRANCE_LODA",
        "source_id": "LEGIARTI000000000001",
        "title": "Disposition relative aux agents territoriaux",
        "excerpt": "Les agents territoriaux bénéficient d'une protection statutaire.",
        "citation_integrity": {"valid": True},
        "temporal_status": "VERSION_RETRIEVED_AT_REQUESTED_DATE",
        "public_service_scope": "FPT",
        "analysis_eligible": True,
        "claim_eligible": True,
        "version_endpoint": endpoint,
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
    }


def test_claim_may_be_scoped_to_the_verified_start_endpoint():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _period_claim("Au 2024-01-01, les agents territoriaux bénéficient d'une protection statutaire."),
        [_period_source("START")],
        facts_period={
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "reference_date_for_retrieval": "2024-12-31",
            "ongoing": False,
        },
    )
    assert result["valid"] is True


@pytest.mark.parametrize("date_text", ["1er janvier 2024", "01/01/2024", "01-01-2024"])
def test_start_endpoint_accepts_equivalent_french_and_numeric_date_formats(date_text):
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _period_claim(f"Au {date_text}, les agents territoriaux bénéficient d'une protection statutaire."),
        [_period_source("START")],
        facts_period={
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "reference_date_for_retrieval": "2024-12-31",
            "ongoing": False,
        },
    )
    assert result["valid"] is True


def test_start_endpoint_still_rejects_a_different_french_date():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _period_claim("Au 02/01/2024, les agents territoriaux bénéficient d'une protection statutaire."),
        [_period_source("START")],
        facts_period={"period_start": "2024-01-01", "period_end": "2024-12-31"},
    )
    assert result["valid"] is False
    assert "claim_0:period_endpoint_not_date_scoped" in result["invalid_claims"]


def test_start_endpoint_cannot_support_a_whole_period_assertion():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _period_claim("Au 2024-01-01, sur toute la période, les agents territoriaux bénéficient d'une protection statutaire."),
        [_period_source("START")],
        facts_period={
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "reference_date_for_retrieval": "2024-12-31",
            "ongoing": False,
        },
    )
    assert result["valid"] is False
    assert "claim_0:unsupported_whole_period_assertion" in result["invalid_claims"]


def test_end_endpoint_requires_the_end_date_in_the_claim():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _period_claim("Au 2024-12-31, les agents territoriaux bénéficient d'une protection statutaire."),
        [_period_source("END")],
        facts_period={
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
            "reference_date_for_retrieval": "2024-12-31",
            "ongoing": False,
        },
    )
    assert result["valid"] is True


def test_claim_validator_rejects_mixed_versant_sources():
    from app.legal_assurance import validate_claim_evidence

    source = _period_source("START")
    source["public_service_scope"] = "MIXED_OR_CONFLICTING_PUBLIC_SERVICE_SCOPE"
    result = validate_claim_evidence(
        _period_claim("Au 2024-01-01, les agents territoriaux bénéficient d'une protection statutaire."),
        [source],
        facts_period={"period_start": "2024-01-01", "period_end": "2024-12-31"},
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_entailment_verifier_uses_excerpt_not_unrelated_full_text():
    from app.ai_provider import validate_entailment_verdicts

    result = validate_entailment_verdicts(
        {"verdicts": [{
            "claim_index": 0,
            "source_id": "LEGIARTI000000000001",
            "verdict": "SUPPORTED",
            "support_quote": "Passage présent uniquement dans le texte intégral non pertinent.",
        }]},
        [{
            "source_id": "LEGIARTI000000000001",
            "excerpt": "Extrait pertinent de vingt caractères au moins.",
            "full_text": "Passage présent uniquement dans le texte intégral non pertinent.",
        }],
        [{"source_id": "LEGIARTI000000000001", "text": "Proposition juridique de test."}],
    )
    assert result["valid"] is False


def test_entailment_verifier_allows_only_the_verified_endpoint_date():
    from app.ai_provider import validate_entailment_verdicts

    quote = "Les agents territoriaux bénéficient d'une protection statutaire."
    source = {
        "source_id": "LEGIARTI000000000001",
        "excerpt": quote,
        "version_endpoint": "START",
        "requested_effective_date": "2024-01-01",
    }
    payload = {"verdicts": [{
        "claim_index": 0,
        "source_id": source["source_id"],
        "verdict": "SUPPORTED",
        "support_quote": quote,
    }]}
    allowed = validate_entailment_verdicts(
        payload,
        [{"source_id": source["source_id"], "text": "Au 2024-01-01, les agents territoriaux bénéficient d'une protection statutaire."}],
        [source],
    )
    rejected = validate_entailment_verdicts(
        payload,
        [{"source_id": source["source_id"], "text": "Au 2024-12-31, les agents territoriaux bénéficient d'une protection statutaire."}],
        [source],
    )
    assert allowed["valid"] is True
    assert rejected["valid"] is False
    assert "verdict_0:support_quote_missing_claim_facts" in rejected["invalid"]


def test_claim_evidence_flags_unknown_uncovered_axis_without_discarding_verified_claims():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    claim_text = source["excerpt"]
    result = validate_claim_evidence({
        "claims": [{
            "text": claim_text,
            "source_id": source["source_id"],
            "quote": source["excerpt"],
            "axis": "santé et sécurité",
        }],
        "uncovered_axes": ["axe inventé"],
    }, [source], required_axes=["santé et sécurité", "rémunération"])

    assert result["valid"] is True
    assert result["partial"] is True
    assert result["claim_count"] == 1
    assert result["uncovered_axes"] == ["rémunération"]
    assert "unknown_or_invalid_uncovered_research_axis" in result["invalid_claims"]


def test_claim_evidence_flags_duplicate_uncovered_axis_declarations():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    claim_text = source["excerpt"]
    result = validate_claim_evidence({
        "claims": [{
            "text": claim_text,
            "source_id": source["source_id"],
            "quote": source["excerpt"],
            "axis": "santé et sécurité",
        }],
        "uncovered_axes": ["rémunération", "rémunération"],
    }, [source], required_axes=["santé et sécurité", "rémunération"])

    assert result["valid"] is True
    assert result["partial"] is True
    assert result["uncovered_axes"] == ["rémunération"]
    assert "duplicate_uncovered_research_axis" in result["invalid_claims"]


def test_source_set_ignores_malformed_connector_records():
    result = assess_source_set([
        None,
        "not-a-source-object",
        {"document_kind": "DECREE", "temporal_status": "IN_FORCE_ON_REQUESTED_DATE"},
    ])
    assert len(result["sources"]) == 1
    assert result["sources"][0]["legal_assurance"]["source_family"] == "DECREE"


def test_citation_validation_fails_closed_on_malformed_source_records():
    from app.legal_assurance import validate_answer_citations

    result = validate_answer_citations(
        "La règle est applicable.",
        [None, "not-a-source-object", {"source_id": "LEGIARTI000000000123", "citation_integrity": "valid"}],
    )
    assert result["valid"] is False
    assert "missing_explicit_source_citation" in result["invalid_references"]


def test_claim_validation_fails_closed_on_malformed_source_records():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé des agents.",
            "L'autorité territoriale organise le service et veille à la protection de la santé et de la sécurité des agents dans les conditions prévues par les textes.",
        ),
        [None, "not-a-source-object", {"source_id": "LEGIARTI000000000123", "citation_integrity": "valid"}],
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_claim_validation_rejects_non_object_citation_integrity_metadata():
    from app.legal_assurance import validate_claim_evidence

    for malformed_integrity in ("valid", ["valid"], 1, True):
        source = {
            "source_id": "LEGIARTI000000000123",
            "source_type": "LEGIFRANCE_API",
            "citation_integrity": malformed_integrity,
            "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
            "excerpt": "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            "official_source": True,
        }
        result = validate_claim_evidence(
            _evidence_claim(
                "L'autorité territoriale veille à la santé des agents.",
                "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            ),
            [source],
        )
        assert result["valid"] is False
        assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


def test_case_law_is_not_mislabeled_as_a_normative_text():
    result = classify_legal_source({
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "temporal_status": "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
        "content_kind": "FULL_TEXT",
    })
    assert result["authority_level"] == "JURISPRUDENCE"
    assert result["usable_for_interpretation"] is True
    assert result["normative"] is False


def test_verified_decree_remains_classified_as_a_primary_norm():
    result = classify_legal_source({
        "document_kind": "DECREE",
        "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
    })
    assert result["authority_level"] == "PRIMARY_LEGAL"
    assert result["normative"] is True


def test_assess_source_set_reports_malformed_records_as_incomplete():
    result = assess_source_set([
        None,
        "not-a-source-object",
        {"document_kind": "DECREE", "temporal_status": "IN_FORCE_ON_REQUESTED_DATE"},
    ])
    assert len(result["sources"]) == 1
    assert result["status"] == "VERIFICATION_INCOMPLETE"
    assert any("mal formé" in warning for warning in result["warnings"])


def test_assess_source_set_reports_non_list_payload_as_incomplete():
    result = assess_source_set({"source_id": "not-a-list"})
    assert result["sources"] == []
    assert result["status"] == "VERIFICATION_INCOMPLETE"
    assert any("format attendu" in warning for warning in result["warnings"])


def test_citation_validator_handles_non_collection_source_payload():
    from app.legal_assurance import validate_answer_citations

    result = validate_answer_citations(
        "L'autorité territoriale doit respecter les règles applicables.",
        42,
    )
    assert result["valid"] is False
    assert "missing_explicit_source_citation" in result["invalid_references"]


def test_claim_validator_handles_non_collection_sources_and_malformed_period():
    from app.legal_assurance import validate_claim_evidence

    result = validate_claim_evidence(
        {"claims": [{
            "text": "L'autorité territoriale doit respecter les règles applicables.",
            "source_id": "SRC-123456",
            "quote": "L'autorité territoriale doit respecter les règles applicables.",
        }]},
        sources=42,
        required_axes="not-a-list",
        facts_period="not-a-dictionary",
    )
    assert result["valid"] is False
    assert result["invalid_claims"] == [
        "claim_0:source_missing_ineligible_or_ambiguous",
    ]


@pytest.mark.parametrize("versant", ["FPE", "FPH"])
def test_claim_evidence_accepts_a_verified_source_for_the_selected_non_territorial_branch(versant):
    from app.legal_assurance import validate_claim_evidence

    quote = (
        "Les agents de la fonction publique bénéficient des garanties prévues "
        "par les dispositions applicables à leur versant."
    )
    source = _verified_evidence_source(
        title=f"Dispositions relatives à la fonction publique — {versant}",
        text=quote,
        excerpt=quote,
        public_service_scope=versant,
    )
    result = validate_claim_evidence(
        _evidence_claim(
            "Les agents de la fonction publique bénéficient des garanties prévues.",
            quote,
        ),
        [source],
        public_service=versant,
    )
    assert result["valid"] is True


def test_claim_evidence_rejects_a_different_public_service_branch_even_when_official():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(public_service_scope="FPH")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé des agents.",
            source["excerpt"],
        ),
        [source],
        public_service="FPE",
    )
    assert result["valid"] is False

def test_claim_evidence_can_quote_beyond_the_compact_display_excerpt():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(
        excerpt="Extrait court réservé à l'affichage.",
        analysis_excerpt=(
            "L'autorité territoriale organise le service et veille à la protection "
            "de la santé et de la sécurité des agents dans les conditions prévues par les textes. "
            "Cette phrase figure au-delà de l'extrait court et reste vérifiable."
        ),
    )
    quote = "Cette phrase figure au-delà de l'extrait court et reste vérifiable."
    result = validate_claim_evidence(
        _evidence_claim(
            "Cette phrase figure au-delà de l'extrait court et reste vérifiable.",
            quote,
        ),
        [source],
    )

    assert result["valid"] is True

def test_claim_evidence_rejects_national_source_without_explicit_versant_scope():
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source()
    source.pop("public_service_scope")
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
        public_service="FPT",
    )
    assert result["valid"] is False
    assert "claim_0:source_missing_ineligible_or_ambiguous" in result["invalid_claims"]


@pytest.mark.parametrize(
    ("scope", "versant", "expected"),
    [
        ("FPT", "FPT", True),
        ("FPE", "FPT", False),
        ("FPH", "FPT", False),
        ("COMMON_PUBLIC_SERVICE", "FPT", True),
        ("FPT_REFERENCE", "FPT", True),
        ("FPT_REFERENCE", "FPE", False),
    ],
)
def test_claim_evidence_requires_explicit_matching_versant_or_common_scope(
    scope, versant, expected,
):
    from app.legal_assurance import validate_claim_evidence

    source = _verified_evidence_source(public_service_scope=scope)
    result = validate_claim_evidence(
        _evidence_claim(
            "L'autorité territoriale veille à la santé et à la sécurité des agents.",
            source["excerpt"],
        ),
        [source],
        public_service=versant,
    )
    assert result["valid"] is expected



@pytest.mark.parametrize(
    "claim_text",
    [
        "Pendant 2024, les agents territoriaux bénéficient d'une protection statutaire.",
        "Durant 2024, les agents territoriaux bénéficient d'une protection statutaire.",
        "Au cours de 2024, les agents territoriaux bénéficient d'une protection statutaire.",
    ],
)
def test_a_calendar_year_reference_is_not_mistaken_for_a_whole_period_assertion(claim_text):
    from app.legal_assurance import _WHOLE_PERIOD_ASSERTION_RE

    assert _WHOLE_PERIOD_ASSERTION_RE.search(claim_text) is None


@pytest.mark.parametrize(
    "claim_text",
    [
        "Pendant toute l'année, les agents territoriaux bénéficient d'une protection statutaire.",
        "Sur l'ensemble de la période, les agents territoriaux bénéficient d'une protection statutaire.",
        "Du 2024-01-01 au 2024-12-31, les agents territoriaux bénéficient d'une protection statutaire.",
    ],
)
def test_explicit_whole_period_assertions_remain_detected(claim_text):
    from app.legal_assurance import _WHOLE_PERIOD_ASSERTION_RE

    assert _WHOLE_PERIOD_ASSERTION_RE.search(claim_text) is not None
