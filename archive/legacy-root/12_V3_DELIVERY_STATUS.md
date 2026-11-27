# 12 — État de livraison V3

## Développé dans cette livraison
- Socle FastAPI 3.0.0.
- Validation JWT OIDC configurable par JWKS.
- Résolution de l'utilisateur et de l'organisation côté serveur.
- Sélection d'organisation non fiable, revérifiée par membership actif.
- Contexte PostgreSQL transactionnel.
- Migration RLS/FORCE RLS couvrant les tables privées métier.
- Lecture des organisations, membres, documents.
- Création d'invitation en attente (sans livraison e-mail).
- Révocation d'adhésion avec journal d'audit et protection du dernier administrateur.
- Configuration Docker PostgreSQL/API et création du rôle runtime.
- Documentation d'exploitation, sécurité et recette.

## Non développé
- Connexion interactive OIDC (à configurer dans l'IdP et son client web).
- Provisionnement plateforme sécurisé et gestion complète des rôles plateforme.
- Acceptation et envoi des invitations.
- CRUD complet des documents, versions et stockage objet privé.
- Connecteur PISTE/Légifrance, corpus local et moteur de recherche.
- Adaptateur IA, format de réponse juridique complet et validation des citations.
- Rate limiting, observabilité, sauvegardes automatisées et gestion de fichiers.

## Vérifications effectuées ici
- Compilation syntaxique Python : réussie.
- Vérification syntaxique du script shell d'initialisation : réussie.
- Contrôle statique de présence RLS/FORCE RLS et cohérence schema/migration : réussi.
- Tests pytest : non exécutés, car les dépendances Python manquantes n'ont pas pu être téléchargées dans cet environnement sans accès réseau.
- Migration PostgreSQL, authentification contre un IdP, tests d'isolation réels : non exécutés.


## Mise à jour V3.1
- Routes ajoutées : création d'organisation plateforme et acceptation d'invitation.
- Invitations créées par un administrateur local avec jeton à usage unique ; seul le hash est stocké.
- Acceptation liée à un e-mail vérifié par OIDC, transactionnelle et journalisée.
- Bootstrap du premier administrateur plateforme documenté hors API.
- Script de permissions SQL runtime ajouté avec interdiction d'écrire dans `platform_admins`.
- Quatre tests statiques V3.1 passent.
- Tests complets bloqués dans cet environnement car `asyncpg` n'est pas installé ; aucun PostgreSQL ni Docker/psql n'est disponible pour la recette réelle.

## Contrôles V3.1 réalisés dans cet environnement
- Compilation syntaxique Python (`compileall`) : réussie.
- Tests statiques de contrat V3.1 : 5 réussis.
- Suite pytest complète : non exécutable ici, car le module `asyncpg` n'est pas installé dans l'environnement d'exécution.
- Recette SQL/RLS PostgreSQL réelle : non exécutée ; aucun client `psql` ni moteur Docker/PostgreSQL n'est disponible ici.


## Addendum V3.2

Le registre global `users` et la table `platform_admins` sont désormais protégés par RLS et FORCE RLS dans la migration 003. Les routes qui consultent ces tables établissent le contexte OIDC dans la transaction. Un harnais de test PostgreSQL à deux organisations a été ajouté ; il reste à l'exécuter sur une base jetable avec le rôle runtime réel. Les tests statiques seuls ne certifient pas l'isolation.


## Addendum V3.3 — gestion documentaire
- Routes de collectivités, import PDF/DOCX, stockage privé, versions, métadonnées, téléchargement authentifié et validation juridique ajoutés au backend.
- Le contrôle de format n'est pas un antivirus. Le code V3.3 seul ne doit pas être exposé en production sans le lot V3.4 ci-dessous.

## Addendum V3.4 — analyse et recherche documentaire
- ClamAV est désormais intégré via INSTREAM et devient une dépendance de l'import : panne scanner = refus de l'import. Les téléchargements ne sont autorisés que pour les fichiers marqués `CLEAN`.
- Extraction PDF par pypdf et DOCX par lecture XML ; pas d'OCR. Indexation plein texte PostgreSQL français dans `document_text`, avec RLS/FORCE RLS.
- Recherche cloisonnée, rescannage des versions et réindexation historique ajoutés.
- Les documents existants passent en `NOT_SCANNED` à la migration ; les responsables doivent les rescanner avant téléchargement et réindexer avant recherche plein texte.
- Validation dans cet environnement : compilation Python réussie ; 32 tests réussis et 1 test PostgreSQL ignoré. La suite a été lancée avec un shim d'import uniquement pour `asyncpg`, absent de l'environnement hors ligne. 26 tests statiques/unitaires ciblés réussis. Le test PostgreSQL réel, l'IdP réel, ClamAV réel et le chemin d'extraction PDF avec la dépendance installée n'ont pas été exécutés.
- `docker-compose.yml` est syntaxiquement lisible en YAML. Aucun déploiement, aucune migration réelle et aucune certification de sécurité n'ont été réalisés.

## Complément V3.5

Le kit inclut désormais des contrôles de configuration OIDC/CORS au démarrage, une validation JWT limitée à RS256/ES256, des en-têtes HTTP de sécurité et un endpoint de disponibilité PostgreSQL (`/ready`). Ces contrôles sont couverts par tests automatisés, mais la validation avec un IdP réel, PostgreSQL réel et le reverse proxy de production reste à effectuer.

## Évolution V3.6
L'interface responsive de travail est intégrée : sélection de l'organisation, vue d'ensemble, documents, collectivités, membres, invitations et question juridique. Le module OIDC PKCE est fourni comme client navigateur public à configurer. Aucun fournisseur d'identité réel n'est préconfiguré ; le parcours doit être validé avec le fournisseur retenu avant production. Voir `docs/16_V3_6_USER_WORKSPACE.md`.

### V3.7 — Intégration Keycloak
La V3.7 fournit un realm Keycloak `cfdt`, un client web public PKCE S256, un mapper d'audience API, un service Keycloak dans Compose et une base PostgreSQL séparée. Le script `scripts/render_keycloak_config.py` génère l'import du realm et la configuration navigateur selon les URL publiques. La documentation de déploiement est dans `docs/17_V3_7_KEYCLOAK.md`.

**Non vérifié dans l'environnement de génération :** démarrage effectif des conteneurs, import Keycloak, échange de code navigateur, claims réels, SMTP et parcours d'invitation. Ces étapes nécessitent Docker et un environnement de déploiement.

### V3.8 — Invitations et rôles
Le kit V3.8 ajoute le provisionnement des comptes Keycloak via un client de service, la vérification d'adresse, l'envoi SMTP du lien d'invitation et les parcours de changement/révocation des rôles par organisation. Ces intégrations nécessitent un realm et un SMTP réels pour être validées.

### V3.9 — Intégrité des invitations
- Unicité des invitations en attente par e-mail et organisation, avec migration de nettoyage conservant l'historique.
- Acceptation d'invitation empêchant le remplacement implicite d'un rôle existant ; sérialisation des acceptations concurrentes.
- Validation HTTPS et origine seule pour l'URL du client Keycloak Admin en production.
- Vérification locale : compilation Python réussie ; 54 tests réussis, 1 test PostgreSQL ignoré. `asyncpg` reste absent et a été remplacé par un shim d'import uniquement pour permettre la collecte des tests ; aucune connexion réelle à PostgreSQL n'a été effectuée.
- Migration 006, provisionnement réel Keycloak, délivrabilité SMTP et scénarios multi-organisations restent à valider sur un environnement de recette.

## Addendum V3.10 — Source nationale CGFP intégrée au kit
- Ajout du PDF du Code général de la fonction publique fourni pour le projet : 1 024 pages, consolidation indiquant une dernière modification au 31 octobre 2026 et génération le 13 novembre 2026.
- Ajout d'un fichier de métadonnées avec empreinte SHA-256, dates, périmètre et statut de validation.
- Ajout d'une procédure documentaire précisant l'indexation par article et la vérification temporelle obligatoire.
- **Limite :** le PDF est embarqué dans le kit, mais n'est pas encore importé dans une base active. Le pipeline juridique, l'historique Légifrance et le validateur de citations restent à développer. L'intégration documentaire ne fait donc pas passer le moteur juridique à l'état opérationnel.

## Addendum V3.11 — CGFP interrogeable
Le PDF CGFP n'est plus uniquement stocké : un index JSON article/page est fourni et exploité par le backend. La route de recherche et le parcours `chat/ask` peuvent retourner des extraits issus du snapshot. Les résultats restent explicitement partiellement vérifiés ; la connexion PISTE/Légifrance, la temporalité juridique, les textes associés, la jurisprudence et le corpus local ne sont pas couverts par cette évolution.


## Addendum V3.12 — Recherche et consultation d'articles CGFP
- Le moteur local classe les résultats par BM25 au lieu de compter uniquement les occurrences de mots.
- Les extraits sont centrés sur les termes de recherche lorsque le texte est long.
- Un service interne permet de récupérer le texte intégral d'un article identifié.
- Routes API authentifiées : `/api/v1/legal/cgfp/source`, `/api/v1/legal/cgfp/articles/{article_ref}`, et `/api/v1/legal/cgfp/search`.
- Tests unitaires du moteur CGFP : 8 réussis. Les tests d'intégration HTTP complets et l'environnement PostgreSQL/Keycloak n'ont pas été exécutés dans cette session.
- **Limite inchangée :** pas de contrôle de version historique, pas de connecteur PISTE/Légifrance, pas de jurisprudence raccordée. Le statut ne peut pas être `VERIFIE` sur la seule base du snapshot.


## Addendum V3.13 — Intégrité des citations CGFP

La V3.13 ajoute un contrôle déterministe côté serveur des citations extraites du snapshot : identifiant de source, référence d'article, plage de pages et correspondance de l'extrait dans le texte intégral. Les références qui échouent sont écartées. Si aucune citation ne passe, le statut retourné est `NON_VERIFIE`. La date des faits est contrôlée au format ISO strict.

Ce contrôle porte uniquement sur l'intégrité par rapport au snapshot local. Il ne prouve pas que le PDF est la version officielle applicable à la date des faits. L'intégration PISTE/Légifrance, la gestion des versions historiques, le corpus local, le fournisseur IA et la recette d'infrastructure restent à réaliser.

## Addendum V3.14 — analyse assistée facultative

L'adaptateur IA serveur est codé et peut être configuré avec un fournisseur compatible OpenAI Chat Completions. Il est désactivé par défaut. Les extraits envoyés au modèle ont passé le contrôle déterministe des citations ; les sources affichées restent construites par le backend. L'IA n'a pas le droit de créer des références. En cas d'absence de configuration ou d'indisponibilité, le service revient au mode documentaire. Le statut reste partiellement vérifié car le connecteur Légifrance, les versions historiques et les corpus locaux ne sont pas raccordés.

L'interface de question juridique a également été ajustée : date des faits au format date ISO, état de chargement du formulaire, présentation des références avec pages/extraits et liste des vérifications manquantes.

Validation de cette livraison : 68 tests réussis, 1 test PostgreSQL ignoré. Les tests ont été lancés avec un module `asyncpg` de substitution, l'environnement étant hors ligne ; aucun test de connexion PostgreSQL réel, de fournisseur IA réel, d'authentification Keycloak réelle ou de déploiement Docker n'a été réalisé.

## Addendum V3.15 — PISTE/Légifrance
- Client OAuth2 Client Credentials et séparation des environnements PISTE sandbox/production.
- Ping et appels documentés `/search` et `/consult/getArticle` pour le fonds `CODE_DATE` du CGFP.
- Recherche datée ; les articles sont retenus uniquement après aller-retour identifiant + texte.
- L'orchestrateur interroge le connecteur en priorité lorsqu'il est configuré, puis conserve le snapshot CGFP comme source documentaire complémentaire.
- Contrôle backend des références d'articles émises par l'IA ; génération rejetée si un numéro d'article cité n'existe pas dans les sources retenues.
- Routes de diagnostic, recherche et indicateur de connexion dans le tableau de bord.
- Compose exécute schéma consolidé et droits minimaux lors de la première initialisation d'un volume PostgreSQL vide.
- Aucun accès PISTE réel, test PostgreSQL réel ou déploiement n'a été effectué dans l'environnement de développement de cette livraison.

## Addendum V3.15 — PISTE/Légifrance
- Client OAuth2 Client Credentials et séparation des environnements PISTE sandbox/production.
- Ping et appels documentés `/search` et `/consult/getArticle` pour le fonds `CODE_DATE` du CGFP.
- Recherche datée ; les articles sont retenus uniquement après aller-retour identifiant + texte.
- L'orchestrateur interroge le connecteur en priorité lorsqu'il est configuré, puis conserve le snapshot CGFP comme source documentaire complémentaire.
- Contrôle backend des références d'articles émises par l'IA ; génération rejetée si un numéro d'article cité n'existe pas dans les sources retenues.
- Routes de diagnostic, recherche et indicateur de connexion dans le tableau de bord.
- Compose exécute schéma consolidé et droits minimaux lors de la première initialisation d'un volume PostgreSQL vide.
- Aucun accès PISTE réel, test PostgreSQL réel ou déploiement n'a été effectué dans l'environnement de développement de cette livraison.


## Addendum V3.16 — jurisprudence administrative

Le backend interroge le fonds CETAT de Légifrance via le client PISTE existant. Les identifiants CETATEXT sont contrôlés, les doublons écartés et les résultats affichés comme métadonnées de recherche. Les résultats ne sont pas transmis au modèle IA car le texte intégral des décisions n'est pas récupéré dans cette livraison. Une route authentifiée de recherche directe est disponible.

Validation locale : compilation Python réussie ; 6 tests ciblés (connecteur CETAT et connecteur PISTE) réussis ; vérification syntaxique JavaScript du frontend réussie. La suite complète pytest ne peut pas être collectée dans cet environnement, car `asyncpg` n'est pas installé. Aucune connexion réelle PISTE, recette Keycloak/PostgreSQL ou déploiement n'a été exécuté.
