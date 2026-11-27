# Dikévia — point d'entrée développeur

**Référence de travail : `main` uniquement.**  
**État du dépôt contrôlé : 27 novembre 2026.**

Ce document est le point d'entrée rapide pour les développeurs. Il décrit ce qui est constaté dans le dépôt ; il ne certifie pas la disponibilité des services externes ni le fonctionnement en production.

**État de référence actuel :** lire d'abord [`docs/57_ETAT_CONSOLIDE_2026-11-27.md`](57_ETAT_CONSOLIDE_2026-11-27.md) pour le bilan consolidé, les limites connues et l'ordre des prochains travaux. Index des documents historiques : [docs/ARCHIVE_INDEX.md](ARCHIVE_INDEX.md). Les autres documents de livraison datés restent des traces historiques tant qu'ils n'ont pas été explicitement actualisés.

## 1. Règle de travail

- La branche de référence et d'intégration est `main`.
- Ne pas créer de nouvelle branche de développement.
- Ne pas repartir d'une ancienne branche `feature/*`, `fix/*`, `release/*` ou `android/*`.
- Avant toute modification : récupérer le dernier `main`, lire les fichiers concernés et vérifier les tests associés.
- Ne jamais faire de push forcé, réécrire l'historique ou lancer un déploiement sans validation.
- Ne jamais ajouter de secret, fichier `.env`, jeton, mot de passe ou donnée personnelle au dépôt.
- Une branche ancienne ne doit être fusionnée que si un changement précis est absent de `main`, relu, testé et compatible avec l'architecture actuelle.

## 2. Architecture présente dans le dépôt

| Zone | Rôle observé |
|---|---|
| `backend/app/` | API Python/FastAPI, authentification, autorisations, moteur conversationnel et juridique, accès aux données |
| `frontend/` | Interface web, styles, module OIDC navigateur et configuration publique |
| `database/` | Schéma PostgreSQL, migrations et droits runtime |
| `corpus_national/` | Corpus juridique national versionné |
| `scripts/` | Préparation développeur, migrations, imports, audits et opérations |
| `android/` | Applications Android standard et administration |
| `.github/workflows/` | CI, contrôles et génération des APK |
| `docs/` | Documentation fonctionnelle, technique, sécurité et exploitation |
| `archive/legacy-root/` | Anciens fichiers racine conservés hors des chemins actifs, non exécutables par défaut |
| `Dockerfile` | Image API : copie notamment `backend`, `frontend`, `database`, `scripts` et `corpus_national` |

Le Dockerfile racine lance `uvicorn app.main:app` avec `PYTHONPATH=/srv/backend`. Le code applicatif utilisé par cette image se trouve donc dans `backend/app/`. Après recherche des références dans le code, les workflows et les scripts actifs, les anciens modules, scripts, Compose et documents racine ont été déplacés dans `archive/legacy-root/`. Ils ne sont pas importés par le runtime et ne sont pas inclus dans le kit développeur.

## 3. Documents à lire en priorité

1. `README.md` — présentation et consignes générales, à confronter à ce guide lorsque des indications historiques divergent.
2. `docs/57_ETAT_CONSOLIDE_2026-11-27.md` — état opérationnel de référence ; `docs/47_AUTH0_MIGRATION.md` reste une documentation technique/historique de l'intégration Auth0.
3. `docs/39_LIVRAISON_DEVELOPPEUR_V3_30.md` — dossier de transfert historique, à ne pas considérer comme un état opérationnel actuel.
4. `docs/44_PREPARATION_RECETTE_DEVELOPPEUR.md` — procédure de validation préparée ; certaines références à Keycloak sont historiques et doivent être adaptées avant une recette OIDC réelle.
5. `docs/50_BETA_READINESS_2026-11-24.md` — état daté de la bêta ; ses indications d'environnement et de fournisseur d'identité ne remplacent pas une vérification actuelle.
6. `docs/AI_DATA_MINIMIZATION_AND_RETENTION.md` — périmètre réel du filtrage avant transfert IA, limites, conservation et prérequis RGPD.

En cas de contradiction, le code de `main`, les workflows réellement exécutés et la configuration active de l'hébergeur doivent être vérifiés. Une documentation datée ne constitue pas une preuve d'état courant.

## 4. Authentification : point de vigilance

Auth0 est le fournisseur retenu et le porteur du projet a confirmé que le chantier est terminé. Le défaut de configuration du backend est maintenant `auth0`. Le fallback statique navigateur est volontairement vide : sans configuration Auth0 serveur, l'authentification reste désactivée au lieu de basculer silencieusement vers un ancien IdP. Le Compose par défaut et `scripts/bootstrap.sh` ne démarrent plus Keycloak ; ses services restent disponibles uniquement via le profil explicite `legacy-keycloak` pour préserver les éléments historiques. Ne pas rouvrir la configuration Auth0, réinitialiser le tenant ou créer une nouvelle application sans demande explicite. La validation Auth0 sur staging ne certifie pas à elle seule chaque appareil Android ni l'environnement de production.

Le fichier `render.yaml` reste un Blueprint historique relié à l'ancienne branche et à l'infrastructure Keycloak de production. Il n'a pas été modifié, car une synchronisation pourrait affecter les services réels. Ne pas synchroniser ce Blueprint ni déclencher un déploiement avant un plan de migration distinct. Les anciens fichiers Keycloak sont conservés comme compatibilité/historique, pas comme configuration par défaut.

## 5. État de validation constaté

Au commit contrôlé `691c35514b961ec29dafcf77430819ad5ec6500e` (27 novembre 2026), le run CI [46017735647](https://github.com/dikevia/Dikevia/actions/runs/46017735647) est terminé avec succès :

- **1 494 tests passent**, dont les tests unitaires, contractuels et l'intégration PostgreSQL/RLS sur base jetable ;
- la migration 033 est exécutée après 032 dans la CI ;
- le nouveau parcours Auth0 par défaut, le fallback fail-closed, le Compose sans Keycloak par défaut et les workflows de déploiement désactivés sont couverts par les contrôles du dépôt ;
- les contrôles de syntaxe, lint, analyse statique de sécurité, audit de dépendances, scripts shell, Docker Compose et le kit développeur Dikévia, limité aux chemins actifs, passent ;
- le workflow de génération des APK Android avait également réussi sur le commit `dfc6bbf59ceed2871a001a399d0cfc9c22a1ecf0` ;
- le succès de compilation d'un APK ne prouve pas le parcours utilisateur complet sur un appareil Android réel.

Le CI vert valide le dépôt et les tests automatisés ; il ne remplace pas une recette Android sur appareil réel, une vérification des générations IA en conditions réelles, ni une validation de pertinence juridique. Aucun avertissement de test ne subsiste après l'ajout du transport de test httpx2 et la configuration explicite de pytest-asyncio. Les avertissements encore visibles dans les logs concernent uniquement l'environnement de conteneur de test (pip exécuté en root et authentification trust du PostgreSQL jetable). Ne pas annoncer une mise en production sur la seule base du CI.

## 6. Procédure de validation locale

Préparer un environnement local isolé, sans utiliser une base de production :

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
bash scripts/run_developer_validation.sh
```

Les tests d'intégration PostgreSQL doivent utiliser une base jetable et des rôles de test. Ne jamais fournir à cette procédure une URL de base contenant des données réelles. La validation locale ne remplace pas la recette Auth0, PISTE/Légifrance, IA, stockage documentaire, ClamAV, sauvegarde/restauration et interface mobile.

## 7. Travaux encore à arbitrer

- Maintenir `main` comme seule branche de travail et conserver la CI verte après chaque modification ; les workflows PR ont été retirés.
- Ne récupérer d'anciennes branches qu'un correctif précis démontré absent de `main`, jamais une branche entière.
- Faire réaliser le benchmark conversationnel et juridique par les développeurs ; les tests CI ne certifient pas la pertinence des réponses.
- Finaliser les garanties RGPD : le filtrage actuel des identifiants directs est une minimisation partielle, pas une anonymisation ; restent à traiter les noms, adresses, garanties contractuelles du fournisseur, politique de rétention/purge, registre, information et AIPD si nécessaire. Voir `docs/AI_DATA_MINIMIZATION_AND_RETENTION.md`.
- Compléter l'OCR des PDF numérisés et le suivi persistant des suites CST/FS/CAP/CCP.
- Valider Auth0 et les deux applications Android sur appareils réels ; ne pas rouvrir l'intégration Auth0 déjà validée sur staging.
- Préparer séparément la migration de production : le service actif reste sur une ancienne branche et le Blueprint Render ne doit pas être synchronisé sans plan dédié.
- Laisser de côté la page Abonnement/billing signalée comme non résolue tant que le porteur du projet ne demande pas sa reprise.

## 8. Politique de nettoyage

Le nettoyage doit être réversible et fondé sur des preuves :

- **Conserver** tout composant utilisé, testé ou nécessaire à une fonctionnalité actuelle.
- **Conserver temporairement** tout développement en cours dont l'utilité n'a pas encore été tranchée.
- **Déplacer vers un historique** les documents datés qui restent utiles comme preuve ou contexte, plutôt que les mélanger aux consignes actuelles.
- **Supprimer** seulement après vérification des imports, références, workflows, scripts, déploiements et dépendances.
- **Ne jamais fusionner une branche entière** uniquement pour récupérer un correctif isolé.

La cible est un dépôt simple à prendre en main, avec `main` comme seule référence de développement, une documentation courte et fiable, et aucun déploiement déclenché par un nettoyage documentaire. Les anciens fichiers racine ont été déplacés dans `archive/legacy-root/` ; leur index documentaire est `docs/ARCHIVE_INDEX.md`.
