import pytest

from app.fpt_scope import classify_public_service_scope


@pytest.mark.parametrize(
    ("article", "text"),
    [
        ("L111-1", "La liberté d'opinion est garantie aux agents publics."),
        ("L114-1", "Les agents publics exercent le droit de grève dans le cadre des lois qui le réglementent."),
        ("L137-1", "Le dossier individuel de l'agent public doit comporter toutes les pièces intéressant sa situation administrative."),
        ("L137-4", "Tout agent public a accès à son dossier individuel."),
    ],
)
def test_live_common_cgfp_articles_can_support_claims(article, text):
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": text,
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["scope"] == "COMMON_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is True


@pytest.mark.parametrize("article", ["L111-1", "L114-1", "L137-1", "L137-4"])
def test_common_cgfp_snapshot_is_context_only(article):
    source = {
        "source_type": "CGFP_SNAPSHOT",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": "Disposition du code général de la fonction publique concernant les agents publics.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["scope"] == "COMMON_PUBLIC_SERVICE"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


@pytest.mark.parametrize("number", range(18, 24))
def test_citis_cgfp_articles_remain_context_only_until_agent_status_is_verified(number):
    article = f"L822-{number}"
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": "Disposition relative à l'accident de service ou à la maladie contractée en service du fonctionnaire.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


@pytest.mark.parametrize("number", range(18, 24))
def test_citis_cgfp_snapshot_remains_non_claim_evidence(number):
    article = f"L822-{number}"
    source = {
        "source_type": "CGFP_SNAPSHOT",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": "Disposition relative à l'accident de service ou à la maladie contractée en service du fonctionnaire.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


def test_l532_9_is_fpt_context_only_until_agent_status_is_verified():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L532-9",
        "article": "L532-9",
        "text": "L'autorité territoriale saisit le conseil de discipline par un rapport précisant les faits reprochés.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["scope"] == "FPT"
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False

def test_functionary_only_disciplinary_article_remains_context_only():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L532-4",
        "article": "L532-4",
        "text": "Le fonctionnaire poursuivi disciplinairement a droit à la communication de son dossier.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


@pytest.mark.parametrize("number", range(1, 7))
def test_therapeutic_part_time_cgfp_articles_remain_context_only_until_agent_status_is_verified(number):
    article = f"L823-{number}"
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": "Le fonctionnaire en activité peut être autorisé à accomplir un service à temps partiel pour raison thérapeutique.",
    }
    result = classify_public_service_scope(source, target_versant="FPT")
    assert result["analysis_eligible"] is True
    assert result["claim_eligible"] is False


@pytest.mark.parametrize("number", range(18, 24))
def test_citis_live_claim_requires_explicit_functionary_status(number):
    article = f"L822-{number}"
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": f"Code général de la fonction publique — article {article}",
        "article": article,
        "text": "Disposition relative à l'accident de service ou à la maladie contractée en service du fonctionnaire.",
    }
    result = classify_public_service_scope(source, target_versant="FPT", agent_status="TITULAIRE_EXPLICIT")
    assert result["claim_eligible"] is True


def test_citis_live_claim_is_rejected_for_explicit_contract_agent():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L822-18",
        "article": "L822-18",
        "text": "Disposition relative à l'accident de service ou à la maladie contractée en service du fonctionnaire.",
    }
    result = classify_public_service_scope(source, target_versant="FPT", agent_status="CONTRACTUEL_EXPLICIT")
    assert result["claim_eligible"] is False


def test_l532_4_live_claim_requires_explicit_functionary_status():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L532-4",
        "article": "L532-4",
        "text": "Le fonctionnaire poursuivi disciplinairement a droit à la communication de son dossier.",
    }
    result = classify_public_service_scope(source, target_versant="FPT", agent_status="TITULAIRE_EXPLICIT")
    assert result["claim_eligible"] is True


def test_l532_9_live_claim_requires_explicit_functionary_status():
    source = {
        "source_type": "LEGIFRANCE_API",
        "title": "Code général de la fonction publique — article L532-9",
        "article": "L532-9",
        "text": "L'autorité territoriale saisit le conseil de discipline par un rapport précisant les faits reprochés.",
    }
    result = classify_public_service_scope(source, target_versant="FPT", agent_status="FONCTIONNAIRE_STATUS_UNSPECIFIED")
    assert result["claim_eligible"] is True
