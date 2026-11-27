# Dikévia — décision d'architecture cible

Date : 27 novembre 2026  
Statut : décision approuvée par le porteur du projet  
Référence de développement : `main` exclusivement

## 1. Décisions non négociables

- Un seul flux de développement et d'intégration : `main`. Aucune branche fonctionnelle parallèle, aucune PR comme méthode de développement.
- Un seul service applicatif Render pour Dikévia. Il héberge le backend commun et sert les interfaces nécessaires. Les composants applicatifs ne doivent plus être répartis entre plusieurs services Render.
- Produit prioritairement mobile : applications Android et iOS conçues comme de véritables applications, et non de simples WebView/TWA enveloppant le site.
- Application web complémentaire, utilisant le même backend et les mêmes règles métier.
- Auth0 est le fournisseur d'identité retenu. Keycloak ne doit plus être une dépendance opérationnelle de la cible.
- Neon reste un service de base de données externe. Les données de test et de production doivent rester isolées, même si le nombre de services applicatifs Render est un.
- Application Administration distincte dans ses parcours et permissions ; elle ne doit pas contenir le chatbot destiné aux agents.
- Accès fondateur personnel : gratuit à 100 %, permanent, sans quota commercial ni crédits, avec toutes les fonctionnalités présentes et futures. L'attribution doit être vérifiée côté serveur sur l'identité OIDC Auth0 (issuer + subject), jamais sur le seul e-mail. Les protections de sécurité et anti-abus restent applicables.

## 2. Suspension des évolutions fonctionnelles

Aucune nouvelle fonctionnalité métier ou amélioration du chatbot ne doit être développée tant que les critères de conformité de l'architecture ci-dessous ne sont pas satisfaits et vérifiés.

Les travaux autorisés pendant cette période sont limités à :
- l'audit et la cartographie de l'existant ;
- la récupération sélective de code utile depuis les branches historiques vers `main` ;
- la consolidation du dépôt et de la configuration de déploiement ;
- la construction ou l'adaptation des socles Android/iOS natifs ;
- la préparation de migration et de retour arrière ;
- les tests d'architecture, de sécurité et de compatibilité nécessaires.

## 3. Cible logique

1. Applications Android et iOS natives.
2. Application web complémentaire et interface d'administration.
3. Un backend/API commun dans un unique service applicatif Render.
4. Auth0 pour l'identité et les sessions.
5. Neon pour les données et le corpus juridique, avec séparation stricte des environnements.

Un service Render unique ne signifie pas une base unique ni le mélange des données de test et de production. Les environnements doivent être séparés par des bases/branches Neon et des configurations explicitement vérifiées.

## 4. Règles de récupération des branches historiques

Aucune branche entière ne doit être fusionnée automatiquement.

Pour chaque branche :
1. comparer son contenu à `main` ;
2. identifier les commits et fichiers réellement absents de `main` ;
3. lire le code et ses tests ;
4. vérifier ses dépendances, son fournisseur d'identité, ses URLs, ses secrets et ses hypothèses d'hébergement ;
5. adapter le changement à l'architecture cible ;
6. intégrer directement sur `main` ;
7. exécuter les contrôles pertinents et conserver une preuve de résultat.

Un changement qui dépend de Keycloak, d'une ancienne API Render, d'une ancienne branche de production, d'une base non vérifiée ou d'un secret non documenté ne doit pas être repris tel quel.

Les branches historiques doivent rester intactes jusqu'à la fin de l'inventaire et à la confirmation que les éléments utiles sont récupérés. Leur suppression est une opération distincte, réservée aux responsables du dépôt après vérification.

## 5. État initial vérifié — 27 novembre 2026

- Le dépôt contient un socle Android avec deux éditions, standard et administration. La documentation Android décrit encore des APK bêta basées sur une enveloppe web et précise que la recette Auth0 sur appareil réel n'est pas validée.
- Aucun répertoire/projet iOS n'a été trouvé à la racine du dépôt `main).
- Une branche historique `android/native-compose-beta-v2` contient une application Kotlin/Jetpack Compose avec AppAuth/PKCE et des écrans natifs. Elle référence toutefois des URL de services Render séparés et un issuer Keycloak ; elle n'est donc pas intégrable telle quelle.
- Une branche `android/native-compose-integration` contient une version native plus avancée, mais conserve les mêmes dépendances d'architecture anciennes. Elle doit être auditée et adaptée avant toute récupération.
- La branche `feature/dikevia-pwa-android-shell` apporte une approche PWA ; elle ne remplace pas l'exigence d'applications Android/iOS natives.
- Le dépôt contient encore un `render.yaml` historique. La documentation de développement signale qu'il référence une ancienne branche et une infrastructure Keycloak. Il ne doit pas être synchronisé avec Render en l'état.
- Les services Render observés précédemment comprennent un service staging sur `main`, ainsi que des services historiques séparés rattachés à une branche `feature/*`. Le nombre cible est un seul service applicatif, mais leur fusion exige une cartographie des routes, domaines, variables, données, volumes, tâches et dépendances avant toute modification.
- Auth0 et Neon doivent être conservés comme services externes distincts. Aucune suppression de Keycloak ni migration de service/base ne doit précéder la validation des flux de connexion et de la correspondance des comptes.

## 6. Critères de conformité avant reprise du développement fonctionnel

- [ ] `main` contient tous les changements utiles et validés ; aucune dépendance fonctionnelle à une branche historique.
- [ ] Dépôt et workflows ne créent plus de branches de développement concurrentes.
- [ ] Un seul service applicatif Render héberge l'ensemble du backend Dikévia.
- [ ] Le service unique utilise une configuration documentée, sans dépendance opérationnelle à Keycloak.
- [ ] Les données de test et de production restent isolées et chaque connexion DB est prouvée.
- [ ] Application Android native compilable, authentification Auth0 testée sur appareil réel, parcours standard et administration séparés.
- [ ] Application iOS native présente, compilable sur environnement Apple et authentification Auth0 validée.
- [ ] Application web complémentaire fonctionnelle avec le même backend.
- [ ] Administration protégée côté serveur, sans chatbot agent.
- [ ] Privilège fondateur vérifié sur l'identité OIDC et testé sur les routes API, sans dépendance au seul e-mail.
- [ ] Tests de non-régression et contrôles de sécurité réussis sur le SHA exact de `main`.
- [ ] Plan de déploiement, retour arrière, variables, domaines et stockage documentés.

## 7. Garde-fous d'exploitation

- Aucun déploiement de production sans autorisation explicite.
- Aucun service payant, aucune dépense et aucune modification de plan sans autorisation explicite.
- Aucune migration destructive ni écriture de données de production pendant la consolidation.
- Aucune suppression de service, branche, base ou volume avant inventaire, preuve de sauvegarde et validation du plan de retour arrière.
- Ne jamais déclarer une fonctionnalité déployée parce que son code est présent sur `main`.
- Ne jamais déclarer les applications mobiles prêtes sur la seule base d'une compilation APK.
