"""Conservative CST topic qualification against the CGFP in force.

This module identifies documentary candidates from explicit topic terms. It
does not decide whether a concrete project legally requires consultation.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
import calendar
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



def assess_cst_agenda_request(
    *,
    titular_representatives: int | None = None,
    requesting_titular_representatives: int | None = None,
    requested_topic_in_competence: bool | None = None,
) -> dict[str, Any]:
    """Assess the statutory agenda-inclusion threshold under CGFP R. 254-43.

    Competence must be assessed separately; the helper never infers it from
    keywords. Counts refer to titular staff representatives, not all members.
    """
    if titular_representatives is None and requesting_titular_representatives is None:
        return {
            "status": "NOT_ASSESSED",
            "reference": "CGFP R. 254-43",
            "legal_conclusion": False,
            "notice": "Renseigner le nombre total de représentants titulaires du personnel et le nombre de demandeurs.",
        }
    if (
        isinstance(titular_representatives, bool)
        or isinstance(requesting_titular_representatives, bool)
        or not isinstance(titular_representatives, int)
        or not isinstance(requesting_titular_representatives, int)
        or titular_representatives < 1
        or requesting_titular_representatives < 0
        or requesting_titular_representatives > titular_representatives
    ):
        raise ValueError("Les effectifs de représentants titulaires sont invalides.")
    threshold = (titular_representatives + 1) // 2
    reaches_threshold = requesting_titular_representatives >= threshold
    if not reaches_threshold:
        status = "THRESHOLD_NOT_REACHED"
        notice = "Le seuil de la moitié des représentants titulaires n'est pas atteint sur la base des effectifs déclarés."
    elif requested_topic_in_competence is True:
        status = "AGENDA_INCLUSION_REQUIRED"
        notice = "Sous réserve de l'exactitude des effectifs et de la compétence de l'instance, la question doit être inscrite à l'ordre du jour."
    elif requested_topic_in_competence is False:
        status = "COMPETENCE_DISPUTED"
        notice = "Le seuil numérique est atteint, mais la question doit relever de la compétence du CST ou de la formation spécialisée pour bénéficier de l'inscription obligatoire."
    else:
        status = "COMPETENCE_TO_VERIFY"
        notice = "Le seuil numérique est atteint. Vérifier la compétence du CST ou de la formation spécialisée avant de conclure à l'inscription obligatoire."
    return {
        "status": status,
        "reference": "CGFP R. 254-43",
        "titular_representatives": titular_representatives,
        "requesting_titular_representatives": requesting_titular_representatives,
        "minimum_requesters": threshold,
        "requested_topic_in_competence": requested_topic_in_competence,
        "legal_conclusion": False,
        "notice": notice,
    }


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def assess_fs_nine_month_trigger(
    *,
    last_meeting_date: date,
    as_of_date: date,
    titular_representatives: int,
    requesting_titular_representatives: int,
) -> dict[str, Any]:
    """Assess the R. 254-42 nine-month trigger and R. 254-35 request threshold."""
    if not isinstance(last_meeting_date, date) or not isinstance(as_of_date, date):
        raise TypeError("Les dates doivent être des objets date.")
    if last_meeting_date > as_of_date:
        raise ValueError("La dernière réunion ne peut pas être postérieure à la date d'évaluation.")
    if (
        isinstance(titular_representatives, bool)
        or isinstance(requesting_titular_representatives, bool)
        or not isinstance(titular_representatives, int)
        or not isinstance(requesting_titular_representatives, int)
        or titular_representatives < 1
        or requesting_titular_representatives < 0
        or requesting_titular_representatives > titular_representatives
    ):
        raise ValueError("Les effectifs de représentants titulaires sont invalides.")
    threshold_date = _add_months(last_meeting_date, 9)
    threshold_reached = as_of_date >= threshold_date
    minimum_requesters = (titular_representatives + 1) // 2
    request_threshold_reached = requesting_titular_representatives >= minimum_requesters
    eligible = threshold_reached and request_threshold_reached
    if not threshold_reached:
        status = "NINE_MONTHS_NOT_REACHED"
    elif not request_threshold_reached:
        status = "REQUEST_THRESHOLD_NOT_REACHED"
    else:
        status = "INSPECTOR_REFERRAL_POSSIBLE"
    return {
        "status": status,
        "last_meeting_date": last_meeting_date.isoformat(),
        "as_of_date": as_of_date.isoformat(),
        "nine_month_threshold_date": threshold_date.isoformat(),
        "nine_month_period_reached": threshold_reached,
        "titular_representatives": titular_representatives,
        "requesting_titular_representatives": requesting_titular_representatives,
        "minimum_requesters": minimum_requesters,
        "request_threshold_reached": request_threshold_reached,
        "inspector_referral_possible": eligible,
        "reference": "CGFP R. 254-42 et R. 254-35",
        "legal_conclusion": False,
        "notice": (
            "Le délai d'au moins neuf mois et le seuil de demande sont atteints sur la base des dates et effectifs déclarés. "
            "Les représentants titulaires peuvent envisager de saisir l'agent chargé des fonctions d'inspection ; vérifier "
            "la réalité de la dernière réunion, la qualité des demandeurs et les conditions du dossier."
            if eligible else
            "Les conditions cumulatives de l'article R. 254-42 ne sont pas toutes réunies sur la base des données déclarées."
        ),
    }


def calculate_fs_inspector_request_deadlines(received_date: date) -> dict[str, Any]:
    """Calculate R. 254-42 outer deadlines after the inspector's request is received."""
    if not isinstance(received_date, date):
        raise TypeError("received_date doit être une date.")
    return {
        "inspector_request_received_date": received_date.isoformat(),
        "authority_convocation_deadline": (received_date + timedelta(days=8)).isoformat(),
        "meeting_deadline": _add_months(received_date, 1).isoformat(),
        "reference": "CGFP R. 254-42",
        "legal_conclusion": False,
        "notice": "Délais calculés à compter de la réception de la demande de l'agent chargé des fonctions d'inspection. Vérifier la date de réception et les circonstances particulières.",
    }


def assess_annual_instance_meeting_frequency(
    *,
    instance: str,
    meetings_held: int,
    formation_specialisee_exists: bool | None = None,
    health_safety_meetings_held: int = 0,
) -> dict[str, Any]:
    """Compare declared annual meeting counts with CGFP R. 254-35 to R. 254-37."""
    normalized = instance.strip().upper() if isinstance(instance, str) else ""
    if normalized not in {"CST", "FS"}:
        raise ValueError("instance doit être CST ou FS.")
    for value in (meetings_held, health_safety_meetings_held):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Les nombres de réunions doivent être des entiers positifs ou nuls.")
    if normalized == "FS":
        required = 3
        return {
            "instance": "FS",
            "minimum_annual_meetings": required,
            "meetings_held": meetings_held,
            "minimum_reached": meetings_held >= required,
            "status": "MINIMUM_REACHED" if meetings_held >= required else "MINIMUM_NOT_YET_REACHED",
            "legal_conclusion": False,
            "reference": "CGFP R. 254-37",
            "notice": "La formation spécialisée du CST se réunit au moins trois fois par an. Le décompte doit être vérifié sur l'année concernée.",
        }
    if formation_specialisee_exists is None:
        return {
            "instance": "CST",
            "status": "FS_EXISTENCE_TO_VERIFY",
            "legal_conclusion": False,
            "reference": "CGFP R. 254-35 et R. 254-36",
            "notice": "Préciser si une formation spécialisée existe pour déterminer si la réunion annuelle supplémentaire consacrée à la santé, à la sécurité et aux conditions de travail s'applique.",
        }
    base_required = 2
    extra_health_required = 0 if formation_specialisee_exists else 1
    total_required = base_required + extra_health_required
    base_met = meetings_held >= base_required
    health_met = extra_health_required == 0 or health_safety_meetings_held >= extra_health_required
    total_met = meetings_held >= total_required
    return {
        "instance": "CST",
        "minimum_annual_meetings": total_required,
        "base_minimum_annual_meetings": base_required,
        "meetings_held": meetings_held,
        "base_minimum_reached": base_met,
        "additional_health_safety_meetings_required": extra_health_required,
        "health_safety_meetings_held": health_safety_meetings_held,
        "health_safety_minimum_reached": health_met,
        "minimum_reached": base_met and total_met and health_met,
        "status": "MINIMUM_REACHED" if base_met and total_met and health_met else "MINIMUM_NOT_YET_REACHED",
        "legal_conclusion": False,
        "reference": "CGFP R. 254-35 et R. 254-36",
        "notice": "Le CST se réunit au moins deux fois par an. En l'absence de formation spécialisée, il tient en outre au moins une réunion annuelle portant sur la santé, la sécurité et les conditions de travail, hors exceptions prévues par le texte.",
    }


def calculate_cst_written_request_deadline(
    *,
    received_date: date,
    titular_representatives: int,
    requesting_titular_representatives: int,
) -> dict[str, Any]:
    """Calculate the two-month meeting deadline when half of titular reps request in writing."""
    if not isinstance(received_date, date):
        raise TypeError("received_date doit être une date.")
    if (
        isinstance(titular_representatives, bool)
        or isinstance(requesting_titular_representatives, bool)
        or not isinstance(titular_representatives, int)
        or not isinstance(requesting_titular_representatives, int)
        or titular_representatives < 1
        or requesting_titular_representatives < 0
        or requesting_titular_representatives > titular_representatives
    ):
        raise ValueError("Les effectifs de représentants titulaires sont invalides.")
    minimum = (titular_representatives + 1) // 2
    reached = requesting_titular_representatives >= minimum
    return {
        "written_request_received_date": received_date.isoformat(),
        "minimum_requesters": minimum,
        "requesting_titular_representatives": requesting_titular_representatives,
        "deadline_date": _add_months(received_date, 2).isoformat() if reached else None,
        "status": "MEETING_WITHIN_TWO_MONTHS_REQUIRED" if reached else "REQUEST_THRESHOLD_NOT_REACHED",
        "reference": "CGFP R. 254-35",
        "legal_conclusion": False,
        "notice": "Si la demande écrite émane d'au moins la moitié des représentants titulaires, le CST doit se réunir dans le délai de deux mois. Vérifier la réception de la demande, la qualité des signataires et les effectifs.",
    }


FS_TOPIC_RULES: tuple[dict[str, Any], ...] = (
    {"code": "fs_health_hygiene_safety", "label": "Protection de la santé physique et mentale, hygiène et sécurité au travail", "article": "R. 253-24, 1°", "keywords": ("santé physique et mentale", "hygiène et sécurité", "hygiene et securite", "sécurité des agents au travail", "securite des agents au travail")},
    {"code": "fs_work_organization", "label": "Organisation du travail", "article": "R. 253-24, 2°", "keywords": ("organisation du travail",)},
    {"code": "fs_telework", "label": "Télétravail", "article": "R. 253-24, 3°", "keywords": ("télétravail", "teletravail")},
    {"code": "fs_disconnection", "label": "Déconnexion et régulation des outils numériques", "article": "R. 253-24, 4°", "keywords": ("droit à la déconnexion", "droit a la deconnexion", "régulation des outils numériques", "regulation des outils numeriques")},
    {"code": "fs_work_conditions", "label": "Amélioration des conditions de travail", "article": "R. 253-24, 5°", "keywords": ("amélioration des conditions de travail", "amelioration des conditions de travail")},
    {"code": "fs_duerp", "label": "Élaboration ou mise à jour du document unique d'évaluation des risques professionnels", "article": "R. 253-24, 6°", "keywords": ("document unique d'évaluation des risques", "document unique d evaluation des risques", "duerp")},
    {"code": "fs_major_work_changes", "label": "Projet important modifiant santé, sécurité ou conditions de travail", "article": "R. 253-25, 1°", "keywords": ("transformation importante des postes", "modification de l'outillage", "changement de produit", "modification importante de l'organisation du travail", "modification du temps de travail", "modification des cadences", "cadences de travail", "normes de productivité", "normes de productivite")},
    {"code": "fs_new_technology", "label": "Projet important d'introduction de nouvelles technologies susceptible d'affecter santé ou sécurité", "article": "R. 253-25, 2°", "keywords": ("introduction de nouvelles technologies", "nouvelle technologie susceptible")},
    {"code": "fs_return_to_work", "label": "Mesures de mise, remise ou maintien au travail après accident, invalidité ou handicap", "article": "R. 253-26", "keywords": ("maintien au travail après accident", "maintien au travail apres accident", "aménagement de poste pour handicap", "amenagement de poste pour handicap", "retour au travail après accident", "retour au travail apres accident")},
    {"code": "fs_incapacity_redeployment", "label": "Mesures générales de reclassement des agents reconnus inaptes", "article": "R. 253-26", "keywords": ("reclassement des agents inaptes", "agents reconnus inaptes")},
    {"code": "fs_annual_prevention_program", "label": "Programme annuel de prévention des risques professionnels et d'amélioration des conditions de travail", "article": "R. 253-27", "keywords": ("programme annuel de prévention", "programme annuel de prevention", "papripact")},
)


def qualify_fs_topic(objet: str) -> dict[str, Any]:
    """Return candidate FPT specialized-committee consultation topics, not conclusions."""
    normalized = f" {_fold(objet)} "
    candidates = []
    for rule in FS_TOPIC_RULES:
        matched = next((term for term in rule["keywords"] if f" {_fold(term)} " in normalized), None)
        if matched:
            candidates.append({
                "code": rule["code"],
                "label": rule["label"],
                "reference": rule["article"],
                "matched_term": matched,
                "status": "candidate_a_verifier",
            })
    return {
        "status": "CANDIDATES_FOUND" if candidates else "NO_TOPIC_MATCH",
        "candidates": candidates,
        "legal_conclusion": False,
        "notice": "Pistes de consultation FS à vérifier au regard du contenu exact du projet, de l'existence et du périmètre de la FS, des exclusions des articles R. 253-24 et R. 253-25 et de l'articulation prévue aux articles R. 253-79 à R. 253-81.",
        "official_references": [
            {"article": "CGFP R. 253-24", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549777"},
            {"article": "CGFP R. 253-25", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549779"},
            {"article": "CGFP R. 253-26", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549781"},
            {"article": "CGFP R. 253-27", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549783"},
        ],
    }


def assess_cst_fs_competence_routing(
    *,
    formation_specialisee_exists: bool | None,
    topic_in_cst_own_competence: bool | None = None,
    topic_in_fs_mandatory_consultation: bool | None = None,
    fs_consultation_already_examined: bool | None = None,
    cst_evocation_initiative: str | None = None,
    cst_staff_representatives_total: int | None = None,
    cst_staff_representatives_supporting: int | None = None,
) -> dict[str, Any]:
    """Apply the high-level FPT articulation safeguards in CGFP R. 253-79 to R. 253-81."""
    base = {
        "legal_conclusion": False,
        "references": ["CGFP R. 253-79", "CGFP R. 253-80", "CGFP R. 253-81"],
        "official_references": [
            {"article": "CGFP R. 253-79", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549927"},
            {"article": "CGFP R. 253-80", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051968704"},
            {"article": "CGFP R. 253-81", "url": "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549931"},
        ],
    }
    if formation_specialisee_exists is None:
        return {**base, "status": "FS_EXISTENCE_TO_VERIFY", "notice": "Préciser si une formation spécialisée a été instituée et vérifier son périmètre avant de répartir les compétences."}
    if formation_specialisee_exists is False:
        return {**base, "status": "CST_EXERCISES_FS_COMPETENCES", "notice": "En l'absence de formation spécialisée instituée, le CST exerce les compétences attribuées à la formation spécialisée par les sous-sections 1 à 4 de la section 2 du chapitre III du titre V du livre II du CGFP."}
    if topic_in_cst_own_competence is True and topic_in_fs_mandatory_consultation is True:
        return {**base, "status": "CST_SOLELY_CONSULTED", "notice": "Lorsque la question ou le projet relève des attributions propres du CST et pourrait aussi relever de la FS, le CST est seul consulté. Vérifier précisément le champ de chaque attribution."}
    if topic_in_cst_own_competence is None or topic_in_fs_mandatory_consultation is None:
        return {**base, "status": "COMPETENCE_TO_VERIFY", "notice": "Qualifier séparément les attributions propres du CST et les consultations obligatoires de la FS avant de choisir l'instance."}
    if topic_in_fs_mandatory_consultation is False:
        return {**base, "status": "CST_COMPETENCE_TO_EXAMINE" if topic_in_cst_own_competence else "NO_AUTOMATIC_INSTANCE_ROUTING", "notice": "Aucune consultation obligatoire de la FS n'est déclarée. Vérifier les autres compétences et textes applicables."}
    if fs_consultation_already_examined is None:
        return {**base, "status": "FS_EXAMINATION_STATUS_TO_VERIFY", "notice": "Vérifier si la consultation obligatoire de la FS a déjà été examinée avant d'envisager la procédure de substitution."}
    if fs_consultation_already_examined is True:
        return {**base, "status": "FS_ALREADY_EXAMINED", "notice": "La consultation FS est déclarée déjà examinée ; le mécanisme de substitution de R. 253-81 vise une question qui n'a pas encore été examinée par la FS."}
    if cst_evocation_initiative not in {"PRESIDENT", "STAFF_REPRESENTATIVES"}:
        return {**base, "status": "FS_MANDATORY_CONSULTATION_TO_EXAMINE", "notice": "La consultation obligatoire relève en principe de la FS. Le CST ne peut se substituer à elle que dans les conditions de R. 253-81."}
    if (
        isinstance(cst_staff_representatives_total, bool)
        or isinstance(cst_staff_representatives_supporting, bool)
        or not isinstance(cst_staff_representatives_total, int)
        or not isinstance(cst_staff_representatives_supporting, int)
        or cst_staff_representatives_total < 1
        or cst_staff_representatives_supporting < 0
        or cst_staff_representatives_supporting > cst_staff_representatives_total
    ):
        raise ValueError("Les effectifs de représentants du personnel au CST sont invalides.")
    minimum = (cst_staff_representatives_total + 1) // 2
    threshold_met = cst_staff_representatives_supporting >= minimum
    if not threshold_met:
        return {**base, "status": "EVOCATION_THRESHOLD_NOT_REACHED", "minimum_supporting_representatives": minimum, "notice": "Le seuil de la moitié des membres représentants du personnel n'est pas atteint sur la base des effectifs déclarés."}
    return {
        **base,
        "status": "CST_OPINION_SUBSTITUTES_FS",
        "minimum_supporting_representatives": minimum,
        "initiative": cst_evocation_initiative,
        "notice": "Sous réserve des conditions de R. 253-81, le CST peut examiner directement la question non encore examinée par la FS ; son avis se substitue alors à celui de la FS. Pour une initiative du président, vérifier l'accord de la moitié des membres représentants du personnel.",
    }


FS_OPERATIONAL_RULES: tuple[dict[str, Any], ...] = (
    {
        "code": "annual_health_safety_report_program",
        "label": "Rapport annuel santé-sécurité et programme annuel de prévention",
        "reference": "CGFP R. 253-30",
        "keywords": ("rapport annuel santé sécurité", "rapport annuel santé-sécurité", "programme annuel de prévention", "papripact", "programme de prévention", "bilan annuel santé sécurité"),
        "actions": (
            "Vérifier que la formation spécialisée est saisie chaque année pour avis sur le rapport annuel écrit relatif à la situation générale santé-sécurité-conditions de travail et aux actions menées.",
            "Vérifier que le programme annuel est établi à partir de l'analyse du rapport social unique et comporte les actions, leurs conditions d'exécution et leur coût estimé.",
            "Tracer les propositions éventuelles de priorisation et de mesures supplémentaires formulées par la formation spécialisée.",
            "Vérifier que les motifs des mesures de prévention non réalisées figurent en annexe du rapport annuel.",
            "Vérifier l'association de la formation spécialisée au suivi du document unique d'évaluation des risques professionnels.",
        ),
    },
    {
        "code": "health_safety_register",
        "label": "Observations consignées au registre santé et sécurité au travail",
        "reference": "CGFP R. 253-35",
        "keywords": ("registre santé et sécurité au travail", "registre santé sécurité au travail", "registre santé-sécurité au travail", "registre ssct", "observations du registre santé"),
        "actions": (
            "Recueillir les observations et suggestions relatives à la prévention des risques professionnels et à l'amélioration des conditions de travail.",
            "Vérifier que la formation spécialisée en prend connaissance.",
            "Regrouper les observations par service, risque, exposition et date sans effacer les signalements individuels.",
            "Demander quelles suites ont été données, quelles mesures restent en attente et pour quels motifs.",
            "Ne pas confondre ce registre avec le registre spécial de danger grave et imminent.",
        ),
    },
    {
        "code": "visit_report_followup",
        "label": "Rapport de visite et suivi des suites",
        "reference": "CGFP R. 253-47",
        "keywords": ("rapport de visite", "suite de visite de service", "suivi des recommandations de visite", "recommandations de la formation spécialisée"),
        "actions": (
            "Vérifier que le rapport de la délégation a été présenté à la formation spécialisée.",
            "Pour chaque constat, consigner le risque, le service ou poste concerné, les mesures proposées et le responsable de la réponse.",
            "Demander la position de l'autorité territoriale, les mesures retenues, leur échéance annoncée et les motifs des mesures non retenues.",
            "Inscrire les points non résolus à l'ordre du jour d'une séance ultérieure lorsque cela relève des règles de fonctionnement de l'instance.",
            "Distinguer les recommandations de la délégation, l'avis de la formation spécialisée et la décision de l'autorité territoriale.",
        ),
    },
    {
        "code": "investigation_conclusion_followup",
        "label": "Conclusions d'enquête et suites réservées",
        "reference": "CGFP R. 253-52",
        "keywords": ("conclusions de l'enquête", "suites de l'enquête", "suivi enquête accident", "suivi enquête maladie professionnelle"),
        "actions": (
            "Vérifier que la formation spécialisée est informée des conclusions de chaque enquête.",
            "Obtenir la traçabilité des suites réservées aux conclusions : mesures décidées, responsables, échéances et état d'avancement communiqué.",
            "Identifier les recommandations restées sans suite et demander les motifs ou mesures alternatives.",
            "Ne pas confondre l'information obligatoire de la formation spécialisée avec un pouvoir de décision attribué à celle-ci.",
        ),
    },
    {
        "code": "risk_analysis_prevention",
        "label": "Analyse des risques et prévention",
        "reference": "CGFP R. 253-37 à R. 253-40",
        "keywords": ("analyse des risques professionnels", "risques professionnels", "prévention des risques", "harcèlement moral", "harcèlement sexuel", "violences sexistes et sexuelles"),
        "actions": (
            "Décrire les risques et les agents ou postes exposés, y compris les expositions particulières.",
            "Identifier les mesures de prévention déjà prises, leur suivi et les actions complémentaires proposées.",
            "Pour une FS créée en raison de risques particuliers, vérifier que l'analyse initiale de ces risques et le périmètre du site ou service ont été établis.",
        ),
    },
    {
        "code": "service_visit",
        "label": "Visite de service par une délégation",
        "reference": "CGFP R. 253-41 à R. 253-47",
        "keywords": ("visite de service", "visite de site", "visite des locaux", "visite de la formation spécialisée", "visite fs"),
        "actions": (
            "Vérifier la délibération fixant l'objet, le secteur géographique et la composition de la délégation.",
            "Vérifier que la délégation comprend le président ou son représentant et des représentants du personnel membres de la FS.",
            "Prévoir les conditions d'accès aux locaux et les éventuelles restrictions réglementaires d'accès.",
            "Pour une visite au domicile d'un agent en télétravail, recueillir son accord écrit préalable.",
            "Formaliser un rapport présenté à la formation spécialisée.",
        ),
    },
    {
        "code": "serious_accident",
        "label": "Accident ayant entraîné ou pouvant entraîner des conséquences graves",
        "reference": "CGFP R. 253-48",
        "keywords": ("accident grave", "accident ayant pu entraîner des conséquences graves", "accident aux conséquences graves"),
        "actions": (
            "Vérifier si l'accident a entraîné ou aurait pu entraîner des conséquences graves.",
            "Préparer la réunion de la formation spécialisée compétente dans les plus brefs délais.",
            "Conserver les éléments factuels utiles et distinguer cette réunion de l'enquête formalisée prévue à R. 253-49.",
        ),
    },
    {
        "code": "mandatory_investigation",
        "label": "Enquête de la formation spécialisée",
        "reference": "CGFP R. 253-49 à R. 253-52",
        "keywords": ("accidents répétés", "accident répété", "maladie professionnelle grave", "incapacité permanente", "enquête après accident", "enquête de la formation spécialisée"),
        "actions": (
            "Vérifier le caractère grave, le risque révélé et, pour les situations répétées, l'identité ou la similarité des postes ou fonctions concernés.",
            "Vérifier la composition de la délégation : président ou représentant et au moins un représentant du personnel de la FS.",
            "Identifier les personnes ressources pouvant participer dans les conditions du texte.",
            "Demander communication des conclusions de l'enquête et des suites réservées à la FS.",
        ),
    },
    {
        "code": "neighbor_nuisance",
        "label": "Nuisances provenant d'un établissement voisin",
        "reference": "CGFP R. 253-53",
        "keywords": ("nuisances établissement voisin", "nuisances d'un établissement voisin", "nuisances provenant d'un établissement voisin"),
        "actions": (
            "Décrire les nuisances particulières et leur exposition pour les agents du ressort de la FS.",
            "Examiner la demande d'audition ou d'observations de l'employeur voisin par l'intermédiaire de l'autorité territoriale.",
            "Suivre les suites réservées aux observations de la FS.",
        ),
    },
    {
        "code": "certified_expert",
        "label": "Recours à un expert certifié",
        "reference": "CGFP R. 253-54 à R. 253-57",
        "keywords": ("expert certifié", "expertise risque grave", "recours à un expert", "recours a un expert"),
        "actions": (
            "Vérifier l'un des cas légaux : risque grave, révélé ou non par un accident ou une maladie professionnelle, ou projet important modifiant santé, sécurité ou conditions de travail hors réorganisation de service.",
            "Vérifier que la FS ne dispose pas des éléments nécessaires à l'évaluation.",
            "Tracer l'initiative du président ou la délibération de la FS et la décision motivée en cas de refus.",
            "Pour la FPT, vérifier le délai maximal d'un mois prévu lorsque l'expertise est demandée par le président.",
            "En cas de désaccord sérieux et persistant, examiner la procédure spécifique de R. 253-57 et son articulation avec R. 253-62.",
        ),
    },
    {
        "code": "serious_imminent_danger",
        "label": "Alerte en cas de danger grave et imminent",
        "reference": "CGFP R. 253-58 à R. 253-60 et R. 253-62 à R. 253-63",
        "keywords": ("danger grave et imminent", "dgi", "registre spécial danger grave"),
        "actions": (
            "Alerter immédiatement l'autorité territoriale ou son représentant.",
            "Consigner l'avis dans le registre spécial dédié au danger grave et imminent ; ne pas le confondre avec le registre santé et sécurité au travail.",
            "Vérifier que l'inscription est datée, signée et identifie les postes, la nature et la cause du danger ainsi que les personnes exposées.",
            "L'autorité territoriale doit mener immédiatement une enquête avec le représentant de la FS et prendre les mesures nécessaires.",
            "En cas de divergence sur le danger ou les moyens de le faire cesser, la FS compétente est réunie en urgence dans un délai maximal de 24 heures ; l'inspecteur du travail est informé et peut assister.",
            "En FPT, en l'absence d'accord après intervention de l'agent chargé des fonctions d'inspection, l'inspecteur du travail est obligatoirement saisi ; vérifier le rapport et la réponse motivée sous quinze jours.",
        ),
    },
)

FS_OPERATIONAL_REFERENCES = [
    {"article": "CGFP R. 253-35 à R. 253-63", "url": "https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000044416551/LEGISCTA000050549693/2026-08-01/"},
]


def qualify_fs_operational_topic(
    objet: str,
    *,
    formation_specialisee_exists: bool | None = True,
) -> dict[str, Any]:
    """Identify FS operational-procedure candidates without deciding applicability."""
    normalized = f" {_fold(objet)} "
    candidates: list[dict[str, Any]] = []
    for rule in FS_OPERATIONAL_RULES:
        matched = next(
            (term for term in rule["keywords"] if f" {_fold(term)} " in normalized),
            None,
        )
        if matched:
            candidates.append({
                "code": rule["code"],
                "label": rule["label"],
                "reference": rule["reference"],
                "matched_term": matched,
                "actions_to_check": list(rule["actions"]),
                "status": "candidate_a_verifier",
            })

    if formation_specialisee_exists is False:
        routing = "CST_SANS_FS_A_EXAMINER"
        routing_note = (
            "Aucune formation spécialisée n'est déclarée. Vérifier les compétences exercées par le CST "
            "en l'absence de FS et les dispositions qui visent expressément la délégation du CST."
        )
    elif formation_specialisee_exists is None:
        routing = "INSTANCE_INDETERMINEE"
        routing_note = "L'existence et le périmètre de la formation spécialisée doivent être établis."
    else:
        routing = "FS_A_EXAMINER"
        routing_note = "Vérifier l'existence, le périmètre et la compétence de la formation spécialisée concernée."

    return {
        "status": "CANDIDATES_FOUND" if candidates else "NO_OPERATIONAL_TRIGGER",
        "candidates": candidates,
        "instance_routing": routing,
        "routing_note": routing_note,
        "formation_specialisee_exists": formation_specialisee_exists,
        "legal_conclusion": False,
        "notice": (
            "Repérage lexical d'une procédure possible, non constat de sa réunion des conditions légales. "
            "Vérifier les faits, le périmètre de la FS, le versant, les textes en vigueur et les pièces du dossier. "
            "Les délais d'urgence ne doivent jamais être traités comme un simple calendrier prévisionnel."
        ),
        "official_references": FS_OPERATIONAL_REFERENCES,
    }
