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

from .cst_qualification import qualify_cst_topic, qualify_fs_topic, qualify_fs_operational_topic


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
            "label": "Conseil de discipline d'un fonctionnaire territorial",
            "keywords": ("sanction disciplinaire", "conseil de discipline", "sanction du deuxième groupe", "sanction du troisième groupe", "sanction du quatrième groupe", "exclusion temporaire de quatre à quinze jours", "exclusion temporaire de seize jours à deux ans", "radiation du tableau d'avancement", "abaissement d'échelon", "rétrogradation", "révocation", "mise à la retraite d'office"),
            "questions": (
                "Quelle sanction précise est envisagée et à quel groupe de l'échelle de l'article L. 533-1 correspond-elle ?",
                "S'agit-il d'une sanction des deuxième, troisième ou quatrième groupes ? La CAP ne siège pas en conseil de discipline pour les sanctions du premier groupe.",
                "Quels faits précis, dates, pièces et circonstances sont mentionnés dans le rapport de saisine ?",
                "L'agent a-t-il été informé de son droit à communication intégrale du dossier et à l'assistance d'un défenseur de son choix ?",
                "La compétence de l'autorité disciplinaire, les délais, l'impartialité, les droits de la défense et la proportionnalité sont-ils vérifiés ?",
            ),
            "documents": ("Rapport de saisine du conseil de discipline", "Dossier individuel et intégralité des pièces invoquées", "Preuve de communication du dossier et choix du défenseur", "Convocation, observations écrites et pièces de défense", "Projet de sanction et éléments de proportionnalité"),
        },
        "refus_titularisation": {
            "label": "Refus de titularisation",
            "keywords": ("refus de titularisation", "refus de titulariser"),
            "questions": (
                "La décision concerne-t-elle bien un fonctionnaire stagiaire et un refus de titularisation, et non une autre décision de gestion du stage ?",
                "Quels rapports d'évaluation, faits professionnels et éléments contradictoires fondent le refus ?",
                "La consultation de la CAP a-t-elle été organisée avant la décision et dans le respect des garanties applicables ?",
            ),
            "documents": ("Arrêté de nomination comme stagiaire et éventuelles prorogations", "Rapports de stage, évaluations et objectifs communiqués", "Projet de décision, rapport circonstancié et pièces du dossier", "Convocation et avis de la CAP"),
        },
        "stage_licenciement": {
            "label": "Licenciement en cours de stage",
            "keywords": ("licenciement en cours de stage", "licenciement du fonctionnaire stagiaire", "licenciement du stagiaire"),
            "questions": (
                "Le licenciement en cours de stage est-il fondé sur l'insuffisance professionnelle ou une faute disciplinaire, seuls motifs visés ici par R. 263-7 ?",
                "Le stade du stage, les évaluations, les faits reprochés et la procédure suivie sont-ils établis ?",
                "La CAP a-t-elle été saisie pour avis avant la décision ?",
            ),
            "documents": ("Arrêtés de nomination et de prorogation du stage", "Rapports d'évaluation et éléments d'accompagnement", "Rapport exposant l'insuffisance professionnelle ou les faits disciplinaires", "Projet de décision et preuve de saisine de la CAP"),
        },
        "availability_three_posts": {
            "label": "Licenciement après refus de trois postes à la réintégration",
            "keywords": ("refus de trois postes", "refus des trois postes", "trois postes proposés pour réintégration"),
            "questions": (
                "L'agent était-il en disponibilité et les trois propositions de postes répondaient-elles aux conditions légales de réintégration ?",
                "Les offres, leur réception, leur adéquation et les refus successifs sont-ils documentés ?",
                "La CAP a-t-elle été saisie avant le licenciement envisagé ?",
            ),
            "documents": ("Arrêté de disponibilité et demande de réintégration", "Trois propositions de postes et preuves de notification", "Réponses ou refus de l'agent", "Projet de licenciement et saisine de la CAP"),
        },
        "insuffisance_professionnelle": {
            "label": "Licenciement pour insuffisance professionnelle",
            "keywords": ("licenciement pour insuffisance professionnelle", "licenciement pour insuffisance professionnelle d'un fonctionnaire"),
            "questions": (
                "Les faits caractérisent-ils une insuffisance professionnelle et non une faute disciplinaire déguisée ?",
                "Les insuffisances sont-elles précises, répétées, objectivées et portées à la connaissance de l'agent ?",
                "La CAP a-t-elle été saisie pour avis avant la décision ?",
            ),
            "documents": ("Évaluations professionnelles et objectifs", "Exemples circonstanciés et datés des difficultés", "Mesures d'accompagnement, formations et alertes", "Projet de décision et avis de la CAP"),
        },
        "medical_termination": {
            "label": "Licenciement pour inaptitude ou situation médicale statutaire",
            "keywords": ("licenciement pour inaptitude physique", "licenciement pour inaptitude", "licenciement après congé maladie fonctionnaire"),
            "questions": (
                "Le cas relève-t-il précisément des articles 17 ou 35 du décret n° 87-602, visés par R. 263-7, et non d'une autre procédure d'inaptitude ?",
                "Les avis médicaux, possibilités de reclassement et étapes statutaires sont-ils établis ?",
                "La CAP a-t-elle été saisie pour avis dans le cas prévu par le texte ?",
            ),
            "documents": ("Avis du conseil médical et pièces médicales strictement nécessaires", "État des congés et décisions statutaires", "Étude des possibilités de reclassement", "Projet de décision et preuve de saisine de la CAP"),
        },
        "individual_decision_on_request": {
            "label": "Saisine de la CAP à la demande du fonctionnaire",
            "keywords": ("recours cap", "saisine cap à la demande", "contestation compte rendu entretien professionnel", "révision compte rendu entretien professionnel", "refus de temps partiel", "litige temps partiel", "refus de démission", "refus de télétravail", "interruption du télétravail", "refus congé compte épargne temps", "refus utilisation compte personnel de formation", "refus congé formation syndicale", "refus congé formation santé sécurité", "second refus de formation"),
            "questions": (
                "Quelle décision individuelle est contestée et relève-t-elle exactement d'un des cas limitativement énumérés à R. 263-10 ?",
                "La demande est-elle présentée par le fonctionnaire intéressé et dans les délais applicables à la décision concernée ?",
                "Pour l'entretien professionnel, le recours hiérarchique préalable et sa réponse sont-ils établis ?",
                "Pour le CPF ou une action de formation, s'agit-il du cas légal précis visé par R. 263-10, notamment du second refus pour certaines actions ?",
            ),
            "documents": ("Décision contestée et preuve de notification", "Demande initiale et échanges avec l'autorité", "Recours hiérarchique préalable et réponse lorsqu'ils sont requis", "Pièces démontrant le cas de saisine prévu par R. 263-10"),
        },
        "mandatory_training_refusal": {
            "label": "Refus de formation soumis à avis obligatoire de la CAP",
            "keywords": ("refus congé de formation hygiène sécurité", "refus congé de formation santé sécurité", "refus congé de formation syndicale", "refus cpf au titre de l'article l. 422-13", "second refus de formation", "deuxième refus action de formation"),
            "questions": (
                "Le refus concerne-t-il un congé de formation en matière d'hygiène, de sécurité et de conditions de travail, un congé de formation syndicale, le CPF dans le cas de L. 422-13 ou une action de formation après un second refus ?",
                "Le cas précis relève-t-il de R. 263-7, qui prévoit une saisine pour avis, et non de la saisine à la demande du fonctionnaire prévue à R. 263-10 ?",
                "Les demandes antérieures, les motifs des refus et leur notification sont-ils établis ?",
            ),
            "documents": ("Demandes de congé ou de formation", "Décisions de refus et preuves de notification", "Historique des demandes et refus successifs", "Texte fondant la demande et projet de décision"),
        },
        "reinstatement_after_civil_disqualification": {
            "label": "Réintégration après privation des droits civiques ou interdiction d'emploi public",
            "keywords": ("réintégration après privation des droits civiques", "réintégration après interdiction d'exercer un emploi public", "réintégration après interdiction emploi public", "réintégration dans la nationalité française"),
            "questions": (
                "La demande intervient-elle à l'issue de la période de privation des droits civiques, d'interdiction d'exercer un emploi public ou à la suite de la réintégration dans la nationalité française ?",
                "L'autorité ayant pouvoir de nomination a-t-elle recueilli l'avis de la commission compétente conformément à R. 263-8 ?",
                "Les dates de fin de la mesure et la demande de réintégration sont-elles établies ?",
            ),
            "documents": ("Décision de privation des droits ou d'interdiction et preuve de sa fin", "Justificatif de réintégration dans la nationalité française le cas échéant", "Demande de réintégration", "Saisine et avis de la CAP"),
        },
        "disabled_worker_recruitment": {
            "label": "Recrutement contractuel d'un travailleur handicapé",
            "keywords": ("renouvellement contrat travailleur handicapé", "non renouvellement contrat travailleur handicapé", "recrutement contractuel travailleur handicapé"),
            "questions": (
                "Le recrutement relève-t-il du dispositif statutaire de recrutement des travailleurs handicapés et des articles R. 352-32 à R. 352-34 ?",
                "S'agit-il du renouvellement ou du non-renouvellement précisément visé par R. 263-7 ?",
                "Les évaluations, avis et éléments de décision sont-ils communiqués à la CAP ?",
            ),
            "documents": ("Contrat et fondement du recrutement", "Évaluations et bilan de période", "Projet de renouvellement ou de non-renouvellement", "Avis et pièces transmis à la CAP"),
        },
        "unemployment_compensation": {
            "label": "Décision relative à l'indemnisation du chômage",
            "keywords": ("indemnisation du chômage fonctionnaire", "allocation chômage fonctionnaire", "refus allocation chômage agent public"),
            "questions": (
                "La décision concerne-t-elle une indemnisation du chômage relevant de L. 557-1-1 ?",
                "Quelle autorité est compétente pour l'indemnisation et quelle décision individuelle est contestée ?",
                "Les éléments de fin de fonctions, d'ouverture des droits et de calcul sont-ils disponibles ?",
            ),
            "documents": ("Décision d'ouverture ou de refus des droits", "Attestation employeur et éléments de fin de fonctions", "Décompte et éléments de calcul de l'indemnisation"),
        },
    },
    "CCP": {
        "fin_contrat": {
            "label": "Fin ou non-renouvellement de contrat : qualification préalable",
            "keywords": ("non-renouvellement", "fin de contrat", "terme du contrat", "renouvellement de contrat"),
            "questions": (
                "Quelle est la nature du contrat, son fondement légal, sa durée, sa date de terme et ses renouvellements ?",
                "La décision est-elle un licenciement, un non-renouvellement à l'échéance ou une simple information sur le terme du contrat ?",
                "Pour un non-renouvellement, l'agent est-il investi d'un mandat syndical ? La consultation prévue à R. 272-19 ne doit pas être généralisée à tous les non-renouvellements.",
                "Pour un licenciement, l'agent a-t-il dépassé la période d'essai et ne relève-t-il pas d'une des exceptions expressément prévues à R. 272-19 ?",
            ),
            "documents": ("Contrat initial et avenants", "Courrier de décision et preuve de notification", "Motif exposé et pièces justificatives", "Éléments relatifs à la période d'essai et au fondement légal du recrutement", "Justificatif du mandat syndical le cas échéant"),
        },
        "dismissal_after_trial": {
            "label": "Licenciement d'un agent contractuel après la période d'essai",
            "keywords": ("licenciement après période d'essai", "licenciement d'un agent contractuel", "licenciement contractuel territorial"),
            "questions": (
                "Le licenciement intervient-il après la période d'essai ?",
                "L'agent relève-t-il d'une exception de R. 272-19, notamment d'un recrutement sur le fondement de L. 333-1, L. 333-12 ou L. 343-1 ?",
                "Quel motif légal est invoqué et quelles garanties particulières s'appliquent (motivation, entretien préalable, reclassement, préavis, notification) ?",
                "La CCP a-t-elle été consultée avant la décision lorsque R. 272-19 l'impose ?",
            ),
            "documents": ("Contrat et avenants avec fondement légal", "Éléments relatifs à la période d'essai", "Rapport motivant le licenciement", "Convocation et compte rendu de l'entretien préalable", "Recherche de reclassement et réponses", "Projet de décision et avis de la CCP"),
        },
        "union_mandate_nonrenewal": {
            "label": "Non-renouvellement du contrat d'un agent investi d'un mandat syndical",
            "keywords": ("non-renouvellement agent mandat syndical", "non renouvellement mandat syndical", "non-renouvellement représentant syndical contractuel", "non-renouvellement agent investi d'un mandat syndical"),
            "questions": (
                "L'agent contractuel est-il investi d'un mandat syndical à la date pertinente ?",
                "Le projet porte-t-il bien sur le non-renouvellement du contrat à son terme ?",
                "La CCP a-t-elle été saisie pour avis avant la décision et les garanties liées au mandat ont-elles été vérifiées ?",
            ),
            "documents": ("Contrat et échéance", "Justificatif du mandat syndical et de sa période", "Éléments du dossier de renouvellement", "Projet de décision et saisine de la CCP"),
        },
        "physical_unfitness": {
            "label": "Licenciement pour inaptitude physique définitive",
            "keywords": ("licenciement pour inaptitude physique définitive", "inaptitude physique définitive agent contractuel"),
            "questions": (
                "L'inaptitude est-elle définitive et établie selon les modalités prévues par le décret n° 88-145 ?",
                "Les obligations de reclassement et les étapes des articles 13 ou 39-5 sont-elles applicables et respectées ?",
                "La CCP a-t-elle été consultée dans le cas prévu par R. 272-19 ?",
            ),
            "documents": ("Avis médical concluant à l'inaptitude définitive", "Contrat et ancienneté", "Étude des possibilités de reclassement et propositions", "Échanges avec l'agent", "Projet de décision et avis de la CCP"),
        },
        "discipline": {
            "label": "Conseil de discipline d'un agent contractuel",
            "keywords": ("sanction disciplinaire", "conseil de discipline", "exclusion temporaire de quatre jours", "exclusion temporaire de quatre à quinze jours", "exclusion temporaire de seize jours", "licenciement disciplinaire", "sanction autre que avertissement", "sanction autre que le blâme"),
            "questions": (
                "Quelle sanction précise est envisagée au regard de l'article 36-1 du décret n° 88-145 ?",
                "S'agit-il d'une exclusion de quatre jours ou plus ou d'un licenciement disciplinaire ? L'avertissement, le blâme et l'exclusion de trois jours au maximum ne relèvent pas de la saisine disciplinaire de la CCP.",
                "La procédure respecte-t-elle le délai de prescription de trois ans à compter de la connaissance effective des faits, sous réserve de l'interruption prévue en cas de poursuites pénales ?",
                "L'agent a-t-il reçu l'information sur son droit à communication intégrale du dossier et à l'assistance de défenseurs de son choix ?",
                "Le rapport décrit-il les faits reprochés et leurs circonstances, et l'agent a-t-il été mis en mesure d'en prendre connaissance ?",
            ),
            "documents": ("Rapport disciplinaire décrivant les faits et circonstances", "Dossier individuel et pièces annexes", "Preuve d'information sur le droit à communication du dossier", "Convocation et preuve de transmission du rapport", "Observations et pièces de défense", "Projet de sanction et éléments de proportionnalité"),
        },
        "refusal_individual_decision": {
            "label": "Saisine de la CCP à la demande de l'agent contractuel",
            "keywords": ("recours ccp", "saisine ccp à la demande", "refus de temps partiel agent contractuel", "litige temps partiel contractuel", "contestation compte rendu entretien professionnel contractuel", "révision compte rendu entretien professionnel contractuel", "refus utilisation compte personnel formation contractuel", "refus de télétravail agent contractuel", "interruption télétravail agent contractuel", "refus congé compte épargne temps contractuel"),
            "questions": (
                "La décision contestée figure-t-elle exactement parmi les cas énumérés à R. 272-21 : temps partiel, révision de l'entretien professionnel, CPF, télétravail ou compte épargne-temps ?",
                "La saisine est-elle demandée par l'agent contractuel intéressé et dans les délais applicables ?",
                "Les démarches préalables, la décision contestée et sa notification sont-elles documentées ?",
            ),
            "documents": ("Décision contestée et preuve de notification", "Demande initiale et échanges", "Recours hiérarchique et réponse lorsqu'ils sont requis", "Pièces démontrant le cas de saisine prévu par R. 272-21"),
        },
        "refusal_training": {
            "label": "Refus de congé de formation syndicale ou santé-sécurité",
            "keywords": ("refus congé de formation syndicale contractuel", "refus congé formation syndicale", "refus congé formation hygiène sécurité contractuel", "refus congé formation santé sécurité contractuel"),
            "questions": (
                "Le refus concerne-t-il le congé de formation en matière d'hygiène, de sécurité et de conditions de travail ou le congé pour formation syndicale visé par R. 272-19 ?",
                "La demande, les conditions d'éligibilité et la décision de refus sont-elles établies ?",
                "La CCP a-t-elle été consultée pour avis avant la décision ?",
            ),
            "documents": ("Demande de congé et justificatifs", "Réponse motivée de l'employeur", "Textes et conditions d'éligibilité applicables", "Saisine et avis de la CCP"),
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


def prepare_instance(
    instance: str,
    objet: str,
    *,
    formation_specialisee_exists: bool | None = None,
) -> dict[str, Any]:
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
    first_group_sanction_terms = (
        "avertissement",
        "blâme",
        "exclusion temporaire de trois jours",
        "exclusion temporaire de fonctions pour une durée maximale de trois jours",
        "premier groupe",
    )
    higher_group_sanction_terms = (
        "deuxième groupe",
        "troisième groupe",
        "quatrième groupe",
        "quatre à quinze jours",
        "seize jours à deux ans",
        "radiation du tableau d'avancement",
        "abaissement d'échelon",
        "rétrogradation",
        "révocation",
        "mise à la retraite d'office",
        "exclusion temporaire de quatre jours",
    )
    first_group_only = (
        any(f" {_fold(term)} " in normalized for term in first_group_sanction_terms)
        and not any(f" {_fold(term)} " in normalized for term in higher_group_sanction_terms)
    )

    for rule_key, rule in INSTANCE_RULES[key].items():
        if (
            rule_key == "discipline"
            and key in {"CAP", "CCP"}
            and first_group_only
        ):
            continue
        if any(f" {_fold(word)} " in normalized for word in rule["keywords"]):
            points.append({
                "code": rule_key,
                "libelle": rule["label"],
                "questions": list(rule["questions"]),
                "documents": list(rule["documents"]),
                "qualification": "piste_de_preparation_a_confirmer",
            })
            documents.extend(rule["documents"])

    result = {
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
    if key == "CST":
        result["cst_qualification"] = qualify_cst_topic(
            objet, formation_specialisee_exists=formation_specialisee_exists
        )
        result["fs_qualification"] = qualify_fs_topic(objet)
        result["fs_operational_qualification"] = qualify_fs_operational_topic(
            objet, formation_specialisee_exists=formation_specialisee_exists
        )
    elif key == "FS":
        result["fs_qualification"] = qualify_fs_topic(objet)
        result["fs_operational_qualification"] = qualify_fs_operational_topic(
            objet, formation_specialisee_exists=True
        )
    return result


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
    decision_metadata_only = family.startswith("jurisprudence") and source.get("full_text_retrieved") is not True
    full_text_retrieved = source.get("full_text_retrieved") is True or (
        not decision_metadata_only and bool(source.get("text") or source.get("full_text"))
    )
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
        "full_text_retrieved": full_text_retrieved,
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
    formation_specialisee_exists: bool | None = None,
) -> dict[str, Any]:
    """Build the checklist and enrich it with bounded official-source searches.

    This function never calls an LLM and never turns search hits into a legal
    conclusion. Each upstream source family is queried once per preparation.
    """
    result = prepare_instance(
        instance, objet, formation_specialisee_exists=formation_specialisee_exists
    )
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
            if not isinstance(value, Exception):
                raise value
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
