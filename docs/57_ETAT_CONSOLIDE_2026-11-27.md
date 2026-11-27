# Dikévia — état consolidé du projet

**Date de référence : 27 novembre 2026**  
**Branche de travail : `main` uniquement**  
**Commit de référence au démarrage de cette consolidation : `8bf70bf3737ca06675a9ed05f427c640f65b5044`**

Ce document est le point de situation opérationnel. Il prévaut sur les anciens états de livraison datés lorsqu'ils décrivent un état antérieur. Il ne constitue ni une recette complète, ni une certification juridique, ni une autorisation de mise en production.

## 1. Règles de conduite du projet

- Toute évolution de code et de documentation se fait directement sur `main`.
- Ne pas créer de branche de développement, ne pas fusionner globalement une ancienne branche et ne pas réécrire l'historique.
- Ne pas déployer ni modifier les services ou bases de production sans autorisation explicite.
- Aucun paiement, fournisseur payant, API payante ou opération susceptible de générer des frais ne doit être activé sans accord explicite.
- Les tests automatisés, les contrôles staging et la validation juridique humaine sont trois niveaux distincts ; ne pas les confondre.
- Auth0 est le fournisseur d'identité retenu. Le chantier Auth0 a été déclaré terminé par le porteur du projet ; ne pas le rouvrir ni revenir à Keycloak comme solution cible.
- Keycloak et les références historiques restantes doivent être traités comme des résidus à inventorier, pas comme une instruction de réactivation.
- Le chantier de benchmark de qualité conversationnelle est réservé à la revue prévue avec les développeurs du porteur du projet. Ne pas le présenter comme réalisé.
- Les sujets explicitement reportés (page Abonnement/billing, cas NBI et module défense dédié) restent hors du présent lot.

## 2. État du code et de la CI

### Référence de dépôt

- Dépôt : `dikevia/Dikevia`.
- Branche : `main`.
- Commit contrôlé : `8bf70bf3737ca06675a9ed05f427c640f65b5044`.
- CI générale associée : run [46006150361](https://github.com/dikevia/Dikevia/actions/runs/46006150361), conclusion `success`.
- Le contrôle rapporté pour ce commit comprend 1 489 tests réussis, sans échec, avec un avertissement de dépréciation Starlette/httpx.
- Le succès CI ne prouve pas le fonctionnement des fournisseurs IA en conditions réelles, la pertinence juridique des réponses, la recette sur appareil Android ni l'alignement de la production.

### Correctif de consolidation CI

La migration `033_chat_daily_question_quota_repair.sql` existe et a été appliquée sur la base de staging. Elle répare de façon additive la table de quota quotidien, active et force RLS et accorde au rôle applicatif les droits de colonnes nécessaires. Avant cette consolidation, le workflow CI s'arrêtait à la migration 032.

La migration 033 est désormais ajoutée à la séquence PostgreSQL jetable de la CI, après 032. Son exécution effective sera confirmée uniquement par le résultat du prochain run CI. Cette modification CI n'exécute aucune migration sur staging ou production.

## 3. Authentification et environnements

### Auth0

- Auth0 est le fournisseur retenu ; le porteur du projet a confirmé que le chantier est fait.
- Les journaux staging contrôlés montrent le chargement de la configuration Auth0, le retour OIDC et une réponse HTTP 200 de `/api/v1/auth/me`.
- Ces traces démontrent un parcours Auth0 fonctionnel sur le staging au moment du contrôle ; elles ne certifient pas tous les scénarios de session, tous les appareils Android ni la production.
- Ne pas recommencer la migration Auth0 ni réintroduire Keycloak dans le produit.

### Écart d'infrastructure à traiter séparément

- Le service staging Render contrôlé est associé à `main`, en déploiement manuel, et son dernier commit live connu est `e8bd12a`. Le staging n'est donc pas nécessairement à jour avec les derniers développements de `main`.
- Le service de production contrôlé est toujours associé à l'ancienne branche `feature/dikevia-v3.38.5-cgfp-chat` et au commit `198ee805d73381fa8f10683e791ec74cf1d78c97`, pas au `main` courant.
- Un service Render historique nommé `dikevia-keycloak` reste actif selon le contrôle précédent. Le Blueprint `render.yaml` et certaines configurations/documentations contiennent encore des références Keycloak et à l'ancienne branche.
- Cet écart est un risque de gouvernance et de cohérence. Aucune suppression, modification de service, migration de production ou bascule de branche n'est incluse dans cette consolidation.

## 4. Corpus juridique et recherche

### Corpus staging

Les éléments suivants ont été contrôlés sur staging, sans toucher à la production :

- Décisions CAA/TA : 506 décisions importées, zéro rejet au run d'import staging contrôlé.
- Embeddings locaux : 7 981 chunks vectorisés après l'import CAA/TA ; le corpus Service-Public a ensuite ajouté 1 286 chunks et embeddings compatibles.
- Fiches Service-Public : 199 fiches importées ; 1 185 références extraites ; audit de provenance `PASS`, sans référence malformée ou identifiant Légifrance mal étiqueté.
- Total contrôlé après l'import Service-Public : 8 020 vecteurs présents, zéro restant à générer.
- Les embeddings ont été générés localement, sans API d'embeddings payante.

### Recherche hybride

Le dépôt contient une recherche lexicale PostgreSQL et vectorielle pgvector, avec fusion RRF et filtres de périmètre/temporalité. Le flag de recherche vectorielle a été activé sur le staging après autorisation. Le câblage du code est présent.

Limite : les contrôles disponibles n'ont pas permis de prouver une requête chatbot authentifiée de bout en bout avec le moteur hybride réellement actif. Les résultats d'audit vectoriel ne certifient pas la pertinence sémantique ou juridique. Le benchmark humain prévu reste à faire.

## 5. Moteur juridique et outils syndicaux

### Fondations et fiabilité

- Correctifs du fournisseur IA intégrés sur `main` : retries bornés, bascule contrôlée sur certaines erreurs temporaires, pas de fallback abusif sur les erreurs d'authentification/quota/client, et statut de disponibilité distingué d'une génération réellement réussie.
- Tests simulés et CI associés réussis sur le commit `e8bd12a` ; déploiement staging de ce correctif confirmé.
- Les erreurs réelles historiques Gemini et Neon AI Gateway ont été observées. Neon AI Gateway a répondu 403 car un service payant est requis ; il reste désactivé.
- La génération réelle doit être surveillée séparément des tests simulés.

### CST et formation spécialisée

- Le module de qualification CST/FS est intégré dans `backend/app/cst_qualification.py` et exposé via `backend/app/instances.py` et l'interface.
- Il couvre des candidats de consultation, débat et information, des contrôles de réunions et délais, des demandes d'inscription à l'ordre du jour et plusieurs situations opérationnelles FS (prévention, visites, accidents, enquêtes, nuisances, expertise, danger grave et imminent).
- Les résultats sont des candidats/checklists à vérifier, pas des conclusions juridiques.
- Les outils ne constituent pas encore un registre durable des avis, suites, échéances et dossiers.

### CAP et CCP

- Le module `prepare_instance` couvre des cas de saisine CAP/CCP, discipline, recours sur entretien professionnel, licenciement, reclassement, congés et réemploi des contractuels.
- Les règles différencient fonctionnaires et contractuels et tiennent compte de la version des textes.
- Le moteur produit des pistes de qualification et des contrôles, pas une décision sur la compétence de la commission ni sur la légalité d'une mesure.
- La documentation dédiée est `docs/56_CAP_CCP_QUALIFICATION.md`.

### Licenciement et réemploi des contractuels

- Les règles du décret n° 88-145 ont été complétées sur les motifs de licenciement, insuffisance professionnelle, reclassement, préavis, protections, entretien, notification, contrats de projet, réemploi après congés et service national/réserves.
- Les dates, le statut, le fondement de recrutement et la version applicable restent déterminants ; les sorties doivent être vérifiées sur le dossier concret.
- La couverture actuelle ne remplace pas un audit humain ni un module complet de défense individuelle.

## 6. Applications et administration

- Le dépôt comporte une application web, une application Android commerciale et une application Android d'administration avec des identifiants de package distincts.
- L'application d'administration doit rester centrée sur la gestion et la supervision ; elle ne doit pas intégrer le chatbot des agents.
- Les APK de développement ou de test ne constituent pas une publication Play Store.
- La recette de l'authentification sur appareils Android réels n'est pas considérée comme certifiée dans le présent état.
- L'audit fonctionnel détaillé des invitations, adhésions, droits, séparation Admin, RLS et parcours mobiles reste à poursuivre.

## 7. Limites et sujets non clôturés

1. **Production non alignée sur main** : l'environnement de production utilise encore une ancienne branche. Ne pas modifier sans décision distincte et plan de migration/retour arrière.
2. **Protection de main** : le contrôle GitHub a indiqué que la branche n'était pas protégée et n'avait pas de vérifications obligatoires. C'est une mesure de gouvernance à mettre en place avec les droits d'administration appropriés ; aucun changement de paramètres n'est effectué ici.
3. **CI migrations** : la migration 033 est maintenant incluse dans le workflow ; attendre le run CI pour constater son résultat.
4. **Documentation historique** : README, checklist de mise en production, documents Keycloak et anciens états de bêta comportent encore des informations périmées. Ils doivent être clairement étiquetés comme historiques ou actualisés sans supprimer les preuves.
5. **Parcours métier** : audit détaillé à terminer sur les droits individuels/syndicaux, quotas serveur, invitations, séparation Admin, isolation multi-organisation et persistance conversationnelle.
6. **Documents agents** : OCR des PDF image et parcours complet d'analyse documentaire restent à développer/valider.
7. **Dossiers et instances** : persistance du suivi des avis, suites, délais, dossiers et historique des actions reste à construire.
8. **RGPD** : la redaction/anonymisation partielle ne vaut pas anonymisation garantie ; politique de rétention/purge, registre, information, contrats de sous-traitance et AIPD si nécessaire restent à formaliser.
9. **IA** : génération réelle, disponibilité fournisseur et pertinence des réponses doivent être contrôlées séparément. Le benchmark de qualité est réservé à la session prévue avec les développeurs.
10. **Billing** : la page Abonnement et l'erreur 500 précédemment observée sont volontairement laissées de côté à la demande du porteur du projet.
11. **NBI et module défense** : sujets reportés, non inclus dans cette consolidation.

## 8. Ordre de travail recommandé

### Priorité 1 — fiabiliser le socle sans toucher à la production
- Confirmer le nouveau run CI avec migration 033.
- Terminer l'audit lecture seule des droits Agent/Syndicat, quotas, invitations, Admin, RLS et conversations.
- Documenter les contradictions entre spécifications, code et migrations sans faire de migration DB non autorisée.
- Protéger `main` lorsque les permissions d'administration le permettront.

### Priorité 2 — consolider le moteur métier
- Compléter les parcours CST/FS/CAP/CCP et leurs tests de non-régression.
- Concevoir le suivi persistant des avis, suites, délais et dossiers.
- Construire le prototype d'analyse documentaire N1 avec traçabilité et limites explicites.
- Ajouter OCR uniquement avec un pipeline contrôlé et des tests de sécurité.

### Priorité 3 — conformité et recette
- Formaliser rétention/purge, registre RGPD, information des personnes et contrats nécessaires.
- Effectuer la revue de qualité juridique humaine prévue.
- Tester les parcours réels web et Android sans assimiler compilation APK et recette utilisateur.
- Préparer séparément tout futur plan d'alignement de production ; aucune bascule ne doit être implicite.

## 9. État de la présente consolidation

Cette consolidation documentaire et CI est effectuée sur `main`. Elle ne change aucune donnée Neon, aucun secret, aucune variable Render, aucun service, aucun déploiement et aucun paramètre de production.

Les statuts `terminé`, `contrôlé`, `à vérifier` et `non validé` sont volontairement séparés : une fonctionnalité présente dans le code n'est pas automatiquement une fonctionnalité validée en exploitation.
