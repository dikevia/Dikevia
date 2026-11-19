# Dikévia — accès découverte et privilèges fondateurs

## Décisions produit

- Essai découverte de 72 heures, sans carte bancaire et sans renouvellement automatique.
- L'essai donne accès aux fonctions Pro disponibles, sous réserve des limites techniques anti-abus et des coûts fournisseurs.
- L'essai commence une seule fois, à la première activation effective du compte après vérification de l'adresse e-mail par OIDC.
- L'heure de début et l'heure de fin sont enregistrées côté serveur en UTC. L'interface affiche le temps restant, mais ne décide jamais des droits.
- À l'expiration, toutes les API applicatives protégées refusent l'accès avec un statut explicite « essai terminé ». Les données restent conservées et le compte peut accéder aux écrans de connexion, d'abonnement, d'export et de suppression.
- La reprise d'accès intervient uniquement après confirmation serveur d'un abonnement payé/actif par le fournisseur de paiement. Aucun renouvellement ou paiement automatique ne doit être déclenché à l'inscription.
- Les comptes existants ne doivent pas être bloqués par surprise lors de l'introduction de la fonctionnalité : prévoir une période de transition ou une activation explicite de la politique après vérification des comptes existants.

## Identité et anti-multicompte

- Conserver OIDC comme mécanisme d'authentification principal : l'e-mail seul n'est pas une preuve d'identité.
- Exiger `email_verified=true` du jeton OIDC avant de démarrer l'essai ou d'activer une clé.
- Lier définitivement l'essai à l'identité stable `(issuer, subject)` et réserver atomiquement l'adresse e-mail vérifiée : une même adresse normalisée ne peut pas démarrer un second essai sur un autre compte OIDC.
- Normaliser l'e-mail côté serveur pour les communications et contrôles, sans appliquer de règles spécifiques à Gmail (points ou suffixes +) qui pourraient fusionner des personnes différentes.
- Une clé d'accès est un mécanisme d'invitation/activation facultatif, pas un substitut à l'authentification. Elle doit être aléatoire, à usage unique, stockée sous forme de hash, limitée dans le temps si nécessaire, et consommée atomiquement dans une transaction.
- Une clé ne doit jamais permettre de réinitialiser l'essai d'une identité déjà utilisée. La détection d'abus doit utiliser des signaux proportionnés, avec limites de débit et revue manuelle plutôt qu'une empreinte invasive du terminal.
- Ne pas imposer le téléphone ou une pièce d'identité pour l'essai initial : cela créerait une friction excessive et un traitement de données disproportionné.

## Dix privilèges fondateurs

- Réserver exactement dix attributions individuelles « fondateur à vie ».
- Une attribution est associée à une identité OIDC vérifiée et conserve son historique d'audit.
- Une place est réservée au propriétaire fondateur ; neuf restent non attribuées jusqu'à décision expresse du propriétaire.
- Ces privilèges sont distincts des sièges d'organisation, des plans commerciaux, des abonnements Stripe et des clés d'essai.
- Les dix bénéficiaires sont exemptés de l'expiration des 72 heures et disposent des fonctions premium présentes et futures prévues par l'application.
- La contrainte de dix attributions doit être garantie en base par transaction/verrou, pas seulement par le frontend.
- Les attributions/révocations sont des opérations administratives explicites et auditées. Aucun endpoint public ne peut créer un privilège fondateur.
- Ne pas attribuer la place réservée au propriétaire tant que le compte OIDC réel n'a pas été confirmé côté serveur.

## Autorisation serveur

Ordre de priorité recommandé :
1. Compte actif et identité OIDC valide.
2. Privilège fondateur individuel actif : accès exempté des règles commerciales.
3. Abonnement payé actif, confirmé côté serveur.
4. Essai unique en cours : accès découverte.
5. Sinon : accès applicatif suspendu, tout en laissant accessibles authentification, facturation, export et suppression.

Les vérifications doivent être centralisées dans une dépendance d'autorisation commune, appliquée à toutes les routes métier et aux téléchargements. Les routes de facturation, de connexion, de récupération, d'export et de suppression doivent rester accessibles après expiration.

## Paiement et coûts

- Le checkout peut être proposé après l'essai, mais Stripe reste désactivé par défaut tant que l'exploitant n'a pas explicitement validé la configuration et les coûts.
- Ne jamais déclencher de paiement à la fin de l'essai.
- Le libellé « gratuit » ne garantit pas l'absence de coûts d'infrastructure ou d'API pour l'éditeur : prévoir des garde-fous de consommation et des plafonds anti-abus côté fournisseur.
- Les crédits des plans commerciaux ne sont pas considérés comme un portefeuille opérationnel tant que le ledger transactionnel n'existe pas.

## Conditions de livraison

Ne pas activer cette politique en production avant :
- migration additive relue et sauvegardée ;
- vérification du schéma réel users/subscriptions et des politiques RLS ;
- tests unitaires offline sur expiration, concurrence, consommation unique des clés et privilèges fondateurs ;
- tests d'intégration avec base de test isolée ;
- inventaire de toutes les routes métier et des téléchargements pour éviter un contournement ;
- période de transition définie pour les comptes déjà existants ;
- validation explicite du propriétaire avant migration, activation du paiement ou déploiement.

## État de l'implémentation sur la branche de travail

La branche `feature/72h-trial-founder-access-design` contient désormais :
- migration additive `020_account_trial_founder_entitlements.sql` et son rollback ;
- démarrage idempotent de l'essai au premier appel d'identité OIDC avec e-mail vérifié ;
- réservation atomique d'une adresse e-mail vérifiée pour un seul essai ;
- contrôle serveur partagé dans le contexte locataire, avec réponse 402 après expiration ;
- accès maintenu aux routes d'identité, d'état d'accès et de facturation ;
- table des dix places fondateurs, historique conservé des attributions/révocations, verrou transactionnel et fonctions d'administration ;
- routes d'administration des places 2 à 10 ; la place 1 reste réservée au propriétaire ;
- tests contractuels offline ajoutés, mais non exécutés.

Les clés d'activation ne remplacent pas l'identité OIDC et ne sont pas requises pour l'essai général. Le mécanisme anti-multicompte livré ici limite à un essai par adresse e-mail vérifiée exacte ; il ne peut pas garantir qu'une personne ne crée jamais plusieurs adresses e-mail distinctes. Les clés d'invitation ponctuelles peuvent être ajoutées pour des campagnes ou invitations privées ultérieures.

La migration n'a pas été appliquée, aucun service n'a été déployé et aucun fournisseur payant n'a été appelé.
