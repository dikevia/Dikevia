# Dikévia

Assistant juridique spécialisé dans la défense des agents de la fonction publique territoriale et l'accompagnement de l'action syndicale.

## Point d'entrée développeur

- [Guide de démarrage développeur](docs/00_DEVELOPMENT_START_HERE.md)
- [État consolidé du projet](docs/57_ETAT_CONSOLIDE_2026-11-27.md)
- [Index des documents historiques](docs/ARCHIVE_INDEX.md)

La seule branche de travail est `main`. Les développements utiles sont intégrés directement sur cette branche. Aucune branche parallèle, PR ou fusion globale d'anciennes branches.

## État du dépôt — 27 novembre 2026

- Dernier contrôle CI complet : [run 46017735647](https://github.com/dikevia/Dikevia/actions/runs/46017735647), **1 494 tests réussis**.
- Auth0 est le fournisseur d'identité par défaut ; le parcours staging a été vérifié. Le Compose local ne démarre plus Keycloak.
- Le corpus juridique staging comporte 8 020 chunks vectorisés. La pertinence juridique du moteur hybride n'est pas encore certifiée par le benchmark métier.
- Aucun paiement n'est activé. Aucun service ou API payant ne doit être activé sans accord explicite.
- La production reste sur une ancienne branche et n'a pas été modifiée dans cette consolidation.

## Architecture — sources de vérité

| Répertoire | Responsabilité |
|---|---|
| `backend/app/` | API FastAPI, authentification, autorisations, conversation, moteur juridique |
| `frontend/` | Interface web, styles et OIDC navigateur |
| `android/` | Applications mobiles standard et administration |
| `database/` | Schéma, migrations et droits PostgreSQL |
| `corpus_national/` | Référentiel juridique national |
| `deploy/` | Docker Compose, image et configuration d'exploitation |
| `scripts/` | Préparation locale, migrations, imports et audits |
| `docs/` | Documentation actuelle et archives documentaires signalées |
| `archive/legacy-root/` | Anciens fichiers racine conservés pour traçabilité ; non utilisés par le runtime et exclus du kit développeur |

Le Dockerfile racine lance `backend/app` via `uvicorn app.main:app`. Ne pas utiliser les anciens modules et scripts de `archive/legacy-root/` comme sources de code.

## Modèle fonctionnel actuel

- **Agent individuel** : chatbot juridique uniquement, limite commerciale de 5 questions par jour.
- **Abonnements syndicaux** : capacités de 5, 10 ou 15 accès ; accès aux fonctionnalités syndicales et aux modules CST, FS, CAP et CCP. Aucun quota commercial de questions n'est prévu pour ces offres.
- Les prix des abonnements syndicaux restent à définir. Aucun checkout ni paiement n'est actif.
- L'application Administration est séparée du parcours chatbot agent et sert au pilotage des organisations, membres, droits et services.

## Développement local

Le point d'entrée opérationnel est le guide [docs/00_DEVELOPMENT_START_HERE.md](docs/00_DEVELOPMENT_START_HERE.md). Les modèles `.env.example` et `.env.staging.example` n'embarquent pas de secrets Auth0 : renseigner une configuration autorisée avant d'attendre un parcours de connexion. Sans configuration Auth0, l'authentification échoue volontairement fermé.

Le Compose standard utilise `deploy/docker-compose.yml`. Keycloak n'est conservé que comme compatibilité historique optionnelle via le profil `legacy-keycloak` ; il ne fait pas partie du démarrage normal.

## Limites à ne pas masquer

- Le benchmark conversationnel et la validation métier restent à réaliser avec les développeurs.
- La minimisation des données personnelles n'est pas une anonymisation complète ; la conformité contractuelle du fournisseur IA et les garanties de traitement restent à finaliser.
- La politique de rétention/purge automatique et les documents RGPD associés restent incomplets.
- L'OCR des PDF numérisés n'est pas encore livré.
- Les qualifications CST/FS/CAP/CCP produisent des candidats et listes de contrôle ; le suivi durable complet des suites d'instances reste à développer.
- L'authentification Android doit encore être validée sur appareils réels.
- La production n'est pas alignée sur `main`. Aucun déploiement n'est inclus dans cette consolidation.

Pour les validations et priorités détaillées, se reporter au document consolidé ; ne pas déduire une certification de production du seul résultat CI.
