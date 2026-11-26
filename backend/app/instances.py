"""Structured preparation aids for FPT social-dialogue bodies.

This module produces working checklists only. It does not determine legal
competence, mandatory consultation, procedural legality, or statutory deadlines.
All legal conclusions must be established separately from current official sources.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date
import unicodedata
from typing import Any


INSTANCE_RULES: dict[str, dict[str, dict[str, Any]]] = {
    "CST": {
        "organisation_travail": {
            "label": "Organisation et conditions de travail",
            "keywords": ("organisation du travail", "temps de travail", "cycle de travail", "horaires", "astreinte", "télétravail"),
            "questions": (
                "Quel est l'objet précis du projet et quelle décision l'autorité envisage-t-elle de prendre ?",
                "Quels agents et quels services sont concernés, et quelles différences de situation existent ?",
                "Quels effets sont attendus sur les conditions de travail, les horaires et la charge de travail ?",
                "Quelles alternatives ont été étudiées et comment les agents ont-ils été associés ?",
            ),
            "documents": ("Projet soumis à consultation et note de présentation", "Étude d'impact sur les services et les agents", "Avis et bilans antérieurs pertinents"),
        },
        "formation": {
            "label": "Formation professionnelle",
            "keywords": ("plan de formation", "formation professionnelle", "formation des agents"),
            "questions": (
                "Comment les besoins de formation ont-ils été recensés ?",
                "Quels agents ou métiers risquent de rester à l'écart des actions prévues ?",
                "Quel bilan quantitatif et qualitatif peut être présenté ?",
            ),
            "documents": ("Projet de plan et bilan du plan précédent", "Données de départ en formation ventilées par service et catégorie", "Budget et calendrier prévisionnels"),
        },
        "ldg": {
            "label": "Lignes directrices de gestion",
            "keywords": ("lignes directrices de gestion", "ldg"),
            "questions": (
                "Quelle version des lignes directrices est soumise et quelle période couvre-t-elle ?",
                "Quels critères sont proposés et comment leur application sera-t-elle tracée ?",
                "Comment les agents seront-ils informés des critères et des décisions individuelles ?",
            ),
            "documents": ("Projet intégral des lignes directrices de gestion", "Bilan d'application et données anonymisées", "Note exposant les critères et leur méthode de pondération"),
        },
        "reglement": {
            "label": "Règlement intérieur ou règlement de service",
            "keywords": ("règlement intérieur", "règlement de service"),
            "questions": (
                "Quelles dispositions nouvelles ou modifiées sont proposées ?",
                "Quels textes et décisions internes fondent chaque disposition ?",
                "Comment les agents seront-ils informés et comment les observations seront-elles recueillies ?",
            ),
            "documents": ("Projet intégral avec suivi des modifications", "Note de présentation et références invoquées", "Version actuellement applicable"),
        },
    },
    "CAP": {
        "discipline": {
            "label": "Situation disciplinaire d'un fonctionnaire",
            "keywords": ("discipline", "disciplinaire", "sanction", "blâme", "révocation", "exclusion temporaire", "conseil de discipline"),
            "questions": (
                "Quelle sanction est envisagée et quelle est la situation statutaire exacte de l'agent ?",
                "Quels faits précis sont reprochés, à quelles dates et sur quelles pièces l'administration s'appuie-t-elle ?",
                "L'agent a-t-il eu accès à l'intégralité des pièces et pu préparer sa défense ?",
                "Les circonstances, l'ancienneté, les antécédents et la proportionnalité sont-ils examinés ?",
            ),
            "documents": ("Rapport disciplinaire et pièces invoquées", "Convocation et preuve de communication du dossier", "État des services et éléments utiles à la défense"),
        },
        "entretien": {
            "label": "Compte rendu d'entretien professionnel",
            "keywords": ("entretien professionnel", "compte rendu d'entretien", "révision du compte rendu"),
            "questions": (
                "Quelle date de notification du compte rendu peut être justifiée ?",
                "Un recours hiérarchique préalable a-t-il été formé et quelle réponse a été notifiée ?",
                "Quels éléments factuels précis sont contestés et quelles pièces les contredisent ?",
            ),
            "documents": ("Compte rendu notifié et preuve de notification", "Demande de révision et réponse hiérarchique", "Éléments objectifs relatifs aux objectifs et résultats"),
        },
        "titularisation": {
            "label": "Titularisation ou insuffisance professionnelle",
            "keywords": ("refus de titularisation", "titularisation", "insuffisance professionnelle"),
            "questions": (
                "Quel est le statut de l'agent, son cadre d'emplois et le stade exact de son parcours ?",
                "Quels faits et évaluations motivent le projet de décision ?",
                "Quelles garanties procédurales et quelles consultations sont applicables à cette situation précise ?",
            ),
            "documents": ("Arrêtés de nomination et de prolongation de stage", "Rapports de stage et évaluations", "Projet de décision et pièces communiquées à l'agent"),
        },
    },
    "CCP": {
        "fin_contrat": {
            "label": "Fin ou non-renouvellement de contrat",
            "keywords": ("non-renouvellement", "fin de contrat", "terme du contrat", "renouvellement de contrat"),
            "questions": (
                "Quelle est la nature du contrat, son fondement légal, sa durée et ses éventuels renouvellements ?",
                "Quelle décision a été prise ou annoncée, par quelle autorité et à quelle date ?",
                "Quel motif est communiqué et quelles pièces l'étayent ?",
                "La situation relève-t-elle d'un cas de consultation obligatoire de la CCP ? À vérifier sur les textes applicables.",
            ),
            "documents": ("Contrat initial et avenants", "Courrier de décision et preuve de notification", "Éléments exposant le motif et la situation de l'emploi"),
        },
        "licenciement": {
            "label": "Licenciement d'un agent contractuel",
            "keywords": ("licenciement", "licenciement pour insuffisance", "suppression d'emploi"),
            "questions": (
                "Quel motif légal précis est invoqué et quelle est la nature du contrat ?",
                "Quelles étapes préalables, possibilités de reclassement ou garanties doivent être vérifiées ?",
                "La CCP doit-elle être consultée dans ce cas particulier ?",
            ),
            "documents": ("Contrat et avenants", "Rapport motivant le licenciement", "Propositions de reclassement ou éléments établissant leur impossibilité", "Convocations et preuves de notification"),
        },
        "discipline": {
            "label": "Discipline d'un agent contractuel",
            "keywords": ("disciplinaire", "sanction", "avertissement", "blâme", "exclusion temporaire"),
            "questions": (
                "Quelle sanction est envisagée et quel texte régit la situation de l'agent ?",
                "Quels faits sont établis et quelles pièces sont communiquées ?",
                "La consultation de la CCP est-elle requise pour la sanction envisagée ?",
            ),
            "documents": ("Rapport disciplinaire et pièces", "Convocation et preuve de communication du dossier", "Projet de décision et éléments relatifs à la proportionnalité"),
        },
    },
    "FS": {
        "risques": {
            "label": "Santé, sécurité et prévention des risques",
            "keywords": ("santé sécurité", "conditions de travail", "risques professionnels", "prévention", "duerp", "document unique"),
            "questions": (
                "Quels risques précis sont identifiés, pour quels agents et dans quelles situations de travail ?",
                "Quelle évaluation figure au DUERP et à quelle date a-t-elle été actualisée ?",
                "Quelles mesures de prévention ont été décidées, financées et effectivement mises en œuvre ?",
                "Comment les représentants du personnel et les agents concernés ont-ils été associés ?",
            ),
            "documents": ("DUERP et programme annuel de prévention", "Registres et rapports pertinents", "Plan d'action, responsables désignés et échéances", "Données anonymisées d'accidents et d'absentéisme utiles"),
        },
        "accident": {
            "label": "Accident de service, incident ou agression",
            "keywords": ("accident de service", "accident du travail", "incident", "agression", "presque accident"),
            "questions": (
                "Quels faits, date, lieu et circonstances sont établis ?",
                "Une analyse des causes et des facteurs organisationnels a-t-elle été conduite ?",
                "Quelles mesures immédiates et durables ont été prises pour éviter la répétition ?",
                "Les suites données aux alertes et recommandations antérieures sont-elles documentées ?",
            ),
            "documents": ("Déclaration et rapport d'accident expurgés des données non nécessaires", "Compte rendu d'enquête et analyse des causes", "Mesures correctives et suivi de leur réalisation"),
        },
        "rps": {
            "label": "Risques psychosociaux et charge de travail",
            "keywords": ("risques psychosociaux", "rps", "charge de travail", "surcharge", "sous-effectif", "épuisement", "violence au travail"),
            "questions": (
                "Quels facteurs organisationnels sont documentés et sur quelle période ?",
                "Comment les effectifs, la charge, les horaires et les changements organisationnels sont-ils évalués ?",
                "Quelles mesures collectives de prévention primaire sont prévues ?",
                "Comment leur efficacité sera-t-elle évaluée avec les agents concernés ?",
            ),
            "documents": ("Évaluation des risques psychosociaux", "Données anonymisées d'effectifs, absentéisme et accidents", "Plan de prévention et indicateurs de suivi"),
        },
    },
}


def _fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def prepare_instance(instance: str, objet: str) -> dict[str, Any]:
    """Build a non-authoritative preparation checklist for one FPT instance."""
    key = str(instance or "").strip().upper()
    if key not in INSTANCE_RULES:
        raise ValueError("Instance inconnue. Valeurs admises : CST, CAP, CCP, FS.")
    if not isinstance(objet, str) or not objet.strip():
        raise ValueError("Décrivez l'objet ou la situation à préparer.")
    if len(objet) > 12000:
        raise ValueError("Le texte transmis ne doit pas dépasser 12 000 caractères.")

    normalized = f" {_fold(objet)} "
    points = []
    documents = []
    for rule_key, rule in INSTANCE_RULES[key].items():
        if any(f" {_fold(word)} " in normalized for word in rule["keywords"]):
            points.append({
                "code": rule_key,
                "libelle": rule["label"],
                "questions": list(rule["questions"]),
                "documents": list(rule["documents"]),
                "qualification": "piste_de_preparation_a_confirmer",
            })
            documents.extend(rule["documents"])

    return {
        "instance": key,
        "objet": objet.strip(),
        "points": points,
        "documents_a_demander": list(dict.fromkeys(documents)),
        "legal_conclusion": False,
        "notice": (
            "Cette fiche est une aide à la préparation syndicale fondée sur des "
            "déclencheurs lexicaux. Elle ne confirme ni la compétence de l'instance, "
            "ni une consultation obligatoire, ni la régularité d'une procédure. "
            "Les faits, le statut de l'agent, les textes en vigueur et les délais "
            "doivent être vérifiés avant toute utilisation."
        ),
    }


# One bounded search per official source family. These are discovery queries,
# not a statement that every returned provision applies to the case.
_INSTANCE_LEGAL_PROFILES: dict[str, dict[str, str]] = {
    "CST": {
        "code": "comité social territorial compétences consultation organisation des services conditions de travail fonction publique territoriale",
        "regulatory": "décret n° 2021-571 du 10 mai 2021 comités sociaux territoriaux fonction publique territoriale",
        "case_law": "comité social territorial consultation obligatoire collectivités territoriales fonction publique territoriale",
    },
    "CAP": {
        "code": "commission administrative paritaire compétences fonctionnaires territoriaux garanties statutaires",
        "regulatory": "décret n° 89-229 du 17 avril 1989 commissions administratives paritaires territoriales",
        "case_law": "commission administrative paritaire fonction publique territoriale compétence consultation",
    },
    "CCP": {
        "code": "commission consultative paritaire agents contractuels fonction publique territoriale compétences",
        "regulatory": "décret n° 2016-1858 du 23 décembre 2016 commissions consultatives paritaires territoriales",
        "case_law": "commission consultative paritaire agent contractuel territorial consultation",
    },
    "FS": {
        "code": "formation spécialisée santé sécurité conditions de travail collectivités territoriales",
        "regulatory": "décret n° 85-603 du 10 juin 1985 santé sécurité travail collectivités territoriales",
        "case_law": "formation spécialisée santé sécurité conditions de travail fonction publique territoriale",
    },
}

_INSTANCE_TOPIC_TERMS: dict[str, dict[str, str]] = {
    "CST": {
        "organisation_travail": "organisation du travail conditions de travail temps de travail",
        "formation": "plan de formation formation professionnelle agents territoriaux",
        "ldg": "lignes directrices de gestion",
        "reglement": "règlement intérieur règlement de service",
    },
    "CAP": {
        "discipline": "discipline fonctionnaire territorial conseil de discipline garanties défense",
        "entretien": "recours compte rendu entretien professionnel saisine CAP",
        "titularisation": "stage titularisation refus titularisation insuffisance professionnelle",
    },
    "CCP": {
        "fin_contrat": "fin contrat non renouvellement agent contractuel",
        "licenciement": "licenciement agent contractuel territorial reclassement",
        "discipline": "sanction disciplinaire agent contractuel territorial",
    },
    "FS": {
        "risques": "santé sécurité prévention risques professionnels DUERP",
        "accident": "accident de service enquête prévention danger grave imminent",
        "rps": "risques psychosociaux charge de travail prévention",
    },
}


def _instance_search_context(instance: str, points: list[dict[str, Any]]) -> str:
    topic_map = _INSTANCE_TOPIC_TERMS.get(instance, {})
    topics = [
        topic_map[point["code"]]
        for point in points
        if isinstance(point, dict) and point.get("code") in topic_map
    ]
    return " ".join(dict.fromkeys(topics))[:180]


def _compact_instance_source(source: dict[str, Any], family: str) -> dict[str, Any]:
    from .fpt_scope import classify_public_service_scope

    text = (
        source.get("excerpt")
        or source.get("analysis_excerpt")
        or source.get("text")
        or source.get("full_text")
        or ""
    )
    scope = classify_public_service_scope(source, target_versant="FPT")
    decision_metadata_only = family == "jurisprudence" and source.get("full_text_retrieved") is not True
    return {
        "family": family,
        "source_type": source.get("source_type"),
        "source_id": source.get("source_id"),
        "title": str(source.get("title") or "Source officielle sans intitulé")[:500],
        "article": source.get("article"),
        "official_number": source.get("official_number"),
        "decision_date": source.get("decision_date"),
        "case_number": source.get("case_number"),
        "excerpt": str(text)[:3500] if text else None,
        "official_url": source.get("official_url") or source.get("source_url"),
        "requested_effective_date": (
            source.get("requested_effective_date")
            or source.get("effective_date_requested")
        ),
        "valid_from": source.get("valid_from"),
        "valid_to": source.get("valid_to"),
        "version_status": source.get("version_status"),
        "source_status": source.get("source_status"),
        "full_text_retrieved": source.get("full_text_retrieved") is True,
        "verification_note": (
            "Résultat de recherche : métadonnées/extrait uniquement, texte intégral non récupéré."
            if decision_metadata_only else
            "Source officielle récupérée à la date demandée ; son applicabilité au dossier reste à qualifier."
        ),
        "scope_assessment": {
            "scope": scope.get("scope"),
            "analysis_eligible": scope.get("analysis_eligible"),
            "claim_eligible": scope.get("claim_eligible"),
            "evidence": scope.get("evidence", []),
        },
    }


async def prepare_instance_with_legal_sources(
    instance: str,
    objet: str,
    *,
    legifrance_connector: Any,
    case_law_connector: Any,
    effective_date: date,
) -> dict[str, Any]:
    """Build the checklist and enrich it with bounded official-source searches.

    This function never calls an LLM and never turns search hits into a legal
    conclusion. Each upstream source family is queried once per preparation.
    """
    result = prepare_instance(instance, objet)
    key = result["instance"]
    profile = _INSTANCE_LEGAL_PROFILES[key]
    topic_context = _instance_search_context(key, result["points"])
    code_query = f"{profile['code']} {topic_context}".strip()[:500]
    regulatory_query = profile["regulatory"]
    case_law_query = f"{profile['case_law']} {topic_context}".strip()[:500]

    if not getattr(legifrance_connector, "configured", False):
        result["legal_research"] = {
            "provider": "PISTE_LEGIFRANCE",
            "status": "NOT_CONFIGURED",
            "requested_date": effective_date.isoformat(),
            "sources": [],
            "searches": [],
            "notice": "La connexion PISTE n'est pas configurée. La fiche reste une aide lexicale sans recherche juridique en direct.",
        }
        return result

    calls = await asyncio.gather(
        legifrance_connector.search_code_articles(code_query, effective_date),
        legifrance_connector.search_regulatory_texts(regulatory_query, effective_date, limit=3),
        case_law_connector.search(case_law_query, effective_date),
        return_exceptions=True,
    )
    families = ("CGFP", "TEXTES_REGLEMENTAIRES", "JURISPRUDENCE_ADMINISTRATIVE")
    compact_sources: list[dict[str, Any]] = []
    searches: list[dict[str, Any]] = []
    failed = 0
    for family, value in zip(families, calls):
        if isinstance(value, BaseException):
            failed += 1
            searches.append({
                "family": family,
                "status": "ERROR",
                "error_type": type(value).__name__,
                "result_count": 0,
            })
            continue
        if not isinstance(value, list):
            failed += 1
            searches.append({
                "family": family,
                "status": "INVALID_RESPONSE",
                "result_count": 0,
            })
            continue
        searches.append({
            "family": family,
            "status": "OK" if value else "NO_RESULT",
            "result_count": len(value),
        })
        compact_sources.extend(
            _compact_instance_source(item, family.lower())
            for item in value[:5]
            if isinstance(item, dict)
        )

    if failed == len(families):
        status = "UNAVAILABLE"
    elif failed:
        status = "PARTIAL"
    elif compact_sources:
        status = "SEARCHED"
    else:
        status = "NO_RESULT"

    result["legal_research"] = {
        "provider": "PISTE_LEGIFRANCE",
        "status": status,
        "requested_date": effective_date.isoformat(),
        "searches": searches,
        "sources": compact_sources[:12],
        "notice": (
            "Les résultats sont des pistes documentaires officielles, pas une conclusion juridique. "
            "La version temporelle, le statut de l'agent, le champ FPT et les conditions de saisine "
            "doivent être vérifiés pour le dossier. Les résultats de jurisprudence peuvent ne contenir "
            "que des métadonnées et extraits, pas le texte intégral."
        ),
    }
    return result
