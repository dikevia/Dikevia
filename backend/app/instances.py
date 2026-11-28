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
                "L'agent a-t-il été informé par écrit de la procédure et des faits précis reprochés, de son droit à communication intégrale du dossier et à l'assistance d'un ou plusieurs conseils de son choix ? Les pièces sont-elles numérotées et un délai suffisant est-il laissé pour préparer la défense (décret n° 89-677, art. 4) ?",
                "Le rapport de saisine et ses annexes ont-ils été mis à disposition de l'agent dans les mêmes conditions (décret n° 89-677, art. 5) ?",
                "L'agent a-t-il été convoqué par lettre recommandée avec avis de réception au moins quinze jours avant la séance et informé de ses droits à observations écrites ou orales, à citation de témoins et à assistance (art. 6) ?",
                "Le conseil de discipline statue-t-il dans les deux mois de sa saisine, délai ramené à un mois en cas de suspension, sous réserve des prolongations légales liées au report (art. 13) ?",
                "L'avis est-il communiqué sans délai et la décision de l'autorité territoriale est-elle motivée (art. 14) ?",
                "La compétence de l'autorité disciplinaire, l'impartialité, les droits de la défense et la proportionnalité sont-ils vérifiés ?",
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
        "availability_reintegration": {
            "label": "Réintégration après disponibilité : régime et postes vacants",
            "keywords": ("réintégration après disponibilité", "demande de réintégration après disponibilité", "fin de disponibilité", "retour de disponibilité", "refus de réintégration après disponibilité", "réintégration disponibilité"),
            "questions": (
                "Quel est le fondement exact de la disponibilité : disponibilité de droit pour raison familiale, disponibilité d'office pour raison de santé, autre disponibilité sur demande, ou disponibilité consécutive au refus d'un emploi après détachement ou congé parental ? Ne pas appliquer un régime unique à toutes les disponibilités.",
                "Pour une disponibilité sur demande, la demande de renouvellement ou de réintégration a-t-elle été adressée au moins trois mois avant l'échéance, sauf disponibilité n'excédant pas trois mois (décret n° 86-68, art. 26) ?",
                "Pour les cas de L. 514-6, les conditions propres à la disponibilité de droit pour raisons familiales ou d'office pour raison de santé sont-elles vérifiées ? Pour le suivi du conjoint ou partenaire, la durée de trois ans modifie la règle de réintégration et la proposition d'une des trois premières vacances.",
                "Dans les autres cas, si la disponibilité n'a pas excédé trois ans, une des trois premières vacances dans la collectivité ou l'établissement d'origine doit-elle être proposée (CGFP, art. L. 514-7) ? Identifier les vacances intervenues et leur date.",
                "La situation relève-t-elle plutôt de L. 514-8 : refus successifs de trois postes proposés en vue de la réintégration, dans le ressort territorial du cadre d'emplois ? Vérifier séparément la réalité, l'ordre, la correspondance au grade et la notification de chaque proposition.",
                "Un licenciement envisagé après trois refus est-il précédé de l'avis de la CAP compétente ? L'article L. 514-8 prévoit une possibilité de licenciement, pas une conséquence automatique ; vérifier également les droits à pension.",
                "Si l'inaptitude physique empêche la réintégration, l'autorité a-t-elle examiné le reclassement, la disponibilité d'office pour raison de santé et, seulement si les conditions sont réunies, la retraite ou le licenciement (décret n° 86-68, art. 26) ?",
            ),
            "documents": ("Arrêté de disponibilité et fondement légal", "Demande de réintégration ou de renouvellement et preuve de réception", "Historique des vacances d'emplois et dates", "Fiches des postes proposés et correspondance au grade", "Preuves de notification et réponses de l'agent", "Avis médicaux utiles le cas échéant", "Saisine et avis de la CAP si un licenciement est envisagé"),
        },
        "parental_leave_reintegration": {
            "label": "Réintégration après congé parental d'un fonctionnaire territorial",
            "keywords": ("réintégration après congé parental", "retour de congé parental fonctionnaire", "fin de congé parental fonctionnaire territorial"),
            "questions": (
                "La personne est-elle fonctionnaire territorial titulaire et le congé parental arrive-t-il à son terme ou fait-il l'objet d'une demande de fin anticipée ?",
                "La réintégration de plein droit dans la collectivité ou l'établissement d'origine est-elle organisée, au besoin en surnombre (CGFP, art. L. 515-11) ?",
                "Le choix de l'agent entre l'ancien emploi et un emploi le plus proche du dernier lieu de travail ou du domicile, lorsque celui-ci a changé pour assurer l'unité de la famille, a-t-il été respecté ?",
                "La situation est-elle distinguée d'une disponibilité pour élever un enfant, qui relève d'un autre régime et ne doit pas être assimilée au congé parental ?",
                "La CAP est-elle sollicitée uniquement si un texte prévoit sa consultation pour la décision effectivement contestée ? La réintégration après congé parental n'entraîne pas, à elle seule, une saisine automatique de la CAP.",
            ),
            "documents": ("Arrêté de congé parental et dates", "Demande de réintégration ou de fin anticipée", "Choix exprimé par l'agent", "Poste proposé et éléments de localisation", "Décision de réintégration et éventuels échanges"),
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
        "reclassement_inaptitude": {
            "label": "Préparation au reclassement et reclassement d'un fonctionnaire territorial",
            "keywords": ("préparation au reclassement", "période de préparation au reclassement", "ppr", "reclassement pour inaptitude", "inaptitude aux fonctions du grade", "inapte à ses fonctions", "procédure de reclassement fonctionnaire"),
            "questions": (
                "Le fonctionnaire est-il reconnu inapte aux fonctions correspondant aux emplois de son grade, sans être inapte à toute activité, et l'avis du conseil médical a-t-il été recueilli (décret n° 85-1054, art. 2) ?",
                "L'autorité a-t-elle informé l'agent de son droit à la période de préparation au reclassement (PPR) dès réception de l'avis du conseil médical ?",
                "La PPR a-t-elle été proposée et sa date de début correctement déterminée ? Vérifier les reports possibles jusqu'à deux mois d'un commun accord et le report du début à la reprise lorsque l'agent est dans certains congés (art. 2).",
                "La PPR a-t-elle pris fin au reclassement ou au plus tard après un an, avec prolongation éventuelle à raison des congés légalement visés ? L'agent reste-t-il en position d'activité et conserve-t-il les éléments de rémunération prévus pendant la PPR (art. 2 et 2-1) ?",
                "Le projet de convention a-t-il été notifié au plus tard deux mois après le début de la PPR et l'agent a-t-il disposé de quinze jours pour le signer (art. 2-3) ?",
                "Si l'agent a demandé son reclassement, plusieurs emplois pouvant être pourvus par détachement ont-ils été recherchés et proposés ? L'impossibilité de proposer de tels emplois est-elle motivée et la procédure conduite dans les trois mois suivant la demande (art. 3) ?",
                "En l'absence de demande de l'agent, les conditions de l'article 3-1 sont-elles réunies, notamment l'inaptitude permanente, l'absence de congé pour raison de santé ou CITIS et la tenue d'un entretien préalable ?",
                "Si la décision engageant la procédure de reclassement a fait l'objet d'un recours gracieux, la CAP a-t-elle été consultée avant que l'autorité statue (art. 3-1) ? Cette consultation n'est pas automatique pour toute PPR ou tout reclassement.",
            ),
            "documents": ("Avis du conseil médical", "Information sur le droit à la PPR", "Convention et projet individuel de préparation", "Évaluations périodiques de la PPR", "Demande de reclassement et date de réception", "Liste des emplois recherchés et offres écrites", "Décision motivée d'impossibilité", "Recours gracieux et avis de la CAP le cas échéant"),
        },
        "individual_decision_on_request": {
            "label": "Saisine de la CAP à la demande du fonctionnaire",
            "keywords": ("recours cap", "saisine cap à la demande", "contestation compte rendu entretien professionnel", "contestation du compte rendu d'entretien professionnel", "révision compte rendu entretien professionnel", "révision du compte rendu d'entretien professionnel", "refus de temps partiel", "litige temps partiel", "refus de démission", "refus de télétravail", "interruption du télétravail", "refus congé compte épargne temps", "refus utilisation compte personnel de formation", "refus congé formation syndicale", "refus congé formation santé sécurité", "second refus de formation"),
            "questions": (
                "Quelle décision individuelle est contestée et relève-t-elle exactement d'un des cas limitativement énumérés à R. 263-10 ?",
                "La demande est-elle présentée par le fonctionnaire intéressé et dans les délais applicables à la décision concernée ?",
                "Pour l'entretien professionnel, le recours préalable de révision a-t-il été formé dans les quinze jours francs suivant la notification du compte rendu (article 7 du décret n° 2014-1526) ?",
                "Pour ce recours, l'autorité territoriale a-t-elle répondu dans les quinze jours suivant sa réception et la CAP a-t-elle été saisie dans le mois suivant la notification de cette réponse ?",
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
                "S'il s'agit d'un contrat de projet, la fin ou la rupture anticipée est-elle notifiée par LRAR ou remise contre signature au plus tard deux mois avant le terme pour un engagement d'au plus trois ans, ou trois mois avant le terme au-delà (articles 38-1 III et 38-2) ? Ne pas étendre ces délais spécifiques à tous les CDD.",
                "Pour un non-renouvellement ordinaire hors contrat de projet, quel texte spécial, statut du contrat et éventuelle protection de l'agent déterminent les formalités et délais ? Depuis le 1er octobre 2025, les I et II de l'article 38-1 relatifs aux anciens délais généraux de notification de l'intention de renouveler ou non sont abrogés : ne pas appliquer ces anciens délais de huit jours, un, deux ou trois mois aux situations relevant du droit en vigueur. Ne pas appliquer par défaut les délais du contrat de projet.",
            ),
            "documents": ("Contrat initial et avenants", "Courrier de décision et preuve de notification", "Motif exposé et pièces justificatives", "Éléments relatifs à la période d'essai et au fondement légal du recrutement", "Justificatif du mandat syndical le cas échéant", "Calendrier de notification du terme pour un contrat de projet"),
        },
        "dismissal_after_trial": {
            "label": "Licenciement d'un agent contractuel après la période d'essai",
            "keywords": ("licenciement après période d'essai", "licenciement d'un agent contractuel", "licenciement contractuel territorial"),
            "questions": (
                "Le licenciement intervient-il après la période d'essai ?",
                "L'agent relève-t-il d'une exception de R. 272-19, notamment d'un recrutement sur le fondement de L. 333-1, L. 333-12 ou L. 343-1 ?",
                "La convocation à l'entretien préalable a-t-elle été remise par lettre recommandée avec avis de réception ou en main propre contre signature, avec indication de son objet, au moins cinq jours ouvrables avant l'entretien ? L'agent peut-il être accompagné par la personne de son choix (article 42 du décret n° 88-145) ?",
                "Si l'agent siège dans un organisme consultatif, a bénéficié au cours des douze derniers mois d'une autorisation spéciale d'absence syndicale visée par les textes, ou dispose d'une décharge d'activité d'au moins 20 %, la CCP a-t-elle été consultée avant l'entretien préalable ? Vérifier aussi la protection de l'ancien représentant pendant les douze mois suivant la fin du mandat et du candidat non élu pendant les six mois suivant l'élection (article 42-2).",
                "Quel motif légal est invoqué et quel fondement de recrutement s'applique ? Distinguer faute disciplinaire, insuffisance professionnelle, inaptitude, motifs de l'article 39-3 et emplois de direction L. 343-1.",
                "Le préavis a-t-il été calculé selon l'ancienneté de services à la date d'envoi de la notification : huit jours avant six mois, un mois de six mois à moins de deux ans, deux mois à partir de deux ans, avec doublement éventuel pour les bénéficiaires concernés d'une obligation d'emploi (article 40) ? Vérifier les exceptions.",
                "Pour les motifs des 1° à 4° du I de l'article 39-3 concernant un agent recruté sur emploi permanent L. 332-8, les conditions du reclassement de l'article 39-5 sont-elles réunies ? Ne pas appliquer ce régime aux motifs exclus, aux emplois de projet visés au II ou aux emplois L. 343-1 visés au III.",
                "La CCP a-t-elle été consultée avant la décision lorsque R. 272-19 l'impose, sous réserve des exceptions légales ? Pour les agents protégés visés à l'article 42-2, la consultation préalable à l'entretien a-t-elle également été faite ?",
                "La décision finale est-elle notifiée par LRAR ou remise en main propre contre signature après l'entretien et la consultation requise, avec motifs précis et date d'effet tenant compte des congés annuels et du préavis (article 42-1) ?",
                "L'agent se trouve-t-il dans une situation de protection contre le licenciement liée à une grossesse, à certains congés ou aux dix semaines suivant leur expiration (article 41) ? Vérifier les exceptions légales.",

            ),
            "documents": ("Contrat et avenants avec fondement légal", "Éléments relatifs à la période d'essai", "Rapport motivant le licenciement", "Convocation et compte rendu de l'entretien préalable", "Recherche de reclassement et réponses", "Projet de décision et avis de la CCP"),
        },
        "professional_inadequacy": {
            "label": "Licenciement pour insuffisance professionnelle d'un agent contractuel",
            "keywords": ("licenciement pour insuffisance professionnelle contractuel", "licenciement pour insuffisance professionnelle d'un agent contractuel", "insuffisance professionnelle agent contractuel territorial"),
            "questions": (
                "Les faits invoqués relèvent-ils d'une insuffisance professionnelle objectivée et non d'une faute disciplinaire déguisée ? Les griefs sont-ils précis, circonstanciés, répétés et appréciés au regard des fonctions réellement confiées ?",
                "Avant la décision, l'agent a-t-il été mis à même de demander la communication de l'intégralité de son dossier individuel et de toute pièce sur laquelle l'autorité entend fonder le licenciement, même si elle ne figure pas au dossier, dans un délai suffisant (article 39-2 du décret n° 88-145) ?",
                "L'entretien préalable a-t-il été organisé conformément à l'article 42, au moins cinq jours ouvrables après la présentation de la convocation, avec possibilité d'accompagnement ?",
                "La CCP doit-elle être consultée avant la décision au titre de R. 272-19 et, si l'agent relève d'une catégorie protégée de l'article 42-2, avant l'entretien préalable ?",
                "La décision motivée a-t-elle été notifiée dans les formes de l'article 42-1 ? Le préavis de l'article 40 est-il dû et correctement calculé ? Le reclassement de l'article 39-5 ne doit pas être présumé applicable à l'insuffisance professionnelle, qui est distincte des motifs de l'article 39-3.",
            ),
            "documents": ("Contrat et fondement légal du recrutement", "Fiche de poste et objectifs communiqués", "Évaluations et éléments factuels datés", "Dossier individuel et pièces externes invoquées", "Preuve de l'information sur le droit à communication", "Convocation et compte rendu de l'entretien préalable", "Avis de la CCP le cas échéant", "Décision motivée et calcul du préavis"),
        },
        "return_after_leave": {
            "label": "Réemploi d'un agent contractuel à l'issue d'un congé",
            "keywords": ("réemploi après congé", "demande de réemploi après congé", "retour de congé agent contractuel", "réintégration après congé agent contractuel", "priorité emploi similaire contractuel", "réemploi après congé parental contractuel"),
            "questions": (
                "Quel est le fondement du recrutement, la nature du contrat (CDI, CDD ou contrat de projet), le congé concerné et sa date de fin ? Vérifier les conditions d'application des articles 33 et 34 du décret n° 88-145.",
                "L'agent est-il physiquement apte à reprendre et remplit-il toujours les conditions requises ? Pour les congés visés à l'article 13 I, appliquer le renvoi aux conditions de l'article 33.",
                "L'ancien emploi peut-il être repris compte tenu des nécessités du service ? À défaut, la priorité pour un emploi similaire assorti d'une rémunération équivalente a-t-elle été examinée et documentée (article 33) ?",
                "Le contrat est-il un CDD dont le terme est postérieur à la date à laquelle l'agent peut prétendre au réemploi ? Si oui, le réemploi ne peut porter que sur la période restant à courir (article 34), sous réserve des exceptions et décisions juridictionnelles applicables.",
                "S'il s'agit d'un contrat de projet, le terme est-il postérieur à la demande de réemploi et le projet ou l'opération n'est-il pas déjà réalisé ? Le réemploi ne peut alors porter que sur la période restant à courir (article 13 I).",
                "S'il s'agit d'un congé parental, vérifier le régime spécial de réintégration de plein droit, au besoin en surnombre, dans l'ancien emploi ou un emploi le plus proche du dernier lieu de travail ou du domicile dans les conditions de l'article 33. Ne pas opposer mécaniquement la condition de terme de l'article 34 : le Conseil d'État a annulé son application à ce congé.",
                "S'il s'agit du congé lié à l'exercice d'un mandat parlementaire visé à l'article 19, vérifier la réintégration à la demande, au besoin en surnombre, dans l'emploi antérieur ou un emploi analogue à rémunération identique dans les deux mois suivant l'information de l'employeur ; tenir compte de l'annulation juridictionnelle de l'article 34 pour ce congé.",
                "Pour un congé pour convenances personnelles ou création d'entreprise, vérifier les exclusions spécifiques liées aux fondements de recrutement L. 333-1, L. 333-12 et L. 343-1 avant de conclure à un droit au réemploi.",
                "En cas de refus ou d'impossibilité de réemploi, distinguer la fin normale du contrat, le non-renouvellement et le licenciement pour impossibilité de réemploi au sens du 5° du I de l'article 39-3. Ne pas confondre priorité de réemploi et reclassement de l'article 39-5.",
            ),
            "documents": ("Contrat et fondement légal du recrutement", "Décision de congé et dates", "Demande de réemploi et preuve de réception", "Avis d'aptitude si nécessaire", "État de l'ancien emploi et nécessités du service", "Inventaire des emplois similaires et rémunérations", "Date de terme du CDD ou du contrat de projet", "État d'avancement du projet le cas échéant", "Décision motivée et notification"),
        },
        "leave_18_1_request_deadline": {
            "label": "Délais de renouvellement ou de réemploi après congé sans rémunération (article 18-1)",
            "keywords": ("demande de réemploi trois mois avant", "réemploi après congé pour convenances personnelles", "réemploi après congé création entreprise", "renouvellement congé sans rémunération contractuel", "silence demande réemploi contractuel", "fin anticipée congé sans rémunération contractuel", "article 18-1 décret 88-145"),
            "questions": (
                "Le congé relève-t-il précisément de l'article 15 (raisons familiales, sous condition d'emploi depuis plus d'un an), de l'article 17 (convenances personnelles, agent en CDI) ou de l'article 18 (création ou reprise d'entreprise) du décret n° 88-145 ? L'article 18-1 ne doit pas être étendu aux autres congés.",
                "L'agent a-t-il sollicité le renouvellement du congé ou son réemploi au moins trois mois avant son terme, par lettre recommandée avec demande d'avis de réception (article 18-1 I) ? Vérifier la date d'envoi et la preuve de réception.",
                "Si l'agent n'a pas fait connaître sa décision dans ce délai, l'autorité l'a-t-elle informé sans délai, par LRAR, des conséquences de son silence ? Le délai de quinze jours ne court qu'à compter de la réception de cette information ; la fin de plein droit et sans indemnité n'intervient au terme du congé qu'en l'absence de réponse dans ce délai (article 18-1 II).",
                "L'agent physiquement apte qui a demandé son réemploi dans le délai doit être réemployé au terme du congé dans les conditions des articles 33 et 34. Vérifier séparément l'ancien emploi, les nécessités du service, la priorité pour un emploi similaire et le terme du CDD.",
                "En cas de demande de fin anticipée du congé, le préavis est-il de trois mois ? Existe-t-il un motif grave, notamment une diminution des revenus du ménage, permettant l'application des conditions de réemploi dès réception de la demande par l'autorité (article 18-1 III) ?",
                "Ne pas appliquer le délai de trois mois de l'article 18-1 aux congés des articles 13, 19 ou 20 : ils relèvent de dispositions spécifiques. Ne pas réutiliser l'ancien article 35, abrogé, ni son ancien délai d'un mois après libération du service national.",
            ),
            "documents": ("Contrat et fondement légal du recrutement", "Décision de congé et article applicable", "Dates de début et de fin du congé", "LRAR de demande de renouvellement ou de réemploi et preuve de réception", "LRAR d'information sur les conséquences du silence et preuve de réception", "Réponse de l'agent et date", "Demande de fin anticipée et motif grave éventuel", "Éléments d'aptitude et de recherche de réemploi"),
        },
        "national_service_reserve_return": {
            "label": "Retour après service national, réserve ou activité liée au SNU",
            "keywords": ("réemploi après service national", "réemploi après libération du service national", "libération du service national", "retour du service national contractuel", "réemploi après une période dans la réserve opérationnelle", "réserve opérationnelle agent contractuel", "réserve de sécurité civile agent contractuel", "réserve sanitaire agent contractuel", "réemploi après réserve", "instruction militaire agent contractuel", "séjour de cohésion SNU agent contractuel"),
            "questions": (
                "S'agit-il de l'accomplissement du service national actif, d'une période d'instruction militaire, d'une activité dans la réserve opérationnelle, la réserve de sécurité civile ou la réserve sanitaire, ou de fonctions de préparation et d'encadrement des séjours de cohésion du SNU ? Ces situations ont des règles distinctes (article 20).",
                "Pour le service national actif, l'agent est-il placé dans la position d'accomplissement du service national avec perte du traitement ? À sa libération, le droit au réemploi est-il examiné au titre de l'article 33, sous réserve de l'article 34 ?",
                "Pour une période d'instruction militaire, l'agent a-t-il été placé en congé avec traitement pendant toute la période ? Ne pas confondre cette instruction avec une activité de réserve.",
                "Pour la réserve opérationnelle, les jours d'activité sur le temps de travail sont-ils décomptés par année civile : congé avec traitement jusqu'à trente jours cumulés, puis congé sans traitement au-delà ? Pour la réserve de sécurité civile, le seuil est de quinze jours cumulés par année civile.",
                "Pour la réserve sanitaire, l'activité ou la formation sur le temps de travail ouvre-t-elle droit au congé avec rémunération pendant toute la période ?",
                "Pour les fonctions de préparation et d'encadrement des séjours de cohésion du SNU, le contrat, renouvellements compris, atteint-il au moins dix-huit mois ? La durée reste-t-elle dans la limite de soixante jours sur douze mois consécutifs et les nécessités de service ont-elles été prises en compte ?",
                "À l'issue d'une activité dans l'une des réserves visées ou des fonctions SNU, le retour sur l'emploi précédent ou un emploi équivalent est-il organisé conformément à l'article 20 et aux articles 33 et 34 ? Pour un agent libéré du service national, examiner l'article 33 et la condition de durée de contrat de l'article 34.",
                "Le contrat est-il un CDI ou un CDD dont le terme est postérieur à la date à laquelle l'agent peut prétendre au réemploi ? Pour un CDD, seule la période restant à courir peut être couverte, sous réserve des exceptions juridictionnelles expressément mentionnées à l'article 34.",
                "Ne pas appliquer à ces situations le délai de trois mois de l'article 18-1, qui vise uniquement les congés des articles 15, 17 et 18. Ne pas appliquer non plus l'ancien délai d'un mois de l'article 35, abrogé.",
            ),
            "documents": ("Contrat et date de terme", "Convocation ou ordre d'appel au service national ou à l'activité de réserve", "Attestation de libération ou de fin de période", "Décompte annuel des jours de réserve par type", "Justificatif de la réserve sanitaire ou de l'instruction militaire", "Contrat et durée d'engagement SNU le cas échéant", "Demande de reprise et preuve de transmission", "État de l'emploi précédent et des emplois équivalents proposés"),
        },
        "dismissal_after_unpaid_leave": {
            "label": "Licenciement pour impossibilité de réemploi après un congé sans rémunération",
            "keywords": ("licenciement impossibilité de réemploi après congé sans rémunération", "impossibilité de réemploi après congé sans rémunération", "impossibilité de réemploi", "licenciement après congé sans rémunération", "licenciement après congé pour convenances personnelles contractuel", "licenciement après congé création entreprise contractuel"),
            "questions": (
                "Le motif invoqué correspond-il à l'impossibilité de réemploi à l'issue d'un congé sans rémunération prévue au 5° du I de l'article 39-3 ou, pour un contrat de projet, au II du même article ? Quelle version du texte s'applique à la date des faits ?",
                "Quel était le fondement et le type exact de congé sans rémunération ? Les conditions de réemploi de l'article 33 sont-elles applicables à cet agent, notamment la réaffectation dans l'emploi si les nécessités du service le permettent ou, à défaut, la priorité pour un emploi similaire assorti d'une rémunération équivalente ?",
                "Les exceptions de l'article 33 concernant certains agents recrutés sur les fondements L. 333-1, L. 333-12 ou L. 343-1 pour les congés pour convenances personnelles ou création d'entreprise sont-elles pertinentes ?",
                "Les démarches de recherche de réemploi, les emplois examinés, les nécessités du service et les raisons concrètes de l'impossibilité sont-ils établis et communiqués ?",
                "Le mécanisme de reclassement de l'article 39-5 exclut le 5° du I ainsi que les licenciements relevant du II (contrat de projet) et du III (emplois L. 343-1) de l'article 39-3 : ne pas le présenter comme une étape obligatoire. Pour un contrat de projet, distinguer aussi la rupture anticipée de l'article 38-2, possible à l'initiative de l'employeur après un an uniquement si le projet ne peut être réalisé ou si son résultat est atteint avant le terme. Vérifier l'entretien préalable, la consultation CCP applicable, la notification et le préavis selon les articles 42, 42-1 et 40.",
            ),
            "documents": ("Contrat et fondement légal du recrutement", "Demande et décision de congé sans rémunération", "Date de fin du congé et demande de réemploi", "Historique des emplois et postes examinés", "Éléments relatifs aux nécessités du service", "Analyse de priorité pour un emploi similaire et rémunération équivalente", "Convocation, avis de la CCP et décision motivée", "Calcul du préavis et preuve de notification"),
        },
        "union_mandate_nonrenewal": {
            "label": "Non-renouvellement du contrat d'un agent investi d'un mandat syndical",
            "keywords": ("non-renouvellement agent mandat syndical", "non renouvellement mandat syndical", "non-renouvellement représentant syndical contractuel", "non-renouvellement agent investi d'un mandat syndical", "mandat syndical"),
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
                "L'inaptitude définitive à occuper l'emploi a-t-elle été constatée par un médecin agréé après un congé entrant dans le champ de l'article 13 III du décret n° 88-145 ? Distinguer inaptitude temporaire et définitive.",
                "L'agent a-t-il été recruté sur un emploi permanent en application de L. 332-8, en CDI ou en CDD dont le terme est postérieur à la date de la demande de reclassement ? Vérifier cette condition avant d'affirmer qu'il bénéficie du dispositif de reclassement de l'article 13 III.",
                "Les emplois proposés relèvent-ils des services de l'autorité qui a recruté l'agent, de la même catégorie hiérarchique ou, à défaut, d'une catégorie inférieure avec accord exprès, et sont-ils adaptés à l'état de santé et compatibles avec les compétences ? L'offre est-elle écrite et précise ?",
                "L'entretien préalable a-t-il été organisé selon l'article 42, avec convocation au moins cinq jours ouvrables avant et possibilité d'accompagnement ? La CCP a-t-elle été consultée avant la notification de la décision (R. 272-19) ?",
                "La lettre de licenciement invite-t-elle l'agent à présenter une demande écrite de reclassement dans un délai égal à la moitié du préavis de l'article 40 et précise-t-elle les conditions de présentation des offres ?",
                "Si une demande de reclassement a été déposée mais qu'aucune offre ne peut être faite avant la fin du préavis, l'agent a-t-il été placé en congé sans rémunération pour trois mois maximum, avec suspension de la date d'effet du licenciement ?",
                "Le licenciement a-t-il été différé jusqu'à l'expiration des dix semaines suivant les congés visés à l'article 10, le cas échéant jusqu'à l'épuisement des droits à congé maladie rémunéré, et l'agent a-t-il pu demander communication de son dossier médical et individuel (article 13 IV et V) ?",
                "En cas d'impossibilité de reclassement, les motifs ont-ils été portés à la connaissance de la CCP (article 39-5 V et article 13 III, selon le fondement applicable) ?",
            ),
            "documents": ("Avis du médecin agréé concluant à l'inaptitude définitive", "Contrat et fondement légal du recrutement", "Avis et recommandations médicales utiles", "Inventaire des emplois recherchés", "Offres écrites et réponses de l'agent", "Convocation et compte rendu de l'entretien préalable", "Demande écrite de reclassement et calcul du délai", "Calcul du préavis", "Dossier médical et individuel communiqué", "Avis de la CCP et preuve de notification"),
        },
        "discipline": {
            "label": "Conseil de discipline d'un agent contractuel",
            "keywords": ("sanction disciplinaire", "conseil de discipline", "exclusion temporaire de quatre jours", "exclusion temporaire de quatre à quinze jours", "exclusion temporaire de seize jours", "licenciement disciplinaire", "sanction autre que avertissement", "sanction autre que le blâme"),
            "questions": (
                "Quelle sanction précise est envisagée au regard de l'article 36-1 du décret n° 88-145 ?",
                "S'agit-il d'une exclusion de quatre jours ou plus ou d'un licenciement disciplinaire ? L'avertissement, le blâme et l'exclusion de trois jours au maximum ne relèvent pas de la saisine disciplinaire de la CCP.",
                "La procédure respecte-t-elle le délai de prescription de trois ans à compter de la connaissance effective des faits, sous réserve de l'interruption prévue en cas de poursuites pénales ?",
                "L'article 37-1 du décret n° 88-145 rend applicables au conseil de discipline les articles 3, 4, 6 à 14, 16, 17, 30 et 30-1 du décret n° 89-677 : information écrite sur les faits, accès intégral au dossier, délai suffisant, pièces numérotées, convocation au moins quinze jours avant la séance, observations, témoins et assistance. Ces garanties sont-elles documentées ?",
                "Le conseil de discipline statue-t-il dans les deux mois de sa saisine, délai ramené à un mois en cas de suspension, sous réserve des prolongations légales liées au report ; l'avis est-il communiqué sans délai et la décision finale motivée (décret n° 89-677, art. 13 et 14) ?",
                "La composition du conseil respecte-t-elle l'article 37-2 du décret n° 88-145, notamment la présidence par un magistrat administratif et la représentation paritaire ?",
                "Pour les sanctions des 3° et 4° de l'article 36-1, le rapport de saisine décrit-il les faits et leurs circonstances et l'agent a-t-il été invité à en prendre connaissance (article 37-4) ?",
            ),
            "documents": ("Rapport disciplinaire décrivant les faits et circonstances", "Dossier individuel et pièces annexes", "Preuve d'information sur le droit à communication du dossier", "Convocation et preuve de transmission du rapport", "Observations et pièces de défense", "Projet de sanction et éléments de proportionnalité"),
        },
        "refusal_individual_decision": {
            "label": "Saisine de la CCP à la demande de l'agent contractuel",
            "keywords": ("recours ccp", "saisine ccp à la demande", "refus de temps partiel agent contractuel", "litige temps partiel contractuel", "contestation compte rendu entretien professionnel contractuel", "contestation du compte rendu d'entretien professionnel", "révision compte rendu entretien professionnel contractuel", "révision du compte rendu d'entretien professionnel", "refus utilisation compte personnel formation contractuel", "refus de télétravail agent contractuel", "interruption télétravail agent contractuel", "refus congé compte épargne temps contractuel"),
            "questions": (
                "La décision contestée figure-t-elle exactement parmi les cas énumérés à R. 272-21 : temps partiel, révision de l'entretien professionnel, CPF, télétravail ou compte épargne-temps ?",
                "La saisine est-elle demandée par l'agent contractuel intéressé et dans les délais applicables ?",
                "Pour la révision d'un compte rendu d'entretien professionnel, l'agent a-t-il été recruté sur un emploi permanent en CDI ou en CDD de plus d'un an, y compris par contrat de projet (article 1-3 du décret n° 88-145) ?",
                "Pour cette révision, la demande a-t-elle été formée dans les quinze jours francs suivant la notification, l'autorité a-t-elle répondu dans les quinze jours francs suivant sa réception, et la CCP a-t-elle été saisie dans le mois suivant la notification de la réponse ?",
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
        "danger_grave_imminent": {
            "label": "Danger grave et imminent, alerte et droit de retrait",
            "keywords": ("danger grave et imminent", "dgi", "registre spécial", "droit de retrait", "alerte danger grave"),
            "questions": (
                "Quels faits précis, datés et localisés caractérisent le danger allégué, et quels agents ou activités sont exposés ?",
                "L'agent ou le représentant a-t-il alerté immédiatement l'autorité territoriale et le représentant a-t-il consigné son avis dans le registre spécial prévu à cet effet ?",
                "Une enquête immédiate a-t-elle été menée conjointement par l'autorité territoriale et le représentant ayant signalé le danger ?",
                "Quelles mesures conservatoires ont été prises, et comment l'autorité a-t-elle motivé un éventuel désaccord sur la réalité du danger ou les mesures à prendre ?",
                "En cas de désaccord persistant, la formation spécialisée a-t-elle été réunie dans les conditions et délais applicables, avec intervention éventuelle de l'inspection du travail ?",
                "La situation individuelle de chaque agent et les conditions légales du droit de retrait ont-elles été examinées sans présumer automatiquement de sa validité ou de son invalidité ?",
            ),
            "documents": ("Extrait du registre spécial de danger grave et imminent", "Signalement daté et éléments factuels", "Compte rendu d'enquête conjointe", "Mesures conservatoires et plan de mise en sécurité", "Échanges motivés entre l'autorité et les représentants", "Convocations, avis et suites données à la réunion de la formation spécialisée"),
        },
        "visites": {
            "label": "Visites de locaux et situations de travail",
            "keywords": ("visite de locaux", "visite de service", "visite de site", "visite de travail", "visites de prévention"),
            "questions": (
                "La visite a-t-elle été inscrite dans le programme de travail de la formation spécialisée et son objet a-t-il été défini ?",
                "Les représentants participants, les services visités et les conditions d'accès ont-ils été déterminés avec l'autorité territoriale ?",
                "Les agents rencontrés ont-ils pu s'exprimer librement, sans présence hiérarchique susceptible d'altérer leurs réponses ?",
                "Les constats distinguent-ils les faits observés, les déclarations recueillies et les analyses ou hypothèses ?",
                "Les suites, responsables, échéances et modalités de suivi des préconisations sont-ils tracés ?",
            ),
            "documents": ("Programme et ordre de mission de la visite", "Grille de visite et constats factuels", "Comptes rendus anonymisés des échanges", "Photographies ou pièces utiles autorisées", "Plan d'actions avec responsables et échéances", "Suivi des recommandations antérieures"),
        },
        "enquete": {
            "label": "Enquête après accident de service ou événement grave",
            "keywords": ("enquête après accident", "enquête accident", "enquête après incident", "enquête après agression", "analyse accident du travail"),
            "questions": (
                "L'événement entre-t-il dans le champ justifiant une enquête de la formation spécialisée et les représentants ont-ils été associés ?",
                "La méthode recherche-t-elle les causes immédiates et organisationnelles plutôt que la seule faute individuelle ?",
                "Les témoignages, horaires, équipements, consignes et conditions réelles de travail ont-ils été recueillis de manière contradictoire et proportionnée ?",
                "Les données personnelles et médicales non nécessaires ont-elles été écartées ou protégées ?",
                "Les mesures correctives portent-elles sur la prévention à la source et leur efficacité sera-t-elle réévaluée ?",
            ),
            "documents": ("Déclaration et rapport d'événement expurgés des données non nécessaires", "Chronologie factuelle et éléments matériels", "Compte rendu d'enquête et analyse des causes", "Mesures correctives, responsables et échéances", "Évaluation de l'efficacité des mesures"),
        },
        "duerp_programme": {
            "label": "DUERP et programme annuel de prévention",
            "keywords": ("mise à jour duerp", "document unique d'évaluation des risques", "programme annuel de prévention", "papripact", "plan annuel de prévention"),
            "questions": (
                "Le DUERP couvre-t-il toutes les unités de travail, les risques réels et les situations de travail dégradées ?",
                "Quelle méthode d'évaluation, quelle date de mise à jour et quelle association des agents et représentants sont documentées ?",
                "Les actions du programme annuel sont-elles hiérarchisées, budgétées, assorties d'un responsable et d'une échéance ?",
                "Les risques persistants, actions reportées et écarts entre prévisions et réalisations sont-ils explicitement présentés ?",
                "Quels indicateurs permettent de mesurer la réduction effective de l'exposition aux risques ?",
            ),
            "documents": ("DUERP complet et historique de ses versions", "Cartographie des unités de travail et méthode d'évaluation", "Programme annuel de prévention ou document équivalent", "Budget, responsables, échéances et indicateurs", "Bilans d'avancement et justification des actions non réalisées"),
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
        "danger_grave_imminent": "danger grave imminent alerte registre spécial droit de retrait enquête conjointe",
        "visites": "visite locaux services conditions réelles de travail constats prévention suivi préconisations",
        "enquete": "enquête accident service incident agression analyse causes prévention",
        "duerp_programme": "document unique évaluation risques professionnels DUERP programme annuel prévention PAPRiPACT",
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
