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

Pour les sujets de santé, sécurité et conditions de travail, l'orientation reste indéterminée tant que l'existence de la formation spécialisée n'est pas renseignée. Le seuil et les cas de création sont prévus à l'article L. 251-9 du CGFP. Son existence ne suffit pas à elle seule : son périmètre et les règles de compétence doivent encore être contrôlés.

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
- **Convocation** : quinze jours au moins avant la séance, ramenés à huit jours en cas d'urgence (R. 254-38).
- **Documents** : toutes les pièces nécessaires doivent être transmises aux titulaires et suppléants au plus tard huit jours avant la séance (R. 254-39). L'urgence ne réduit pas ce délai dans le calcul fourni.
- **Demande écrite de réunion du CST** : lorsque la demande émane d'au moins la moitié des représentants titulaires, le CST doit se réunir dans les deux mois (R. 254-35). Le helper calcule une date butoir de deux mois calendaires à partir de la date de réception déclarée.
- **FS non réunie depuis neuf mois** : en FPT, si la FS n'a pas été réunie depuis au moins neuf mois, les représentants titulaires peuvent saisir l'agent chargé des fonctions d'inspection dans les conditions de R. 254-35. L'outil vérifie séparément le délai et le seuil numérique (R. 254-42).
- **Après demande de l'agent chargé des fonctions d'inspection** : l'autorité territoriale convoque une réunion dans les huit jours de la réception de cette demande ; la réunion doit avoir lieu dans le mois (R. 254-42).

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
