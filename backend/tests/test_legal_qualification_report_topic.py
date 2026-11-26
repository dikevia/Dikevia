from app.legal_qualification import qualify_legal_question


def test_hierarchical_report_contestation_is_recognized_as_its_own_topic():
    result = qualify_legal_question(
        "Mon chef a fait un rapport circonstancié contre moi, puis-je le contester ?",
        public_service="FPT",
    )

    assert "REPORT_HIERARCHICAL_CONTESTATION" in result["topics"]
