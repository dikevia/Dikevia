from pathlib import Path


def test_beta_document_uploads_are_disabled_without_antivirus_service():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text()
    assert "Import temporairement désactivé sur cette bêta" in html
    personal = html.split('id="personalZipForm"', 1)[1].split("</form>", 1)[0]
    assert 'type="file"' in personal and "disabled" in personal
    org = html.split('id="uploadForm"', 1)[1].split("</form>", 1)[0]
    assert 'type="file"' in org and "disabled" in org
    assert "Le serveur refuse tout dépôt sans analyse antivirus" in html
