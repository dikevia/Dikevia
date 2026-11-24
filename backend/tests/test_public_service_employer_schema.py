import pytest
from pydantic import ValidationError

from app.schemas import AskRequest


def payload(public_service: str, employer: str):
    return {
        "public_service": public_service,
        "employer": employer,
        "question": "Quelles règles sont applicables à ma situation ?",
    }


@pytest.mark.parametrize(
    ("versant", "employer"),
    [
        ("FPE", "Ministère de l'Intérieur"),
        ("FPE", "Rectorat de Lyon"),
        ("FPH", "Centre hospitalier universitaire"),
        ("FPH", "Établissement public de santé"),
    ],
)
def test_fpe_fph_accept_specific_employer_context(versant, employer):
    request = AskRequest(**payload(versant, employer))
    assert request.public_service == versant
    assert request.employer == employer


@pytest.mark.parametrize("employer", ["NATIONAL", "VILLE_SAINT_ETIENNE", "SAINT_ETIENNE_METROPOLE"])
def test_fpt_keeps_existing_employer_values(employer):
    request = AskRequest(**payload("FPT", employer))
    assert request.employer == employer


def test_fpt_rejects_non_territorial_employer_value():
    with pytest.raises(ValidationError):
        AskRequest(**payload("FPT", "Ministère de l'Intérieur"))


@pytest.mark.parametrize("employer", ["", "   ", "x" * 181])
def test_employer_context_is_nonempty_and_bounded(employer):
    with pytest.raises(ValidationError):
        AskRequest(**payload("FPH", employer))
