# Qualification indicative des sujets CST

## Périmètre

Le module `backend/app/cst_qualification.py` propose une qualification documentaire par déclencheurs lexicaux, à partir des dispositions du Code général de la fonction publique en vigueur au 27 novembre 2026.

Il distingue les trois natures suivantes :

- **Consultation pour avis** : CGFP, article R. 253-7.
- **Débat annuel** : CGFP, articles R. 253-8 et R. 253-9.
- **Information** : CGFP, article R. 253-10.

Le référentiel R. 253-7 intègre les 24 rubriques de sa version entrée en vigueur le 1er août 2026, notamment la liste des postes à responsabilité ouvrant une formation de professionnalisation (24°). Les rubriques de débat et d'information suivent les versions en vigueur depuis le 1er août 2026.

## Limites fonctionnelles et juridiques

Une correspondance de mots-clés est un **candidat à vérifier**, jamais une conclusion. Le moteur ne déduit pas seul :

- que le document est un projet de décision ou un projet soumis à avis ;
- que les conditions précises de l'article cité sont réunies ;
- que le sujet relève effectivement du CST de la collectivité ;
- qu'une autre disposition spéciale ne modifie pas l'analyse ;
- que le sujet relève du CST ou de la formation spécialisée.

Pour les sujets de santé, sécurité et conditions de travail, l'orientation reste indéterminée tant que l'existence de la formation spécialisée n'est pas renseignée. En FPT, une FS est obligatoire dans les collectivités et établissements employant au moins 200 agents ; en dessous, elle peut être créée par délibération lorsque des risques professionnels particuliers le justifient. Une FS est instituée dans chaque SDIS sans condition d'effectif (CGFP L. 251-9). Son existence ne suffit pas à elle seule : son périmètre et les règles de compétence doivent encore être contrôlés.

## Délais de séance

La fonction `calculate_cst_meeting_deadlines` calcule des dates cibles par soustraction de jours calendaires :

- convocation : 15 jours avant la séance, ramenés à 8 jours en cas d'urgence (R. 254-38) ;
- documents nécessaires : au plus tard 8 jours avant la séance (R. 254-39).

L'urgence ne modifie dans ce calcul que le délai de convocation. Le calcul ne traite pas les cas contentieux de computation, les circonstances particulières ou les éventuelles règles spéciales. Il ne doit pas être présenté comme une validation de régularité de la convocation.

## Références officielles

- [CGFP, article R. 253-7](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000054087794)
- [CGFP, article R. 253-8](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549725)
- [CGFP, article R. 253-9](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549727)
- [CGFP, article R. 253-10](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549731)
- [CGFP, article L. 251-9](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000044427304)
- [CGFP, article R. 254-38](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550057)
- [CGFP, article R. 254-39](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550061)

## Évolutions non couvertes

Cette première livraison ne qualifie pas encore automatiquement les consultations propres aux autres textes, les compétences détaillées de la formation spécialisée, les demandes d'inscription à l'ordre du jour, les règles de quorum, les avis défavorables ou les suites données aux avis. Ces sujets nécessitent des règles dédiées et des tests juridiques distincts.


## Demandes d'inscription à l'ordre du jour

L'API de préparation CST peut recevoir, en complément du sujet :

- `titular_representatives` : nombre total de représentants titulaires du personnel ;
- `requesting_titular_representatives` : nombre de titulaires ayant demandé l'inscription ;
- `requested_topic_in_competence` : appréciation humaine facultative indiquant si le sujet relève de la compétence du CST ou de la formation spécialisée.

Le helper `assess_cst_agenda_request` applique le seuil d'au moins la moitié des représentants titulaires prévu par l'article R. 254-43 du CGFP. Il distingue le seuil non atteint, la compétence à vérifier, la compétence contestée et le cas où l'inscription est indiquée comme requise sous réserve des données déclarées.

La compétence n'est jamais déduite par mots-clés. Si elle n'est pas renseignée, le résultat reste `COMPETENCE_TO_VERIFY`. Le résultat porte toujours `legal_conclusion: false`. Le calcul est une aide de contrôle fondée sur les effectifs saisis, qui doivent être vérifiés.

Source officielle : [CGFP, article R. 254-43](https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000044416551/LEGISCTA000050550047/2026-06-17/).


## Fonctionnement et calendrier des réunions CST / FS

Les fonctions de contrôle sont des aides de calcul à partir des données saisies. Elles ne constatent pas automatiquement une irrégularité.

- **CST — périodicité** : au moins deux réunions par an (R. 254-35).
- **CST sans formation spécialisée** : une réunion supplémentaire par an doit porter sur la santé, la sécurité et les conditions de travail, hors cas particuliers prévus par R. 254-36. Le contrôle distingue donc les réunions CST ordinaires et cette réunion supplémentaire.
- **Formation spécialisée du CST** : au moins trois réunions par an en FPT (R. 254-37).
- **Convocation** : elle fixe l'ordre du jour, précise les points soumis au vote et est adressée quinze jours au moins avant la séance, délai ramené à huit jours en cas d'urgence (R. 254-38). L'interface propose un contrôle déclaratif des points soumis au vote.
- **Secrétaire de la FS** : il doit être consulté avant la définition de l'ordre du jour et peut proposer l'inscription de points (R. 254-40). L'interface demande si cette consultation préalable est déclarée effectuée ; elle ne vérifie pas la réalité de l'échange.
- **Documents** : toutes les pièces nécessaires doivent être transmises aux titulaires et suppléants au plus tard huit jours avant la séance (R. 254-39). L'urgence ne réduit pas ce délai dans le calcul fourni.
- **Demande écrite de réunion du CST** : lorsque la demande émane d'au moins la moitié des représentants titulaires, le CST doit se réunir dans les deux mois (R. 254-35). Le helper calcule une date butoir de deux mois calendaires à partir de la date de réception déclarée.
- **FS non réunie depuis neuf mois** : en FPT, si la FS n'a pas été réunie depuis au moins neuf mois, les représentants titulaires peuvent saisir l'agent chargé des fonctions d'inspection dans les conditions de R. 254-35. L'outil vérifie séparément le délai et le seuil numérique propres aux représentants titulaires de la FS, distincts des effectifs du CST (R. 254-42).
- **Après demande de l'agent chargé des fonctions d'inspection** : l'autorité territoriale convoque une réunion dans les huit jours de la réception de cette demande ; la réunion doit avoir lieu dans le mois (R. 254-42). Les motifs d'un éventuel refus sont communiqués aux membres de la FS. En l'absence de réponse ou si le refus est insuffisamment motivé, l'agent chargé des fonctions d'inspection saisit l'inspecteur du travail.

Les échéances de huit jours, quinze jours, un mois et deux mois sont calculées comme des dates calendaires par les helpers. La computation doit être vérifiée pour le dossier concret ; aucune validation automatique de régularité n'est émise. Pour les périodicités annuelles, un nombre inférieur au minimum pendant une année encore en cours n'est pas présenté comme un manquement définitif.

Références officielles :
- [CGFP, article R. 254-35](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550051)
- [CGFP, article R. 254-36](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550053)
- [CGFP, article R. 254-37](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550055)
- [CGFP, article R. 254-38](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550057)
- [CGFP, article R. 254-39](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550061)
- [CGFP, article R. 254-40](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550063)
- [CGFP, article R. 254-42](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550069)
- [CGFP, article R. 254-43](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050550071)


## Consultations propres à la formation spécialisée et articulation CST / FS

Pour la fonction publique territoriale, le référentiel FS indicatif couvre désormais les sujets des articles R. 253-24 à R. 253-27 :

- **R. 253-24** : questions de santé physique et mentale, hygiène et sécurité, organisation du travail, télétravail, déconnexion, amélioration des conditions de travail et élaboration / mise à jour du DUERP, sous réserve de l'exclusion des questions mentionnées à R. 253-7.
- **R. 253-25** : projets importants d'aménagement modifiant la santé, la sécurité ou les conditions de travail, hors cas visé au 2° de R. 253-7 ; projets importants de nouvelles technologies susceptibles d'avoir des conséquences sur la santé et la sécurité.
- **R. 253-26** : mesures de mise, remise ou maintien au travail des personnes visées par le texte, notamment aménagement de poste ; mesures générales de reclassement des agents reconnus inaptes.
- **R. 253-27** : programme annuel de prévention des risques professionnels et d'amélioration des conditions de travail, établi à partir de l'analyse des risques et des informations santé-sécurité du RSU.

Les mots-clés ne sont que des déclencheurs documentaires. Les exclusions, la nature du projet, son importance, son périmètre et les conditions propres à chaque article doivent être examinés humainement.

### Règles d'articulation

- **Sans FS instituée** : le CST exerce les compétences attribuées à la FS dans les sous-sections 1 à 4 de la section 2 (R. 253-79).
- **Compétence partagée** : le CST est seul consulté sur une question ou un projet relevant de ses propres attributions et qui aurait également pu relever de la FS (R. 253-80).
- **Substitution exceptionnelle** : avant examen par la FS, un projet ou une question soumis à consultation obligatoire de celle-ci peut, sous les conditions de R. 253-81, être inscrit directement à l'ordre du jour du CST. En FPT, si l'inscription est à l'initiative du président du CST, elle nécessite l'accord de la moitié des membres représentants du personnel. L'inscription peut également être à l'initiative de la moitié de ces membres. L'avis du CST se substitue alors à celui de la FS.

L'outil demande une qualification humaine séparée des attributions propres du CST, de la consultation obligatoire de la FS et de l'état d'examen par la FS. Pour R. 253-81, il contrôle les effectifs et soutiens déclarés. Il ne vérifie ni la réalité de l'accord, ni la qualité des membres, ni la portée exacte du projet. Le résultat conserve toujours `legal_conclusion: false`.

Références officielles :
- [CGFP, article R. 253-24](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549777)
- [CGFP, article R. 253-25](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549779)
- [CGFP, article R. 253-26](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549781)
- [CGFP, article R. 253-27](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549783)
- [CGFP, article R. 253-79](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549927)
- [CGFP, article R. 253-80](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051968704)
- [CGFP, article R. 253-81](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549931)


## Procédures opérationnelles de la formation spécialisée

Le helper `qualify_fs_operational_topic` ajoute un repérage indicatif des procédures prévues par le CGFP. Il est exposé dans la préparation FS et, lorsque l'utilisateur indique l'absence de FS, dans la préparation CST avec une orientation à vérifier.

### Référentiel couvert

- **Analyse et prévention des risques** : analyse des expositions, risques particuliers, prévention, harcèlement et violences sexistes et sexuelles (R. 253-37 à R. 253-40).
- **Visites** : délibération définissant objet, secteur géographique et délégation ; composition de la délégation ; accès aux locaux ; accord écrit préalable pour accéder au domicile d'un télétravailleur ; rapport à la FS (R. 253-41 à R. 253-47).
- **Accident grave ou potentiellement grave** : réunion de la FS compétente dans les plus brefs délais (R. 253-48).
- **Enquêtes** : cas d'accident grave ou de maladie professionnelle grave, danger grave révélé, ou répétition d'accidents/maladies sur des postes ou fonctions identiques ou similaires ; composition de la délégation et information de la FS sur les conclusions et suites (R. 253-49 à R. 253-52).
- **Nuisances d'un établissement voisin** : possibilité de demander une audition ou des observations de l'employeur voisin par l'intermédiaire de l'autorité territoriale (R. 253-53).
- **Expert certifié** : risque grave ou projet important hors réorganisation, conditions de recours, frais à la charge de l'employeur public, délai maximal d'un mois dans le cas FPT où l'expertise est demandée par le président, motivation du refus et procédure de désaccord sérieux et persistant (R. 253-54 à R. 253-57).
- **Danger grave et imminent** : alerte immédiate, registre spécial, contenu de l'inscription, enquête immédiate, réunion d'urgence sous 24 heures en cas de divergence, rôle de l'inspection du travail et réponse motivée sous quinze jours après rapport dans la procédure FPT (R. 253-58 à R. 253-60 et R. 253-62 à R. 253-63).

### Précautions juridiques intégrées

- Les déclencheurs lexicaux produisent uniquement des candidats ; ils ne déterminent ni la gravité d'un accident, ni le caractère répété, ni l'existence d'un risque grave, ni l'applicabilité d'une expertise.
- La procédure DGI FPT est distinguée des procédures propres aux comités sociaux d'administration et d'établissement. Le code ne doit pas appliquer automatiquement R. 253-61 ou R. 253-65 à une collectivité territoriale.
- Le registre spécial DGI de R. 253-58 et R. 253-59 est distinct du registre santé et sécurité au travail consulté par la FS au titre de R. 253-35.
- Les délais de 24 heures et de quinze jours sont des délais procéduraux déclenchés par des événements définis par le texte ; ils ne sont pas assimilés à de simples échéances de réunion.
- En l'absence de FS, le résultat demande de vérifier les compétences exercées par le CST et les dispositions visant expressément le comité en l'absence de formation spécialisée. Il ne transpose pas mécaniquement toutes les dispositions FS au CST.

Sources officielles : [CGFP, chapitre III — attributions des formations spécialisées](https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000044416551/LEGISCTA000050549693/2026-08-01/), [CGFP, procédure DGI R. 253-58 à R. 253-65](https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000044416551/LEGISCTA000050549863/).


## Registre santé-sécurité, rapports et suivi des suites

Le repérage opérationnel couvre également les obligations d'information, de rapport et de suivi prévues par les articles suivants :

- **R. 253-27 — programme annuel de prévention en FPT** : la formation spécialisée du CST est saisie chaque année pour avis sur le programme annuel de prévention. Celui-ci est établi à partir de l'analyse prévue à R. 253-38 et des informations santé-sécurité du rapport social unique ; il détaille les actions, leurs conditions d'exécution et leur coût estimé. La FS peut proposer des priorités et des mesures supplémentaires ; les motifs des mesures non réalisées sont annexés au programme.
- **R. 253-35 — registre santé et sécurité au travail** : la FS prend connaissance des observations et suggestions inscrites au registre coté, relatives à la prévention et à l'amélioration des conditions de travail. Ce registre est distinct du registre spécial DGI.
- **R. 253-47 — rapport de visite** : les missions de la délégation donnent lieu à un rapport présenté à la FS.
- **R. 253-52 — suites des enquêtes** : la FS est informée des conclusions de chaque enquête et des suites qui leur sont réservées.

Les checklists invitent à distinguer :
1. le constat ou signalement initial ;
2. le rapport de la délégation ou les conclusions de l'enquête ;
3. les propositions ou avis de la FS ;
4. la décision de l'autorité territoriale ;
5. les mesures effectivement réalisées, les échéances et les motifs des mesures non réalisées.

**Limite de la version actuelle :** Dikévia génère des points de contrôle et des éléments à demander. Il ne conserve pas encore un registre persistant des recommandations, responsables, échéances et états d'avancement. Ce suivi durable nécessitera un module de dossiers avec droits d'accès, cloisonnement organisationnel, historique et règles de conservation ; il ne doit pas être simulé par une simple fiche temporaire.

Sources officielles : [CGFP R. 253-27](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549783/), [CGFP R. 253-35](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549803/), [CGFP R. 253-47](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549833/), [CGFP R. 253-52](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000050549847/).
