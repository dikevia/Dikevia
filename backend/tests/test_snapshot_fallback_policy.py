from app.orchestrator import _apply_cgfp_snapshot_fallback_policy


def test_snapshot_is_discovery_only_when_live_cgfp_is_available():
    source = {
        "source_type": "CGFP_SNAPSHOT",
        "claim_eligible": True,
        "general_info_eligible": True,
        "reference_role": "CGFP_SNAPSHOT_FALLBACK_EVIDENCE",
    }

    result = _apply_cgfp_snapshot_fallback_policy(
        source, fallback_enabled=False, facts_date_present=False,
    )

    assert result["reference_role"] == "SNAPSHOT_DISCOVERY_ONLY"
    assert result["claim_eligible"] is False
    assert result["general_info_eligible"] is False
    assert source["reference_role"] == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"


def test_snapshot_can_be_used_as_bounded_fallback_only_when_enabled_for_general_info():
    source = {
        "source_type": "CGFP_SNAPSHOT",
        "claim_eligible": True,
        "general_info_eligible": True,
    }

    result = _apply_cgfp_snapshot_fallback_policy(
        source, fallback_enabled=True, facts_date_present=False,
    )

    assert result["reference_role"] == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
    assert result["claim_eligible"] is True
    assert result["general_info_eligible"] is True


def test_snapshot_never_becomes_fallback_evidence_for_a_historical_facts_date():
    source = {
        "source_type": "CGFP_SNAPSHOT",
        "claim_eligible": True,
        "general_info_eligible": True,
    }

    result = _apply_cgfp_snapshot_fallback_policy(
        source, fallback_enabled=True, facts_date_present=True,
    )

    assert result["reference_role"] == "SNAPSHOT_DISCOVERY_ONLY"
    assert result["claim_eligible"] is False
    assert result["general_info_eligible"] is False


def test_live_legal_source_is_not_changed_by_snapshot_policy():
    source = {
        "source_type": "LEGIFRANCE_API",
        "claim_eligible": True,
        "general_info_eligible": True,
    }

    result = _apply_cgfp_snapshot_fallback_policy(
        source, fallback_enabled=False, facts_date_present=False,
    )

    assert result == source
