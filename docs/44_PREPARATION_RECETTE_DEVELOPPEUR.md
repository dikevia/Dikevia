# V3.38 — Préparation de recette développeur

## Objectif

Cette livraison réduit le travail de préparation du développeur : dépôt, dépendances,
contrôles statiques, tests automatisés, configuration Docker et smoke tests disposent
d'une procédure unique. Elle ne remplace pas les essais réels avec les fournisseurs
externes ni la validation humaine des réponses juridiques.

## Point de départ contrôlé

- Branche : `cfdt-juris-v3-30-developer-ready`
- PR : #1, ouverte et non fusionnée.
- Base Neon principale : hors périmètre.
- Production : hors périmètre.
- Aucun secret, identifiant réel ou dossier syndical n'est nécessaire pour les tests CI.

## Préparation locale

Depuis la racine du dépôt :

```bash
python -m venv .venv
# Linux/macOS :
source .venv/bin/activate
# Windows PowerShell :
# .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements-dev.txt
python scripts/prepare_dev_env.py
python scripts/render_runtime_env.py --source .env --output .env.runtime
```

Le fichier `.env` créé contient des secrets locaux aléatoires. Il ne doit jamais
être committé, copié dans un ticket ou transmis au porteur du projet. Les clés
PISTE, IA, SMTP et Stripe ne sont pas inventées : elles sont à fournir séparément
si le scénario testé en a besoin.

## Lancement de la validation

```bash
bash scripts/run_developer_validation.sh
```

Cette commande exécute compilation, audit du modèle de configuration, Ruff,
Bandit, pip-audit, suite pytest, syntaxe shell et, si `.env` existe, validation
de la configuration Docker Compose. Elle ne démarre aucun conteneur, n'applique
aucune migration et ne modifie aucune base.

Pour construire aussi les images Docker :

```bash
BUILD_IMAGES=1 bash scripts/run_developer_validation.sh
```

Pour exiger les trois URL d'intégration PostgreSQL :

```bash
REQUIRE_POSTGRES_INTEGRATION=1 bash scripts/run_developer_validation.sh
```

Les URL doivent pointer vers une base jetable dédiée aux tests, jamais vers Neon
principal ou une base contenant des données réelles. Les migrations de recette
doivent être appliquées par le développeur dans cette base isolée selon le workflow
CI et les scripts SQL documentés. Le script de validation ne migre aucune base.

Après démarrage de l'application sur un environnement de test :

```bash
SMOKE_BASE_URL=http://127.0.0.1:8000 bash scripts/run_developer_validation.sh
```

Les endpoints `/health` et `/ready` sont vérifiés. Ces contrôles ne prouvent
pas la connexion OIDC, PISTE, IA, SMTP, Stripe ou l'exactitude juridique.

## Matrice de recette externe à compléter par le développeur

| Domaine | Test à lancer | Preuve attendue |
|---|---|---|
| PostgreSQL | Migrations 001–019 sur une base jetable, puis tests RLS avec rôles runtime | Sortie SQL + pytest sans test d'intégration ignoré |
| Keycloak/OIDC | Connexion PKCE, audience/issuer, e-mail vérifié, expiration et révocation | Parcours navigateur/API réussi et logs expurgés |
| Invitations | Créer, envoyer, accepter une fois, refuser mauvaise adresse, expirer/révoquer | Tests fonctionnels et audit |
| Documents | Import PDF/DOCX, ClamAV sain/infecté/indisponible, téléchargement, versions, reindex, suppression | Fichier de test, statuts et vérification stockage/DB |
| PISTE/Légifrance | OAuth sandbox, ping, recherche, article à date, erreur/quota | Identifiant article officiel, URL, date d'effet et réponse API expurgée |
| IA | Question de recette avec fournisseur choisi, refus des références non sourcées, panne et quota | Requête/réponse anonymisées et compteurs sans contenu sensible |
| Interface | Connexion, sélection organisation, conversation, dossier, documents, membres, invitation | Parcours desktop et mobile documenté |
| Sauvegarde | Sauvegarder puis restaurer DB, fichiers et Keycloak sur environnement isolé | Rapport de restauration et contrôles d'intégrité |
| Sécurité | Deux organisations, accès croisés, ID falsifiés, comptes suspendus, fichiers privés | Tous les refus attendus, aucune fuite |
| Juridique/RGPD | Corpus, dates, citations, conservation, sous-traitants et droits | Validation écrite des responsables compétents |

## Conditions de clôture de recette

Le développeur doit joindre au compte-rendu :
1. commit exact et artefact du kit ;
2. sortie complète du script de validation ;
3. versions des services et variables non secrètes utilisées ;
4. résultats des tests PostgreSQL/RLS, OIDC, ClamAV, PISTE et IA ;
5. liste des tests ignorés, échecs et réserves ;
6. preuves de restauration et tests mobiles ;
7. liste des points bloquants, sans données personnelles ni secrets.

Un test ignoré n'est pas un test réussi. Une simulation HTTP ne vaut pas connexion au fournisseur réel. Le passage en production reste interdit tant que les réserves sécurité, RGPD, juridiques et d'exploitation ne sont pas levées.

## Actions qui restent nécessairement externes

- Fournir et configurer les identifiants sandbox PISTE et le fournisseur IA retenu.
- Configurer l'instance Keycloak cible et ses URI autorisées.
- Fournir un environnement de recette distinct et ses accès.
- Définir les règles de conservation avec le responsable de traitement/DPO.
- Faire relire les scénarios et réponses juridiques par une personne compétente.
- Valider les droits sur les corpus, la marque et le code.

Aucune de ces actions ne doit être simulée ou remplacée par des identifiants fictifs.

## Précision sur le mode PostgreSQL strict

`REQUIRE_POSTGRES_INTEGRATION=1` vérifie uniquement que les trois variables d'environnement sont renseignées. Il ne teste pas à lui seul la connectivité, les privilèges SQL, la présence des migrations ni l'absence de tests ignorés. La preuve de l'intégration PostgreSQL est le résultat pytest sur une base jetable correctement initialisée, comme dans le workflow CI.


## Contrôle d'intégrité du stockage documentaire

La réindexation et le téléchargement comparent désormais les octets du fichier à l'empreinte SHA-256 conservée en base. Une différence bloque l'opération. La route de nouvelle analyse antivirus marque également la version comme `INFECTED` avec le moteur `INTEGRITY_CHECK` si les octets ont changé depuis l'import initial. Ce contrôle détecte une altération du fichier ; il ne remplace ni une sauvegarde ni une vérification périodique de l'ensemble du stockage.


Les fichiers privés sont créés avec des permissions de service restrictives (`0700` pour les répertoires organisation/document, `0600` pour les fichiers), puis publiés par renommage atomique après écriture synchronisée. Le développeur doit vérifier que le volume monté conserve ces permissions et que le compte du service est le seul compte système autorisé à lire le stockage.


Les téléchargements renvoient les octets mêmes qui ont été contrôlés par empreinte SHA-256 ; le serveur ne relit pas le chemin après validation, ce qui évite une substitution entre le contrôle et l'envoi. Lors d'une nouvelle analyse, le moteur associé au résultat de la version courante est propagé tel quel au document parent, notamment `INTEGRITY_CHECK` en cas d'altération.


### Contrôle complémentaire du versionnement documentaire

Le dépôt d'une nouvelle version verrouille désormais la ligne du document avec `SELECT ... FOR UPDATE` à l'intérieur de la transaction qui calcule le prochain numéro, écrit le fichier et enregistre les métadonnées. Le verrou est conservé jusqu'au commit. Cette sérialisation évite les collisions de numéros lorsque plusieurs utilisateurs déposent simultanément une version du même document. En cas d'échec de transaction, le fichier écrit est supprimé. La recette doit inclure un scénario de dépôts concurrents sur un même document.
