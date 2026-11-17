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
