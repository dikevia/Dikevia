from pathlib import Path


def test_chat_privacy_notice_requires_fictitious_or_anonymized_data():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")
    required_phrases = (
        "Mode pilote — données fictives ou anonymisées uniquement",
        "peuvent être transmis à Google Gemini",
        "Google indique que, sur le niveau gratuit de l’API Gemini, le contenu transmis peut être utilisé pour améliorer ses produits",
        "le niveau effectivement utilisé par ce service n’étant pas encore vérifié",
        "Les échanges sont enregistrés dans votre espace d’organisation",
        "N’indiquez aucun nom, matricule, coordonnée, bulletin de paie",
        "donnée médicale, disciplinaire ou syndicale nominative",
        "Les réponses précédentes ne remplacent jamais les sources juridiques vérifiées",
    )
    for phrase in required_phrases:
        assert phrase in html
