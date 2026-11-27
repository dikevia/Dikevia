> **PLAN HISTORIQUE V3.30.** Ce plan ne décrit plus l'ordre de travail courant. Utiliser `docs/00` et `docs/57` pour les priorités actuelles.

# Plan développeur — finalisation V3.30

## État du kit

Le kit fourni est une préproduction. Il ne prouve ni l'application des migrations
sur la base cible, ni la configuration des comptes OIDC/PISTE, ni la restauration
d'une sauvegarde. Ne pas ouvrir l'instance à des dossiers réels avant la recette
staging et la validation humaine des scénarios juridiques.

Sur l'archive révisée, la suite Python a donné **169 réussis et 3 ignorés**.
Les trois tests ignorés sont les tests d'intégration PostgreSQL, faute de base et
d'URL de test dans cet environnement. Ce résultat ne valide donc pas les migrations
014/015 en base; la CI et la recette staging doivent encore le faire.
La CI GitHub crée son propre PostgreSQL éphémère et fournit les URL locales aux
tests; elle n'a besoin d'aucun secret GitHub contenant une URL Neon.

## Améliorations préparées dans cette révision

- La CI applique maintenant les migrations 014 et 015 sur PostgreSQL avant les tests.
- Un test PostgreSQL dédié couvre la liste des membres, le refus d'un identifiant
  d'administrateur inconnu, deux approbations simultanées, la limite de dix,
  la libération d'une place par suspension et la journalisation.
- La migration 015 refuse de s'appliquer si plusieurs organisations existent déjà.
  Elle refuse aussi une base qui contient déjà plus de dix adhésions actives.
  Cela évite d'activer silencieusement le profil privé sur une base incompatible.
- Les 42 diagnostics Ruff hérités du dépôt ont été corrigés sans changer la logique;
  la commande de lint CI passe sur cette révision.
- La procédure privée demande maintenant la pré-vérification des données, une
  sauvegarde restaurable et la recette des approbations concurrentes.
- La commande d'installation locale et la documentation des comptes listés ont
  été corrigées.
- Les parseurs XML de documents DOCX et de circulaires utilisent `defusedxml`;
  une régression vérifie le rejet d'entités XML et la dépendance est déclarée
  directement dans les exigences runtime.

## Ordre de travail recommandé

### 1. Vérifier l'environnement cible

- Confirmer qu'il s'agit bien d'une instance dédiée et qu'elle contient au plus
  une organisation.
- Vérifier l'issuer, le subject OIDC vérifié et le compte commanditaire autorisé.
- Préparer les variables de configuration dans le gestionnaire de secrets de
  l'hébergeur; ne pas les envoyer par e-mail ou les intégrer au ZIP.
- Faire une sauvegarde et réaliser au moins une restauration de contrôle.

### 2. Exécuter la recette staging

- Installer la même version PostgreSQL et les mêmes rôles que la cible.
- Exécuter la CI complète et conserver le lien du run et son commit.
- La CI utilise son PostgreSQL éphémère; les URL Neon ne doivent pas être ajoutées
  aux secrets GitHub.
- Tester invitation, acceptation, approbation, refus, suspension, réactivation,
  révocation et concurrence de deux approbations.
- Vérifier que le onzième compte actif est refusé, qu'une suspension libère une
  place et que l'administrateur reste capable de gérer l'instance.
- Vérifier les événements d'audit, les refus d'accès d'un membre suspendu et
  l'absence de routes Stripe accessibles.
- Effectuer la recette OIDC, PISTE, ClamAV, stockage documentaire, sauvegardes
  et restauration avec des données de test.

### 3. Valider le périmètre juridique et données personnelles

- Faire relire les scénarios FPT par un juriste ou le référent compétent.
- Vérifier les dates d'effet, les sources officielles et les réserves affichées.
- Valider les règles de conservation, suppression, confidentialité, sous-traitants
  IA et accès aux documents avant les dossiers réels.

### 4. Autoriser la production

La promotion en production ne se fait qu'après les étapes staging, la preuve de
restauration, la validation du compte administrateur, l'approbation du propriétaire
de l'instance et la consignation des résultats de recette.

## Points à confirmer lors de la revue développeur

- Le compteur de sièges est global à l'instance et inclut toute adhésion active,
  y compris celle du compte administrateur lorsqu'il est membre de l'organisation.
- Les fonctions SQL `SECURITY DEFINER` privées sont appelées par l'API après son
  contrôle OIDC; examiner la frontière de confiance et les privilèges du rôle
  runtime avant exposition à un autre chemin d'accès.
- Les notes de préparation rapportent deux résultats historiques différents
  (135/2 et 164/2). Le dernier résultat local de l'archive révisée est 169/3;
  le run de CI PostgreSQL doit faire foi pour la livraison finale.
- Le nouveau test PostgreSQL suppose une base CI jetable sans adhésions actives
  préexistantes, condition vérifiée explicitement par le test.


## V3.31 — Protection contre les rafales de requêtes chat

- Migration 017 : compteur PostgreSQL par organisation, utilisateur et minute ; aucune question ni contenu conversationnel n'est enregistré dans ce compteur.
- La mise à jour du compteur est atomique (INSERT ON CONFLICT) pour fonctionner avec plusieurs workers API.
- RLS/FORCE RLS limite la lecture et l'écriture du compteur au tenant et à l'utilisateur courant.
- Valeur par défaut : 10 requêtes chat par minute et par utilisateur ; configuration CHAT_RATE_LIMIT_PER_MINUTE bornée entre 1 et 120.
- Au dépassement, l'API renvoie HTTP 429 avec Retry-After ; les compteurs de plus de 24 heures sont nettoyés lors de la requête suivante de l'utilisateur.
- Cette limite protège contre les rafales, mais ne constitue pas un budget mensuel de dépenses IA, un quota PISTE ou un WAF. Ces contrôles doivent être définis séparément avant commercialisation.


## V3.32 — Comptabilisation de la consommation IA

- Migration 018 : journal `ai_usage_events` par organisation et utilisateur, avec identifiant technique de requête, fournisseur, modèle, compteurs de tokens disponibles, date et issue de l'appel.
- Aucun contenu de question, de réponse, de conversation ou de document n'est stocké dans ce journal.
- Les compteurs absents ou invalides restent `NULL` ; aucune consommation ni aucun coût ne sont estimés artificiellement.
- Le rôle API peut uniquement ajouter des événements. Il ne peut ni lire ni modifier le journal ; RLS/FORCE RLS contrôle les insertions selon l'organisation et l'utilisateur courants.
- Les réponses IA, réponses rejetées pour référence non sourcée et erreurs du fournisseur sont distinguées.
- Les quotas mensuels et le calcul monétaire ne sont pas activés : ils nécessitent les tarifs fournisseurs vérifiés et une décision sur les budgets/plans. Ne pas présenter le compteur de tokens comme un coût en euros.


## V3.33 — Quota partagé des traitements juridiques coûteux
Le quota PostgreSQL initialement appliqué au chat est également appliqué à la revue de cohérence des règles locales. Les deux routes partagent le même compteur par organisation/utilisateur et la même configuration `CHAT_RATE_LIMIT_PER_MINUTE`. Le contrôle de la revue intervient avant la lecture du document et l'interrogation du corpus national. Le compteur n'enregistre aucun contenu.


## V3.34 — Protection des connecteurs juridiques directs
Les routes de contrôle PISTE, de recherche Légifrance et de recherche/consultation CETAT partagent maintenant le compteur PostgreSQL par organisation et utilisateur déjà utilisé par le chat et la revue locale. Le quota est contrôlé avant tout appel externe ; les entrées invalides sont rejetées avant consommation. La réponse de dépassement est HTTP 429 avec `Retry-After`. Cette protection couvre les routes API directes, mais ne remplace pas les quotas contractuels PISTE ni un budget fournisseur.


## V3.35 — Bornage des imports PISTE

- Les routes d'ingestion réglementaire et CETAT valident les recherches (2 à 500 caractères) et limitent les imports à 1–20 résultats avant toute connexion ou opération externe.
- La borne CETAT limite également les consultations de décisions intégrales.
- Version API : 3.35.0 ; aucun changement de schéma SQL.
- CI du commit code V3.35 : 193 tests réussis, aucun échec ; migrations 001 à 018, tests PostgreSQL 16/RLS, contrôles qualité et construction du kit réussis.
- Preuve et empreinte de l'archive : voir `docs/42_V3_30_PREUVE_VALIDATION_CI.md`.

## Clarification du modèle de conversation et point RGPD bloquant

Les versions ultérieures ont ajouté l'historique privé des conversations et les dossiers juridiques persistants (migration 012 et migration 013). Les anciens documents qui décrivaient un chat sans historique serveur étaient devenus obsolètes ; les exigences produit, sécurité et acceptation ont été harmonisées le 17 novembre 2026.

- Les conversations et messages sont stockés dans PostgreSQL et protégés par RLS/FORCE RLS, avec cloisonnement par organisation et utilisateur.
- La suppression d'une conversation entraîne la suppression en cascade de ses messages et du dossier juridique associé.
- Le journal de consommation IA ne stocke pas le texte des conversations.
- **Point non réalisé :** aucune durée de conservation métier approuvée ni purge automatique planifiée des conversations/dossiers n'est démontrée par le kit.
- Avant production, le responsable de traitement/DPO doit valider les finalités, durées, bases légales, information, droits d'accès/export/suppression et politique de sauvegarde ; le développeur doit implémenter et tester les purges correspondantes.
- Ne pas utiliser de dossiers réels avant cette validation. Ne pas déduire une conformité RGPD du seul passage de la CI.


## V3.36 — contrats API de propriété des conversations et dossiers

- Ajout de tests des gestionnaires API pour les conversations et dossiers qui ne sont pas visibles dans le contexte propriétaire courant.
- Une conversation étrangère/inconnue ne doit pas être listée ou lue ; sa suppression doit renvoyer 404 ; les opérations de création, lecture et modification du dossier lié doivent être refusées.
- La suite CI du commit `c19b109d7ce76c64113dd5fb2e4bce57181dc05a` a réussi : **199 tests, aucun échec** (run [44066187124](https://github.com/dikevia/Dikevia/actions/runs/44066187124)).
- Les nouveaux tests V3.36 exercent directement les gestionnaires de routes avec une connexion simulant le masquage RLS. Ils complètent les tests PostgreSQL réels déjà présents ; ils ne constituent pas une recette HTTP/OIDC complète.
- Cette évolution est principalement une extension de tests et de preuve, sans changement de schéma ni migration SQL.
- Le kit correspondant est disponible dans l'artefact [14319513979](https://github.com/dikevia/Dikevia/actions/runs/44066187124/artifacts/14319513979).

Le blocage de conservation/purge décrit ci-dessus reste ouvert et ne doit pas être contourné par une durée technique choisie sans validation du responsable de traitement/DPO.


## V3.37 — préparation technique de la purge des conversations privées

- Ajout de `scripts/purge_private_conversations.py`, outil opérateur sans planification automatique.
- Prévisualisation sans effet de bord par défaut ; seuil absolu ISO-8601 avec fuseau obligatoire.
- Double confirmation `--execute --confirm-delete` pour supprimer.
- Refus des connexions dont le rôle PostgreSQL n'a ni `SUPERUSER` ni `BYPASSRLS`.
- La suppression des conversations entraîne les cascades déjà définies vers messages et dossiers.
- Tests unitaires des garde-fous et test PostgreSQL réel prévu dans la CI pour vérifier prévisualisation, suppression et cascades, sans toucher à Neon.
- Aucun délai métier n'est défini et aucun job planifié n'est installé. L'outil n'est pas exécuté sur une base réelle.
- La règle technique utilise `chat_conversations.updated_at` comme colonne de comparaison ; le responsable de traitement/DPO doit valider le point de départ, les durées, exceptions, sauvegardes et périmètres avant toute utilisation.
- Documents téléversés, journaux d'audit et métriques ne sont pas inclus dans cette première version.
