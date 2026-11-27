# Index des documents historiques et des sources de vérité

## Sources de vérité à utiliser

1. [README.md](../README.md) — vue d'ensemble du dépôt.
2. [00_DEVELOPMENT_START_HERE.md](00_DEVELOPMENT_START_HERE.md) — démarrage et consignes de contribution.
3. [08_COMMERCIAL_MODEL.md](08_COMMERCIAL_MODEL.md) — modèle commercial actuel.
4. [54_AGENT_UNION_ACCESS_MODEL.md](54_AGENT_UNION_ACCESS_MODEL.md) — droits Agent/Syndicat.
5. [55_CST_TOPIC_QUALIFICATION.md](55_CST_TOPIC_QUALIFICATION.md) — qualification candidate CST/formation spécialisée.
6. [56_CAP_CCP_QUALIFICATION.md](56_CAP_CCP_QUALIFICATION.md) — qualification candidate CAP/CCP.
7. [57_ETAT_CONSOLIDE_2026-11-27.md](57_ETAT_CONSOLIDE_2026-11-27.md) — état consolidé, preuves et limites.

## Documents historiques à ne pas traiter comme configuration ou état courant

| Document | Statut |
|---|---|
| 17_V3_7_KEYCLOAK.md | Ancienne intégration Keycloak ; Auth0 est désormais le fournisseur par défaut. |
| 24_V3_17_SAAS_BILLING.md | Anciennes offres Stripe ; paiements et checkout désactivés. |
| 32_V3_22_PRODUCTION_READINESS.md | Ancien rapport de préparation production, non valable pour l'état actuel. |
| 33_V3_24_ESPACE_COMMERCIAL_CLIENT.md | Ancienne console commerciale et facturation Stripe ; modèle actuel sans offre collectivité ni paiement actif. |
| 39_LIVRAISON_DEVELOPPEUR_V3_30.md | Ancienne livraison V3.30. |
| 40_INSTANCE_PRIVEE_10_COMPTES.md | Ancien mode privé à 10 membres, désactivé par défaut et non représentatif du catalogue actuel. |
| 41_PLAN_DEVELOPPEUR_V3_30.md | Ancienne feuille de route V3.30. |
| 42_V3_30_PREUVE_VALIDATION_CI.md | Ancienne preuve CI sur une branche et une PR historiques. |
| 44_PREPARATION_RECETTE_DEVELOPPEUR.md | Anciennes instructions de branches/PR ; le travail se fait directement sur main. |
| 46_BETA_PRIVEE_CHECKLIST_MISE_EN_SERVICE.md | Checklist datée du 23 novembre ; utiliser le document 57 pour l'état actuel. |
| 47_AUTH0_MIGRATION.md | Historique de migration Auth0 ; ne pas relancer la migration ni créer un nouveau tenant. |
| 50_BETA_READINESS_2026-11-24.md | Ancien état de bêta, remplacé par le document 57. |

Les documents fondamentaux plus anciens (01 à 16 et 18 à 23) peuvent conserver des exigences ou du contexte utiles, mais leurs hypothèses d'implémentation et de calendrier ne prévalent pas sur les sources de vérité listées ci-dessus.

## Archive de fichiers racine

Les anciens modules, scripts, fichiers Compose, index et documents qui se trouvaient à la racine ont été déplacés dans [archive/legacy-root/](../archive/legacy-root/). Ils sont conservés pour traçabilité, ne sont pas importés par le runtime et sont exclus du kit développeur.
