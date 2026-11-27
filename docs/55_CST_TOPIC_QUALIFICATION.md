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
