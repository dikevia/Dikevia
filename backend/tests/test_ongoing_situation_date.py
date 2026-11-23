import pytest

from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest


@pytest.mark.asyncio
async def test_ongoing_situation_requires_start_date_before_research():
    result = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            question="Quels sont mes droits dans cette situation ?",
            situation_ongoing=True,
        ),
        organization_id="00000000-0000-0000-0000-000000000001",
        conn=None,
    )

    assert result.verification_status == "NON_VERIFIE"
    assert result.sources == []
    assert "date de début" in result.missing_information[0]
