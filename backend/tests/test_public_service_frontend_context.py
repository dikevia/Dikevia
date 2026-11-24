from pathlib import Path


def test_fpe_fph_chat_can_capture_specific_employer_context():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")

    assert 'id="askEmployerDetailsField"' in html
    assert 'id="askEmployerDetails"' in html
    assert "selectedPublicService==='FPT'" in html
    assert "selectedPublicService==='FPE'" in html
    assert "Ministère, rectorat, préfecture, administration" in html
    assert "Centre hospitalier, CHU, établissement public de santé" in html
    assert "const employer=employerDetails||$('#askEmployer').value" in html


def test_chat_history_preserves_custom_employer_label():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")
    assert "employerLabels[extra.employer]||extra.employer||''" in html
