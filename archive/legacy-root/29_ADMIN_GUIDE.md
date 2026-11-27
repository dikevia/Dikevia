# Manuel administrateur — Console SaaS et organisation

## 1. Rôles

Les rôles métier sont attribués dans le périmètre d'une organisation. Les permissions effectives sont contrôlées côté API et en base ; masquer un bouton dans le navigateur ne constitue jamais une autorisation.

- **Administrateur plateforme** : opérations globales sur les espaces clients, accès offerts et suspension/réactivation selon les routes protégées de la console plateforme. Ce rôle doit être provisionné hors API via `database/bootstrap_platform_admin.sql`.
- **Administrateur d'organisation** : gestion des membres, invitations et paramètres autorisés de son espace.
- **Éditeur juridique** : opérations d'édition juridique permises par les dépendances d'autorisation.
- **Membre** : accès aux fonctionnalités de travail permises dans son organisation.

Consulter les routes réellement disponibles dans `docs/06_API_CONTRACT.md` et les contrôles dans `backend/app/dependencies.py` avant d'accorder un rôle. Le rôle Keycloak authentifie l'identité ; les appartenances et rôles métier sont conservés et vérifiés dans PostgreSQL.

## 2. Créer un espace client

1. S'authentifier avec le compte plateforme préalablement autorisé.
2. Ouvrir la console d'administration plateforme.
3. Créer l'organisation avec un identifiant/slug unique et un nom explicite.
4. Vérifier son statut et l'offre initiale.
5. Inviter le premier administrateur de l'organisation via le flux d'invitation.
6. Vérifier l'acceptation de l'invitation et la présence d'une adhésion active.

Ne jamais créer manuellement des adhésions en contournant les fonctions transactionnelles de la plateforme.

## 3. Accès gratuit, suspension et réactivation

Les accès gratuits sont attribués par la console plateforme et doivent avoir un motif et, lorsqu'il y a lieu, une échéance. Une suspension bloque l'accès selon les contrôles serveur ; elle ne doit pas servir à supprimer les données. Réactiver uniquement après vérification de la demande et tracer le motif opérationnel.

## 4. Abonnements et sièges

Les codes d'offre, prix et plafonds doivent rester définis côté serveur dans `backend/app/billing.py`. Le navigateur ne doit jamais être la source du prix. Les événements Stripe doivent être reçus par le webhook et leur signature validée. Utiliser les clés de test en préproduction. Avant ouverture commerciale, vérifier facturation, TVA, factures, résiliation, impayés, remboursement et obligations contractuelles avec un professionnel compétent.

## 5. Invitations et départs

Inviter l'adresse professionnelle/personnelle confirmée par le membre, attribuer le rôle minimal nécessaire et vérifier l'acceptation. À la sortie d'un membre, désactiver son adhésion dans l'organisation concernée et vérifier les accès. Ne pas supprimer l'identité globale si la personne appartient à un autre syndicat.

## 6. Contrôles périodiques

- Revoir les membres et rôles au moins chaque trimestre.
- Vérifier les invitations en attente et les accès gratuits arrivant à échéance.
- Contrôler les journaux d'administration et les événements de paiement.
- Tester régulièrement la restauration des sauvegardes.
- Vérifier les alertes de santé et l'espace disque.
- Ne jamais partager les comptes d'administration plateforme.
