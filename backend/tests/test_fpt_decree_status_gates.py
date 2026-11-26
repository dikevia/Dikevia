import pytest

from app.fpt_scope import classify_public_service_scope


@pytest.mark.parametrize(
    "title",
    [
        "Décret n° 87-602 du 30 juillet 1987 relatif aux congés de maladie des fonctionnaires territoriaux",
        "Décret n° 89-677 du 18 septembre 1989 relatif à la procédure disciplinaire des fonctionnaires territoriaux",
        "Décret n° 2021-1462 du 8 novembre 2021 relatif au temps partiel thérapeutique dans la fonction publique territoriale",
        "Décret n° 2026-705 relatif au CITIS des fonctionnaires territoriaux",
    ],
)
def test_functionary_only_fpt_decrees_require_explicit_functionary_status(title):
    source = {"source_type": "LEGIFRANCE_API", "title": title, "text": "Dispositions applicables aux fonctionnaires territoriaux."}
    unknown = classify_public_service_scope(source, target_versant="FPT")
    titular = classify_public_service_scope(source, target_versant="FPT", agent_status="TITULAIRE_EXPLICIT")
    contract = classify_public_service_scope(source, target_versant="FPT", agent_status="CONTRACTUEL_EXPLICIT")

    assert unknown["analysis_eligible"] is True
    assert unknown["claim_eligible"] is False
    assert titular["claim_eligible"] is True
    assert contract["claim_eligible"] is False


def test_decree_91_298_requires_functionary_and_non_complete_status():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Décret n° 91-298 du 20 mars 1991 portant dispositions statutaires applicables aux fonctionnaires territoriaux nommés dans des emplois permanents à temps non complet",
        "article": "34-1",
        "text": "Le fonctionnaire en activité peut être autorisé à accomplir un service à temps partiel pour raison thérapeutique.",
    }
    non_complete = classify_public_service_scope(
        source, target_versant="FPT",
        agent_status="TITULAIRE_EXPLICIT",
        agent_working_time_status="NON_COMPLETE_EXPLICIT",
    )
    full_time = classify_public_service_scope(
        source, target_versant="FPT",
        agent_status="TITULAIRE_EXPLICIT",
        agent_working_time_status="FULL_TIME_EXPLICIT",
    )
    contract = classify_public_service_scope(
        source, target_versant="FPT",
        agent_status="CONTRACTUEL_EXPLICIT",
        agent_working_time_status="NON_COMPLETE_EXPLICIT",
    )

    assert non_complete["claim_eligible"] is True
    assert full_time["claim_eligible"] is False
    assert contract["claim_eligible"] is False


def test_decree_88_145_is_reserved_to_explicit_contract_agents():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Décret n° 88-145 du 15 février 1988 relatif aux agents contractuels de la fonction publique territoriale",
        "text": "Dispositions relatives aux agents contractuels territoriaux.",
    }
    contract = classify_public_service_scope(
        source, target_versant="FPT", agent_status="CONTRACTUEL_EXPLICIT"
    )
    titular = classify_public_service_scope(
        source, target_versant="FPT", agent_status="TITULAIRE_EXPLICIT"
    )
    unknown = classify_public_service_scope(source, target_versant="FPT")

    assert contract["claim_eligible"] is True
    assert titular["claim_eligible"] is False
    assert unknown["claim_eligible"] is False
