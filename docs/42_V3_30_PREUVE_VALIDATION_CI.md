# V3.30 — preuve de validation CI du kit développeur

Date de validation : 17 novembre 2026

## Révision contrôlée

- Dépôt : `dikevia/Dikevia`
- Branche : `cfdt-juris-v3-30-developer-ready`
- Commit contrôlé : `248313253b6fd1786a997082727f6e4500151762`
- Pull request : [#1](https://github.com/dikevia/Dikevia/pull/1), vers `main`, laissée ouverte et non fusionnée.
- Exécution GitHub Actions : [run 44046067289](https://github.com/dikevia/Dikevia/actions/runs/44046067289)

## Résultats observés

L'exécution complète du workflow `test-and-audit` s'est terminée avec succès. La validation inclut la séparation du rôle PostgreSQL administrateur, les fonctions SQL de création d'organisation et d'attribution d'accès gratuit, et le refus des opérations privilégiées depuis le rôle runtime.

- **178 tests réussis**, aucun échec.
- Ruff : réussi.
- Bandit : réussi.
- `pip-audit` : réussi.
- Compilation Python et audit du modèle d'environnement : réussis.
- Migrations SQL 001 à 016, création des rôles dédiés et tests d'intégration sur PostgreSQL 16 éphémère : réussis.
- Vérification syntaxique des scripts shell : réussie.
- Validation des configurations Docker Compose : réussie.
- Construction et téléversement du kit développeur : réussis.

Un avertissement non bloquant subsiste dans les tests : dépréciation Starlette liée à l'utilisation de `httpx` dans `TestClient`. Il ne provoque aucun échec.

## Artefact généré

GitHub Actions a produit l'artefact `CFDT-JURIS-V3.30-Kit-Developpeur`, identifiant `14311272570`, taille 2 393 594 octets. Empreinte SHA-256 de l'archive : `e8915ece0d1b4045c863787107bf3aa9883bee0c523a51c3b8a22151d9cbfd9b`. Sa conservation GitHub est prévue jusqu'au 17 décembre 2026.

Le ZIP du kit est accompagné du fichier `SHA256SUMS_KIT.txt`, qui permet de contrôler les fichiers contenus.

## Portée et limites

Cette validation prouve que les contrôles automatisés et les tests sur la base PostgreSQL jetable passent sur la révision indiquée. Elle ne prouve pas :

- la connexion à un fournisseur OIDC réel ;
- la disponibilité d'identifiants PISTE/Légifrance ou d'un fournisseur IA réel ;
- la recette sur l'instance Neon du propriétaire ;
- la restauration effective d'une sauvegarde de l'instance cible ;
- un audit d'intrusion indépendant ou une certification juridique.

Aucune migration n'a été appliquée à la base Neon du propriétaire et aucun déploiement de production n'a été effectué.
