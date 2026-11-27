"""Conservative CST topic qualification against the CGFP in force.

This module identifies documentary candidates from explicit topic terms. It
does not decide whether a concrete project legally requires consultation.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any


CGFP_REFERENCES = {
    "consultation": "CGFP, article R. 253-7",
    "debate": "CGFP, articles R. 253-8 and R. 253-9",
    "information": "CGFP, article R. 253-10",
}

# These topic labels track the current structure of R. 253-7 (as amended
# through 1 August 2026), R. 253-9 and R. 253-10. Keywords are discovery
# triggers, not substitutes for checking the exact project and legal basis.
CST_TOPIC_RULES: tuple[dict[str, Any], ...] = (
    {"code": "organisation_services", "label": "Fonctionnement et organisation des services", "kind": "consultation", "article": "R. 253-7, 1°", "keywords": ("organisation des services", "organisation du service", "réorganisation", "reorganisation", "fonctionnement des services")},
    {"code": "conditions_travail_reorganisation", "label": "Aménagement important lié à une réorganisation et affectant santé, sécurité ou conditions de travail", "kind": "consultation", "article": "R. 253-7, 2°", "keywords": ("réorganisation et conditions de travail", "reorganisation et conditions de travail", "aménagement important", "amenagement important")},
    {"code": "egalite_plan", "label": "Projet de plan d'action relatif à l'égalité professionnelle", "kind": "consultation", "article": "R. 253-7, 3°", "keywords": ("plan d'action égalité professionnelle", "plan d'action relatif à l'égalité", "plan egalite professionnelle")},
    {"code": "vote_electronique", "label": "Recours au vote électronique pour les élections professionnelles", "kind": "consultation", "article": "R. 253-7, 4°", "keywords": ("vote électronique", "vote electronique")},
    {"code": "outils_numeriques_syndicaux", "label": "Modalités d'utilisation des technologies numériques par les organisations syndicales", "kind": "consultation", "article": "R. 253-7, 5°", "keywords": ("outils numériques syndicaux", "technologies numériques des syndicats", "outils numeriques syndicaux")},
    {"code": "autorisations_absence_representants", "label": "Majoration du contingent annuel d'autorisations d'absence des représentants du personnel", "kind": "consultation", "article": "R. 253-7, 6°", "keywords": ("contingent annuel d'autorisations d'absence", "autorisations d'absence des représentants")},
    {"code": "rsu_projet", "label": "Projet de rapport social unique", "kind": "consultation", "article": "R. 253-7, 7°", "keywords": ("projet de rapport social unique", "projet de rsu")},
    {"code": "ldg_strategie", "label": "Projets de lignes directrices de gestion relatives à la stratégie RH et aux parcours professionnels", "kind": "consultation", "article": "R. 253-7, 8°", "keywords": ("projet de lignes directrices de gestion", "ldg stratégie rh", "ldg strategie rh", "promotion et valorisation des parcours")},
    {"code": "ldg_promotion_interne_cdg", "label": "LDG relatives à la promotion interne élaborées par les centres de gestion", "kind": "consultation", "article": "R. 253-7, 9°", "keywords": ("ldg promotion interne centre de gestion", "lignes directrices promotion interne cdg")},
    {"code": "dossier_individuel_numerique", "label": "Gestion des dossiers individuels sur support électronique", "kind": "consultation", "article": "R. 253-7, 10°", "keywords": ("dossier individuel électronique", "dossiers individuels sur support électronique", "dossier agent dématérialisé")},
    {"code": "criteres_evaluation", "label": "Critères d'appréciation de la valeur professionnelle", "kind": "consultation", "article": "R. 253-7, 11°", "keywords": ("critères d'évaluation professionnelle", "critères d'appréciation de la valeur professionnelle", "criteres valeur professionnelle")},
    {"code": "taux_avancement_grade", "label": "Taux d'avancement de grade", "kind": "consultation", "article": "R. 253-7, 12°", "keywords": ("taux d'avancement de grade", "ratios d'avancement de grade")},
    {"code": "plan_formation_projet", "label": "Projet de plan de formation", "kind": "consultation", "article": "R. 253-7, 13°", "keywords": ("projet de plan de formation", "projet du plan de formation")},
    {"code": "suppression_emploi", "label": "Projet de suppression d'emploi", "kind": "consultation", "article": "R. 253-7, 14°", "keywords": ("suppression d'emploi", "suppression de poste")},
    {"code": "creation_cig", "label": "Projet de création d'un centre interdépartemental de gestion", "kind": "consultation", "article": "R. 253-7, 15°", "keywords": ("centre interdépartemental de gestion", "centre interdepartemental de gestion")},
    {"code": "accueil_salaries_prives", "label": "Organisation d'un service accueillant des salariés de droit privé mis à disposition", "kind": "consultation", "article": "R. 253-7, 16°", "keywords": ("salariés de droit privé mis à disposition", "salaries de droit prive mis a disposition")},
    {"code": "temps_travail_cet", "label": "Temps de travail ou compte épargne-temps", "kind": "consultation", "article": "R. 253-7, 17°", "keywords": ("temps de travail", "compte épargne-temps", "compte epargne temps", "cycles de travail", "annualisation du temps")},
    {"code": "journee_solidarite", "label": "Fixation de la journée de solidarité", "kind": "consultation", "article": "R. 253-7, 18°", "keywords": ("journée de solidarité", "journee de solidarite")},
    {"code": "politique_indemnitaire", "label": "Orientations stratégiques de politique indemnitaire et critères de répartition", "kind": "consultation", "article": "R. 253-7, 19°", "keywords": ("politique indemnitaire", "régime indemnitaire", "regime indemnitaire", "rifseep", "ifse", "cia")},
    {"code": "prime_interessement", "label": "Institution d'une prime d'intéressement liée à la performance des services", "kind": "consultation", "article": "R. 253-7, 20°", "keywords": ("prime d'intéressement", "prime d'interessement")},
    {"code": "action_sociale_psc", "label": "Orientations stratégiques d'action sociale et de protection sociale complémentaire", "kind": "consultation", "article": "R. 253-7, 21°", "keywords": ("action sociale", "protection sociale complémentaire", "protection sociale complementaire")},
    {"code": "action_groupe", "label": "Mesures dans le cadre d'une action de groupe", "kind": "consultation", "article": "R. 253-7, 22°", "keywords": ("action de groupe",)},
    {"code": "autre_consultation_legale", "label": "Autre consultation expressément prévue par un texte", "kind": "consultation", "article": "R. 253-7, 23°", "keywords": ("consultation obligatoire du cst", "consultation prévue par un texte", "consultation prevue par un texte")},
    {"code": "postes_responsabilite_formation", "label": "Liste des postes à responsabilité ouvrant une formation de professionnalisation", "kind": "consultation", "article": "R. 253-7, 24°", "keywords": ("postes à responsabilité", "postes a responsabilite", "formation de professionnalisation")},
    {"code": "programmation_travaux", "label": "Programmation annuelle des travaux du CST", "kind": "debate", "article": "R. 253-8", "keywords": ("programmation annuelle des travaux", "programme annuel des travaux du cst")},
    {"code": "accessibilite_qualite", "label": "Évaluation de l'accessibilité et de la qualité des services rendus", "kind": "debate", "article": "R. 253-9, 1°", "keywords": ("accessibilité des services", "qualité des services rendus", "qualite des services rendus")},
    {"code": "dematerialisation_methodes", "label": "Dématérialisation, évolutions technologiques et méthodes de travail", "kind": "debate", "article": "R. 253-9, 2°", "keywords": ("dématérialisation des procédures", "dematerialisation des procedures", "évolutions technologiques", "evolutions technologiques")},
    {"code": "egalite_discriminations_debat", "label": "Égalité professionnelle et prévention des discriminations", "kind": "debate", "article": "R. 253-9, 3°", "keywords": ("prévention des discriminations", "prevention des discriminations", "enjeux en matière d'égalité professionnelle", "enjeux en matiere d'egalite professionnelle")},
    {"code": "evolution_rh_rsu", "label": "Évolution des politiques RH sur la base du RSU", "kind": "debate", "article": "R. 253-9, 4°", "keywords": ("évolution des politiques rh", "evolution des politiques rh", "évolution rh fondée sur le rsu", "evolution rh fondee sur le rsu")},
    {"code": "bilan_pacte", "label": "Bilan annuel des recrutements par le PACTE", "kind": "debate", "article": "R. 253-9, 5°", "keywords": ("bilan pacte", "parcours d'accès aux carrières")},
    {"code": "alternance_concours", "label": "Bilan du dispositif expérimental d'accompagnement des contractuels en alternance préparant les concours", "kind": "debate", "article": "R. 253-9, 6°", "keywords": ("contractuels en alternance", "préparation aux concours en alternance")},
    {"code": "handicap_insertion", "label": "Politique d'insertion, de maintien dans l'emploi et d'accompagnement du handicap", "kind": "debate", "article": "R. 253-9, 7°", "keywords": ("maintien dans l'emploi des travailleurs handicapés", "insertion professionnelle handicap", "handicap et maintien dans l'emploi")},
    {"code": "bilan_apprentissage", "label": "Bilan annuel de l'apprentissage", "kind": "debate", "article": "R. 253-9, 8°", "keywords": ("bilan annuel de l'apprentissage", "bilan apprentissage")},
    {"code": "bilan_ldg", "label": "Bilan de mise en œuvre des LDG", "kind": "debate", "article": "R. 253-9, 9°", "keywords": ("bilan de mise en œuvre des ldg", "bilan d'application des ldg", "bilan ldg")},
    {"code": "bilan_formation", "label": "Bilan annuel du plan de formation", "kind": "debate", "article": "R. 253-9, 10°", "keywords": ("bilan annuel du plan de formation", "bilan du plan de formation")},
    {"code": "emplois_tnc", "label": "Création d'emplois à temps non complet", "kind": "debate", "article": "R. 253-9, 11°", "keywords": ("création d'emplois à temps non complet", "creation d'emplois à temps non complet")},
    {"code": "mise_en_oeuvre_egalite", "label": "Mise en œuvre annuelle du plan d'action pour l'égalité professionnelle", "kind": "information", "article": "R. 253-10, 1°", "keywords": ("mise en œuvre du plan d'action égalité", "mise en oeuvre du plan d'action egalite")},
    {"code": "actualisation_bds", "label": "Actualisation de la base de données sociales", "kind": "information", "article": "R. 253-10, 2°", "keywords": ("base de données sociales", "base de donnees sociales")},
    {"code": "accompagnement_personnalise", "label": "Offre d'accompagnement personnalisé", "kind": "information", "article": "R. 253-10, 3°", "keywords": ("offre d'accompagnement personnalisé", "offre d'accompagnement personnalise")},
    {"code": "credits_formation", "label": "Volume des crédits complémentaires au plan de formation", "kind": "information", "article": "R. 253-10, 4°", "keywords": ("crédits complémentaires au plan de formation", "credits complementaires au plan de formation")},
)

def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def qualify_cst_topic(objet: str, *, formation_specialisee_exists: bool | None = None) -> dict[str, Any]:
    """Return candidate CST categories; never assert legal applicability."""
    normalized = f" {_fold(objet)} "
    matches: list[dict[str, str]] = []
    for rule in CST_TOPIC_RULES:
        matched = next((term for term in rule["keywords"] if f" {_fold(term)} " in normalized), None)
        if matched:
            matches.append({
                "code": rule["code"],
                "label": rule["label"],
                "category": rule["kind"],
                "reference": rule["article"],
                "matched_term": matched,
                "status": "candidate_a_verifier",
            })

    health_topic = any(
        f" {_fold(term)} " in normalized
        for term in ("santé sécurité", "sante securite", "risques professionnels", "conditions de travail", "duerp", "document unique", "accident de service", "risques psychosociaux")
    )
    if health_topic and formation_specialisee_exists is True:
        routing = "formation_specialisee_a_examiner"
        routing_note = "Une formation spécialisée est déclarée existante : vérifier son périmètre et les règles de répartition des compétences avant de saisir le CST."
    elif health_topic and formation_specialisee_exists is False:
        routing = "cst_competence_sante_securite_a_examiner"
        routing_note = "Aucune formation spécialisée n'est déclarée : vérifier les compétences exercées par le CST et les cas particuliers de réunion."
    elif health_topic:
        routing = "indetermine"
        routing_note = "L'existence et le périmètre de la formation spécialisée doivent être précisés avant de déterminer l'instance compétente."
    else:
        routing = "cst_a_examiner"
        routing_note = "Vérifier la compétence du CST au regard du projet et des textes applicables."

    categories = sorted({item["category"] for item in matches})
    return {
        "status": "CANDIDATES_FOUND" if matches else "NO_TOPIC_MATCH",
        "candidates": matches,
        "candidate_categories": categories,
        "health_safety_routing": routing,
        "routing_note": routing_note,
        "formation_specialisee_exists": formation_specialisee_exists,
        "legal_conclusion": False,
        "notice": "Qualification documentaire indicative par mots-clés. Une correspondance ne prouve pas qu'une consultation, un débat ou une information est juridiquement requis : vérifier le contenu exact du projet, son fondement, la collectivité, la date et les textes en vigueur.",
        "official_references": [
            {"article": "CGFP R. 253-7", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054087794"},
            {"article": "CGFP R. 253-8", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549725"},
            {"article": "CGFP R. 253-9", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549727"},
            {"article": "CGFP R. 253-10", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549731"},
            {"article": "CGFP L. 251-9", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000044427304"},
        ],
    }


def calculate_cst_meeting_deadlines(meeting_date: date, *, urgent: bool = False) -> dict[str, Any]:
    """Calculate statutory calendar-date targets from CGFP R. 254-38 and R. 254-39."""
    if not isinstance(meeting_date, date):
        raise TypeError("meeting_date doit être une date.")
    convocation_days = 8 if urgent else 15
    return {
        "meeting_date": meeting_date.isoformat(),
        "urgent": urgent,
        "convocation_minimum_days_before": convocation_days,
        "convocation_target_date": (meeting_date - timedelta(days=convocation_days)).isoformat(),
        "documents_minimum_days_before": 8,
        "documents_target_date": (meeting_date - timedelta(days=8)).isoformat(),
        "references": ["CGFP R. 254-38", "CGFP R. 254-39"],
        "notice": "Dates calculées en jours calendaires par soustraction de dates. Vérifier les règles de computation applicables et les circonstances particulières du dossier ; en urgence, seul le délai de convocation est ramené à huit jours.",
    }
