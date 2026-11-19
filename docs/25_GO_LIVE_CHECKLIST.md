# CFDT JURIS — Parcours de mise en service

Ce document sépare l'installation technique de la mise en production commerciale. Une compilation réussie ne vaut ni recette de sécurité ni validation juridique.

## A. Installation de développement

1. Installer Docker Engine + plugin Docker Compose, Python 3.12+ et Git.
2. Décompresser le kit et ouvrir un terminal dans `CFDT_JURIS_V3/`.
3. Générer les secrets locaux : `python scripts/prepare_dev_env.py`.
4. Générer les fichiers Keycloak et OIDC :
   ```bash
   set -a; . ./.env; set +a
   python scripts/render_keycloak_config.py
   ```
5. Démarrer : `docker compose -f deploy/docker-compose.yml up --build -d`.
6. Contrôler `http://localhost:8000/health`, `http://localhost:8000/ready` et la disponibilité Keycloak.
7. Configurer l'identité OIDC du premier administrateur plateforme avec `database/bootstrap_platform_admin.sql` (commande psql documentée dans le script).
8. Connecter l'administrateur, créer l'organisation pilote via `POST /api/v1/platform/organizations`, puis inviter les autres membres.

Le compte Keycloak et l'administrateur plateforme doivent être provisionnés par une personne autorisée. Aucun compte par défaut n'est livré.

## B. Migration d'une installation V3.16

1. Faire une sauvegarde vérifiée de PostgreSQL.
2. Appliquer `database/migrations/007_saas_billing.sql` en tant que DBA/migration.
3. Exécuter `database/grant_runtime_permissions.sql` en tant que DBA.
4. Déployer le code V3.17.
5. Contrôler `/ready`, les logs et `GET /api/v1/billing/plans`.
6. Ne jamais rejouer `database/schema.sql` sur une base déjà initialisée.

## C. Configuration de l'offre payante

1. Créer le compte Stripe du porteur juridique/commercial du service.
2. Renseigner des clés de test `STRIPE_SECRET_KEY` et `STRIPE_WEBHOOK_SECRET` dans le `.env` serveur.
3. Déclarer l'URL webhook `/api/v1/billing/stripe/webhook` avec les cinq événements listés dans `docs/24_V3_17_SAAS_BILLING.md`.
4. Tester un checkout, un paiement réussi, un paiement refusé, une annulation, une échéance et une notification répétée.
5. Vérifier en base que l'organisation et la formule ont été mises à jour une seule fois.
6. Configurer les URLs HTTPS de retour avant d'activer les clés live.

## D. Recette obligatoire avant ouverture à des syndicats

- Tests réels PostgreSQL : RLS/FORCE RLS, deux organisations, tentatives de lecture/écriture croisées.
- Tests Keycloak réels : PKCE, issuer, audience, email vérifié, révocation, reset, session expirée.
- Tests ClamAV réels et fichiers malveillants de test contrôlés.
- Tests Stripe en mode test et vérification des webhooks.
- Tests de sauvegarde et restauration des bases et documents.
- HTTPS, reverse proxy, CSP adaptée, CORS strict, rotation des secrets, supervision et procédure d'incident.
- Tests de charge, limites de requêtes, quotas IA, coûts et protection contre les abus.
- Validation des mentions légales, CGU/CGV, politique de confidentialité, DPA, conservation/suppression, sous-traitants IA, transferts éventuels hors UE et analyse RGPD.
- Vérification des droits sur le nom CFDT JURIS, les logos, le code, les corpus et le droit de commercialiser à des tiers.

## E. Périmètre fonctionnel à achever avant une offre commerciale large

- Interface d'administration plateforme pour créer/suspendre les syndicats, attribuer les accès gratuits et consulter l'état des abonnements.
- Téléchargement du texte intégral des décisions de jurisprudence, contrôles de provenance et validation temporelle avant injection dans l'IA.
- Corpus des décrets, arrêtés, circulaires, textes réglementaires et jurisprudence ; connecteurs et stratégie de mise à jour documentés.
- Ingestion des corpus propres à chaque organisation avec validation des droits d'accès et de réutilisation.
- Tests de non-régression juridique par scénarios FPT, jeu de questions de référence et revue par juristes/agents compétents.
- Gestion des quotas IA, coûts par organisation, limitation de débit et alertes d'usage.
- Facturation conforme, TVA, factures, avoirs et export comptable ; Stripe Checkout seul n'est pas un logiciel de facturation complet.

## F. Critère de lancement

Le lancement pilote est autorisé uniquement après validation des sections A, B et D applicables. La commercialisation nécessite en plus C, E et les validations juridiques, contractuelles et comptables. Tant que les tests externes ne sont pas faits, le logiciel doit être considéré comme une préversion de recette, pas comme un service juridique certifié.


## V3.18 — Console plateforme

Pour une base existante V3.17 : sauvegarder la base, puis appliquer `database/migrations/008_platform_admin_console.sql` avec `cfdt_migration` (rôle DBA/BYPASSRLS), redémarrer l'API et vérifier l'accès de l'administrateur plateforme. Le script échoue volontairement si le rôle de migration ne possède pas `BYPASSRLS`.

Recette à effectuer :
- Un utilisateur non inscrit dans `platform_admins` reçoit HTTP 403 sur `GET /api/v1/platform/organizations` et sur les opérations de suspension.
- Un administrateur plateforme voit l'annuaire même sans adhésion à une organisation.
- Création d'une organisation, attribution d'un accès offert avec motif, suspension puis réactivation.
- Vérifier la trace `ORGANIZATION_SUSPENDED` / `ORGANIZATION_REACTIVATED` dans l'audit de l'organisation.
- Vérifier qu'une organisation suspendue ne peut plus utiliser les routes tenant (contrôle existant dans `get_tenant_context`).
- Vérifier que le rôle applicatif ne possède que `EXECUTE` sur les fonctions de console et aucun privilège transversal direct.

## V3.21 — Corpus juridique national
- [ ] Créer le rôle PostgreSQL `cfdt_juris_ingest` avec un secret distinct.
- [ ] Appliquer la migration `009_permanent_legal_knowledge.sql` avant d'activer les routes d'import sur une base existante.
- [ ] Configurer `LEGAL_CORPUS_INGEST_DATABASE_URL` dans l'environnement API.
- [ ] Vérifier que `cfdt_juris_app` ne dispose que de SELECT sur le corpus national.
- [ ] Vérifier que `cfdt_juris_ingest` n'a ni SUPERUSER, ni BYPASSRLS, ni propriété des tables.
- [ ] Tester en sandbox PISTE les workflows `/search` + `/consult/legiPart` et CETAT avec des identifiants connus.
- [ ] Contrôler manuellement la provenance du fichier XML CIRCULAIRES avant toute validation ; le statut initial est `IMPORTED_UNVERIFIED`.
- [ ] Vérifier les dates d'effet, les empreintes SHA-256, les liens Légifrance et le statut temporel des versions.
- [ ] Confirmer que les sources `METADATA_ONLY`, `IMPORTED_UNVERIFIED` et à temporalité incomplète sont exclues du contexte IA.
- [ ] Exécuter la recette complète sur une base PostgreSQL dédiée et vérifier les quotas PISTE.


## V3.30 — CGFP et moteur juridique

- [ ] Vérifier l'empreinte SHA-256 du PDF CGFP et contrôler le mode à blanc : `python scripts/import_cgfp_to_legal_corpus.py`.
- [ ] Créer/configurer le rôle dédié `cfdt_juris_ingest` et `LEGAL_CORPUS_INGEST_DATABASE_URL` côté serveur ; ne jamais utiliser `DATABASE_URL`/`cfdt_juris_app` pour l'import.
- [ ] Appliquer la migration `014_cgfp_snapshot_source_type.sql` sur une base existante.
- [ ] Exécuter l'import CGFP en environnement cible après sauvegarde : `python scripts/import_cgfp_to_legal_corpus.py --apply`.
- [ ] Contrôler en base les 4 242 articles, les versions et chunks, l'absence de doublons et les statuts `IMPORTED_UNVERIFIED` / `UNKNOWN`.
- [ ] Vérifier en sandbox puis production les recherches `CODE_DATE`, `LODA_DATE` et `CETAT` ; valider les consentements PISTE, les identifiants et les quotas.
- [ ] Vérifier qu'une question sans date des faits ne déclenche pas d'analyse IA contextualisée.
- [ ] Vérifier qu'un snapshot CGFP seul ne déclenche pas d'analyse IA et ne permet jamais le statut `VERIFIE`.
- [ ] Faire valider par un juriste le jeu de scénarios FPT avant toute utilisation opérationnelle.

- [ ] Recetter la recherche locale avec les deux employeurs : Ville de Saint-Étienne et Saint-Étienne Métropole ; vérifier l'isolation organisationnelle, le filtrage collectivité, les scans CLEAN, les empreintes, la validation et les dates d'effet (voir `docs/38_RECHERCHE_DOCUMENTS_LOCAUX.md`).

- [ ] Garder `LEGIFRANCE_CETAT_FULLTEXT_ENABLED=false` tant que le point d'entrée `/consult/juri` n'a pas été validé avec un identifiant CETAT réel en sandbox PISTE ; n'activer l'import intégral qu'après cette recette.


## G. État de la bêta technique non commerciale — 19 novembre 2026

Cette section décrit l'état de préparation de la bêta Dikévia. Elle ne vaut ni autorisation de mise en service ni certification juridique.

### Éléments préparés et vérifiés en CI

- [x] Suite automatisée exécutée sur une base PostgreSQL jetable : migrations 001 à 019, tests applicatifs et contrôles RLS.
- [x] Test d'intégration de la capacité bêta : réservation transactionnelle, invitations en attente, rôle runtime et concurrence sur la dernière place.
- [x] Coque PWA préparée ; le service worker ne met en cache que les ressources statiques de la page hors connexion.
- [x] Compilation Android de debug réussie sur runner GitHub Actions. L'APK est signé par une clé debug éphémère et n'est pas distribuable.
- [x] Les changements de préparation sont isolés dans des PR brouillon ; aucune fusion ni mise en production n'est présumée.

### Éléments non encore réalisés — bloquants avant la bêta sur hébergement

- [ ] Revoir puis fusionner explicitement les PR de préparation dans l'ordre convenu ; vérifier les contrôles CI après chaque étape. La branche commerciale suivie par Render déclenche un déploiement automatique : ne pas y pousser directement.
- [ ] Appliquer la migration 019 sur la base cible uniquement après sauvegarde, validation de la procédure et décision explicite de mise en service. Le test CI sur PostgreSQL jetable ne prouve pas que Neon a été migré.
- [ ] Vérifier sur l'environnement hébergé la connexion réelle, les rôles, les invitations, le plafond d'un utilisateur et les parcours de récupération de compte.
- [ ] Choisir l'origine HTTPS définitive de l'application Android, la méthode de signature et l'empreinte du certificat ; configurer puis vérifier Digital Asset Links si la TWA est retenue.
- [ ] Installer et tester l'application sur un appareil Android réel, notamment connexion, retour d'authentification et pièces jointes.
- [ ] Vérifier les sauvegardes/restaurations, la journalisation expurgée, les paramètres de sécurité et l'absence de secrets dans les artefacts.

### Conditions avant toute utilisation juridique opérationnelle

- [ ] Valider en sandbox PISTE les parcours Légifrance nécessaires, notamment le texte intégral CETAT avec un identifiant réel ; garder `LEGIFRANCE_CETAT_FULLTEXT_ENABLED=false` jusque-là.
- [ ] Faire examiner un jeu représentatif de situations FPT et les résultats par un juriste compétent ; les tests logiciels ne certifient pas la justesse juridique.
- [ ] Vérifier les obligations RGPD, les mentions d'information, la conservation/suppression, les sous-traitants et les droits sur les contenus.
- [ ] Faire tourner les identifiants OAuth précédemment exposés dans des échanges de développement avant tout usage réel ou production.

### Limites et règle de prudence

Les tests automatisés réussis démontrent le comportement des versions testées dans l'environnement CI, pas celui de l'environnement hébergé. Aucun déploiement, aucune migration distante et aucun test d'authentification sur appareil réel ne sont attestés par cette checklist. La bêta reste une préversion technique non commerciale tant que les cases bloquantes applicables ne sont pas validées.
