# Dikévia — point d'entrée développeur

**Référence de travail : `main` uniquement.**  
**État du dépôt contrôlé : 26 novembre 2026.**

Ce document est le point d'entrée rapide pour les développeurs. Il décrit ce qui est constaté dans le dépôt ; il ne certifie pas la disponibilité des services externes ni le fonctionnement en production.

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
| `Dockerfile` | Image API : copie notamment `backend`, `frontend`, `database`, `scripts` et `corpus_national` |

Le Dockerfile racine lance `uvicorn app.main:app` avec `PYTHONPATH=/srv/backend`. Le code applicatif utilisé par cette image se trouve donc dans `backend/app/`. Des modules Python historiques existent encore à la racine ; ils ne doivent pas être supprimés avant une recherche complète de leurs références dans les scripts, workflows et outils locaux.

## 3. Documents à lire en priorité

1. `README.md` — présentation et consignes générales, à confronter à ce guide lorsque des indications historiques divergent.
2. `docs/47_AUTH0_MIGRATION.md` — conception et paramètres documentés de l'intégration Auth0.
3. `docs/39_LIVRAISON_DEVELOPPEUR_V3_30.md` — dossier de transfert historique, à ne pas considérer comme un état opérationnel actuel.
4. `docs/44_PREPARATION_RECETTE_DEVELOPPEUR.md` — procédure de validation préparée ; certaines références à Keycloak sont historiques et doivent être adaptées avant une recette OIDC réelle.
5. `docs/50_BETA_READINESS_2026-11-24.md` — état daté de la bêta ; ses indications d'environnement et de fournisseur d'identité ne remplacent pas une vérification actuelle.

En cas de contradiction, le code de `main`, les workflows réellement exécutés et la configuration active de l'hébergeur doivent être vérifiés. Une documentation datée ne constitue pas une preuve d'état courant.

## 4. Authentification : point de vigilance

Auth0 est l'orientation documentée pour le navigateur. Le flux attendu est OIDC Authorization Code + PKCE ; les autorisations applicatives et les appartenances restent gérées par Dikévia en base.

Ne pas réinitialiser le tenant, créer une nouvelle application Auth0 ou modifier ses listes d'URL pour corriger une régression sans diagnostic préalable. L'authentification fonctionnait avant les derniers changements d'interface et d'application Android, selon le retour du porteur du projet.

Le fichier `render.yaml` et certains fichiers de configuration historiques contiennent encore des références Keycloak et une ancienne branche. Ils sont incohérents avec l'orientation Auth0 documentée et doivent être audités avant toute synchronisation Blueprint ou tout déploiement. Ne pas les utiliser comme preuve de la configuration Render active.

## 5. État de validation constaté

Au commit `b48c92f7e69449f46ec5f02782b7119de6fdfb43` :

- le workflow de génération des APK Android est terminé avec succès ;
- le workflow CI général est en échec sur l'étape de tests unitaires, contractuels et d'intégration PostgreSQL/RLS ;
- le succès de compilation d'un APK ne prouve pas que le parcours de connexion Auth0 fonctionne sur l'appareil ;
- la connexion Android doit donc rester un sujet ouvert jusqu'à un test utilisateur concluant.

Ne pas annoncer une version stable ou une mise en production sur la seule base de la compilation.

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

- Examiner les branches historiques et extraire uniquement les changements réellement utiles qui manquent à `main`.
- Résoudre l'échec CI du dernier commit avant de déclarer `main` sain.
- Diagnostiquer le parcours Auth0 Android ; ne pas fusionner une correction non vérifiée.
- Réconcilier `render.yaml`, les fichiers de configuration historiques et la configuration Render réellement active.
- Auditer les modules Python racine, les anciens fichiers Keycloak et les documents de versions successives avant suppression.
- Réduire la documentation à un index actuel et un historique clairement séparé, sans supprimer les preuves techniques ou procédures encore utiles.

## 8. Politique de nettoyage

Le nettoyage doit être réversible et fondé sur des preuves :

- **Conserver** tout composant utilisé, testé ou nécessaire à une fonctionnalité actuelle.
- **Conserver temporairement** tout développement en cours dont l'utilité n'a pas encore été tranchée.
- **Déplacer vers un historique** les documents datés qui restent utiles comme preuve ou contexte, plutôt que les mélanger aux consignes actuelles.
- **Supprimer** seulement après vérification des imports, références, workflows, scripts, déploiements et dépendances.
- **Ne jamais fusionner une branche entière** uniquement pour récupérer un correctif isolé.

La cible est un dépôt simple à prendre en main, avec `main` comme seule référence de développement, une documentation courte et fiable, et aucun déploiement déclenché par un nettoyage documentaire.
