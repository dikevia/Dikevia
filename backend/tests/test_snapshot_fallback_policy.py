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


def test_snapshot_discovery_only_source_is_not_shown_as_answer_evidence():
    from app.orchestrator import filter_irrelevant_sources_for_display

    sources = [
        {
            "source_id": "snapshot",
            "source_type": "CGFP_SNAPSHOT",
            "reference_role": "SNAPSHOT_DISCOVERY_ONLY",
            "analysis_eligible": True,
            "research_axis_relevant": True,
        },
        {
            "source_id": "live",
            "source_type": "LEGIFRANCE_API",
            "analysis_eligible": True,
            "research_axis_relevant": True,
        },
    ]

    visible = filter_irrelevant_sources_for_display(sources)

    assert [source["source_id"] for source in visible] == ["live"]


def test_relevant_live_cgfp_article_suppresses_snapshot_fallback():
    from app.orchestrator import should_use_cgfp_snapshot_fallback

    found = {
        "results": [
            {
                "article": "L111-1",
                "title": "Code général de la fonction publique — article L111-1",
                "text": "La liberté d'opinion est garantie aux agents publics.",
            }
        ]
    }
    live = [{
        "source_type": "LEGIFRANCE_API",
        "article": "L111-1",
        "title": "Code général de la fonction publique — article L111-1",
        "text": "La liberté d'opinion est garantie aux agents publics.",
        "analysis_eligible": True,
    }]

    assert should_use_cgfp_snapshot_fallback(
        None,
        found,
        ["Que prévoit l'article L111-1 du CGFP ?"],
        target_versant="FPT",
        live_sources=live,
    ) is False
