from datetime import date

import pytest

from app.instances import prepare_instance_with_legal_sources


class FakeLegifrance:
    configured = True

    def __init__(self):
        self.code_queries = []
        self.regulatory_queries = []

    async def search_code_articles(self, query, effective_date):
        self.code_queries.append((query, effective_date))
        return [{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000000000001",
            "article": "L123-1",
            "title": "Code général de la fonction publique — L123-1",
            "text": "Dispositions applicables aux agents publics. " * 8,
            "excerpt": "Dispositions applicables aux agents publics.",
            "effective_date_requested": effective_date.isoformat(),
            "official_source": True,
            "source_url": "https://www.legifrance.gouv.fr/",
        }]

    async def search_regulatory_texts(self, query, effective_date, limit=10):
        self.regulatory_queries.append((query, effective_date, limit))
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif aux instances territoriales",
            "official_number": "2021-571",
            "excerpt": "Dispositions réglementaires relatives aux instances.",
            "full_text": "Dispositions réglementaires relatives aux instances. " * 8,
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "version_status": "UNKNOWN",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
        }]


class FakeCaseLaw:
    def __init__(self):
        self.queries = []

    async def search(self, query, effective_date):
        self.queries.append((query, effective_date))
        return [{
            "source_type": "LEGIFRANCE_CETAT_SEARCH",
            "source_id": "CETATEXT000000000001",
            "title": "Décision administrative relative au dialogue social",
            "decision_date": "2024-01-15",
            "excerpt": "Extrait de la décision.",
            "full_text_retrieved": False,
            "official_source": True,
            "source_url": "https://www.legifrance.gouv.fr/search/cetat",
        }]


@pytest.mark.asyncio
async def test_instance_preparation_reuses_all_three_existing_piste_search_families():
    legal = FakeLegifrance()
    case_law = FakeCaseLaw()
    effective_date = date(2026, 11, 27)

    result = await prepare_instance_with_legal_sources(
        "CST",
        "Organisation du travail et conditions de travail",
        legifrance_connector=legal,
        case_law_connector=case_law,
        effective_date=effective_date,
    )

    assert result["legal_conclusion"] is False
    assert result["legal_research"]["provider"] == "PISTE_LEGIFRANCE"
    assert result["legal_research"]["status"] == "SEARCHED"
    assert [item["family"] for item in result["legal_research"]["sources"]] == [
        "cgfp", "textes_reglementaires", "jurisprudence_administrative"
    ]
    assert len(legal.code_queries) == 1
    assert len(legal.regulatory_queries) == 1
    assert len(case_law.queries) == 1
    assert all(call[1] == effective_date for call in (
        legal.code_queries[0], legal.regulatory_queries[0], case_law.queries[0]
    ))
    case_law_source = result["legal_research"]["sources"][2]
    assert case_law_source["full_text_retrieved"] is False
    assert "métadonnées/extrait uniquement" in case_law_source["verification_note"]


@pytest.mark.asyncio
async def test_instance_preparation_keeps_lexical_checklist_when_piste_is_not_configured():
    class Unconfigured:
        configured = False

    result = await prepare_instance_with_legal_sources(
        "FS",
        "Risques psychosociaux et charge de travail",
        legifrance_connector=Unconfigured(),
        case_law_connector=FakeCaseLaw(),
        effective_date=date(2026, 11, 27),
    )

    assert result["points"]
    assert result["legal_research"]["status"] == "NOT_CONFIGURED"
    assert result["legal_research"]["sources"] == []


@pytest.mark.asyncio
async def test_instance_preparation_reports_partial_piste_failures_without_losing_other_sources():
    class PartlyUnavailable(FakeLegifrance):
        async def search_regulatory_texts(self, query, effective_date, limit=10):
            raise RuntimeError("upstream unavailable")

    legal = PartlyUnavailable()
    case_law = FakeCaseLaw()
    result = await prepare_instance_with_legal_sources(
        "CCP",
        "Non-renouvellement d'un agent contractuel",
        legifrance_connector=legal,
        case_law_connector=case_law,
        effective_date=date(2026, 11, 27),
    )

    assert result["legal_research"]["status"] == "PARTIAL"
    assert len(result["legal_research"]["sources"]) == 2
    regulatory = next(
        item for item in result["legal_research"]["searches"]
        if item["family"] == "TEXTES_REGLEMENTAIRES"
    )
    assert regulatory["status"] == "ERROR"
    assert regulatory["error_type"] == "RuntimeError"



def test_instance_ui_renders_law_sources_and_does_not_hide_metadata_only_jurisprudence():
    from pathlib import Path

    frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    source = frontend.read_text(encoding="utf-8")
    assert "async function prepareInstance()" in source
    assert "async async function prepareInstance()" not in source
    assert "result.legal_research" in source
    assert "full_text_retrieved" in source
    assert "Consulter sur Légifrance" in source
    assert "function invalidateInstancePreparation()" in source
    assert "latestInstancePreparation=null" in source
    assert "$('#instanceObject').addEventListener('input',invalidateInstancePreparation)" in source
    assert "card.dataset.instanceChoice===$('#instanceType').value" in source
    assert "SOURCES RETOURNÉES" in source
    assert "full_text_retrieved" in source
    assert "MISSION JURIS" in source
    assert "data.cst_qualification" in source
    assert "event.target.id!=='instanceObject'" in source
    assert "event.target.id!=='instanceType'" in source
    assert "document.addEventListener('click',event=>{const button=event.target?.closest?.('[data-instance-choice]')" in source
    assert "card.setAttribute('aria-pressed',String(active))" in source
    assert all(f'data-instance-choice="{choice}"' in source for choice in ("CST", "CAP", "CCP", "FS"))
    theme = frontend.with_name("dikevia-chat-theme.css").read_text(encoding="utf-8")
    assert "pointer-events:auto" in theme
    assert "touch-action:manipulation" in theme
    assert "dikevia-chat-theme.css?v=20261128-instance-touch-fix-1" in source
    assert "touch-action:manipulation" in theme
    assert ".instance-launch-card:focus-visible" in theme


@pytest.mark.asyncio
async def test_instance_preparation_distinguishes_full_text_from_case_law_metadata():
    result = await prepare_instance_with_legal_sources(
        "FS",
        "Risques psychosociaux et conditions de travail",
        legifrance_connector=FakeLegifrance(),
        case_law_connector=FakeCaseLaw(),
        effective_date=date(2026, 11, 27),
    )

    sources = result["legal_research"]["sources"]
    assert sources[0]["full_text_retrieved"] is True
    assert sources[1]["full_text_retrieved"] is True
    assert sources[2]["full_text_retrieved"] is False
    assert "métadonnées/extrait uniquement" in sources[2]["verification_note"]


@pytest.mark.parametrize(
    ("objet", "expected_code"),
    [
        ("Alerte pour danger grave et imminent et droit de retrait", "danger_grave_imminent"),
        ("Visite de locaux et visite de service", "visites"),
        ("Enquête après accident de service", "enquete"),
        ("Mise à jour du DUERP et programme annuel de prévention", "duerp_programme"),
    ],
)
def test_f3sct_operational_preparation_covers_core_missions(objet, expected_code):
    from app.instances import prepare_instance

    result = prepare_instance("FS", objet)

    matching = [point for point in result["points"] if point["code"] == expected_code]
    assert len(matching) == 1
    assert len(matching[0]["questions"]) >= 4
    assert len(matching[0]["documents"]) >= 4
    assert result["legal_conclusion"] is False


@pytest.mark.asyncio
async def test_f3sct_operational_topics_feed_the_official_legal_search_context():
    legal = FakeLegifrance()
    case_law = FakeCaseLaw()

    result = await prepare_instance_with_legal_sources(
        "FS",
        "Mise à jour du DUERP et programme annuel de prévention",
        legifrance_connector=legal,
        case_law_connector=case_law,
        effective_date=date(2026, 11, 28),
    )

    assert result["points"][0]["code"] == "duerp_programme"
    assert "DUERP" in legal.code_queries[0][0]
    assert "DUERP" in case_law.queries[0][0]
    assert result["legal_research"]["status"] == "SEARCHED"


def test_native_instance_preparation_is_handed_to_the_shared_juris_chat():
    from pathlib import Path

    native = (
        Path(__file__).resolve().parents[2]
        / "android" / "app" / "src" / "main" / "java"
        / "fr" / "dikevia" / "commercial" / "feature" / "home"
        / "NativeHomeScreen.kt"
    )
    source = native.read_text(encoding="utf-8")
    assert "buildJurisInstancePrompt(instancePreparation)" in source
    assert "onSendQuestion(buildJurisInstancePrompt(instancePreparation))" in source
    assert "api.ask(" not in source
    assert "Approfondir cette préparation avec JURIS" in source


def test_android_f3sct_label_maps_to_backend_fs_instance_key():
    from pathlib import Path

    activity = (
        Path(__file__).resolve().parents[2]
        / "android" / "app" / "src" / "main" / "java"
        / "fr" / "dikevia" / "commercial" / "NativePreviewActivity.kt"
    )
    source = activity.read_text(encoding="utf-8")
    assert 'instance.equals("F3SCT", ignoreCase = true)' in source
    assert 'else instance' in source
    assert 'backendInstance,' in source


def test_native_instance_result_is_bound_to_the_selected_instance():
    from pathlib import Path

    native = (
        Path(__file__).resolve().parents[2]
        / "android" / "app" / "src" / "main" / "java"
        / "fr" / "dikevia" / "commercial" / "feature" / "home"
        / "NativeHomeScreen.kt"
    )
    source = native.read_text(encoding="utf-8")
    assert "preparationMatchesInstance(instancePreparation, selectedInstance)" in source
    assert 'selectedInstance.equals("F3SCT", ignoreCase = true)' in source
    assert '"F3SCT (FS)"' in source
