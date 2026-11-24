# Dikévia — état de préparation de la bêta

**Date de contrôle : 24 novembre 2026**  
**Branche commerciale déployée :** `feature/dikevia-v3.38.5-cgfp-chat`

Ce document distingue les contrôles réellement effectués des fonctions qui restent à valider. Il ne constitue pas une certification juridique.

## État opérationnel contrôlé

- API commerciale Render : déploiement en ligne, `/ready` répond `200`.
- Identité : Keycloak/OIDC conservé pour la bêta. La découverte OIDC, les JWKS, PKCE, l'URI de retour et la configuration dynamique ont passé les smoke tests live. La connexion avec un compte utilisateur réel reste à effectuer.
- Realm Keycloak : auto-inscription désactivée et vérification d'e-mail exigée. La configuration SMTP et le client de service Keycloak nécessaires au provisionnement automatique ne sont pas confirmés. En mode manuel, un administrateur doit donc créer et vérifier le compte dans Keycloak avant que l'invitation Dikévia puisse être acceptée.
- Identifiant public OIDC : `cfdt-juris-web`, fixé dans le Blueprint commercial.
- Sources légales : PISTE/Légifrance en **Production**. Les sondes de démarrage CGFP L.111-1, Code civil 1217 et les trois sondes IHTS ont retourné des références exactes et des textes intégraux.
- IA : Gemini `gemini-2.5-flash` configuré ; le catalogue du fournisseur répond `AVAILABLE`. Cela ne remplace pas un test de génération réelle avec une session utilisateur.
- Capacité bêta : plafond global de 100 comptes, appliqué côté serveur aux membres actifs, administrateurs plateforme et invitations en attente. Ce plafond n'est pas une garantie de 100 connexions simultanées.
- Contrôle de capacité en production : fonction SQL présente ; un test de disponibilité d'invitation pour un nouvel e-mail de test a retourné `true`.

## Corpus et fiabilité juridique

- L'image Docker commerciale embarque un index CGFP daté du 31 octobre 2026, utilisé pour la découverte des références et confronté aux recherches PISTE en direct.
- La base PostgreSQL commerciale ne contient actuellement aucun enregistrement dans `legal_documents` ou `legal_chunks`. Les documents et embeddings complémentaires restent en préproduction.
- En préproduction : 4 459 documents, 5 640 segments et 5 640 embeddings présents ; contrôles de texte et de SHA-256 réussis.
- Audit des 217 documents de guidance : classification d'autorité effectuée ; aucune guidance n'est autorisée à soutenir seule une affirmation juridique.
- Recherche vectorielle : audit technique sur quatre questions exécuté, mais la pertinence sémantique n'est pas certifiée. Elle reste désactivée en production.
- Recherche plein texte de jurisprudence administrative CETAT : désactivée en production en attente de validation métier.
- Les réponses juridiques doivent afficher et respecter les sources officielles et leur période d'applicabilité. Les snapshots non vérifiés ne doivent pas être présentés comme preuve autonome du droit en vigueur.

## Documents et confidentialité

- La table `personal_documents` existe en production ; RLS est activé et forcé avec une politique propriétaire basée sur `app.current_user_id`.
- Aucun document personnel n'est présent en production.
- Les imports de documents personnels et d'organisation sont désactivés dans l'interface bêta, car aucun scanner antivirus dédié n'est déployé sur l'hébergement actuel. Le backend doit rester fail-closed.
- Les 49 PDF locaux de Saint-Étienne ne sont pas transférés en production.

## Applications Android

- Deux APK ont été compilés et validés par GitHub Actions : Standard et Administration.
- Ce sont des conteneurs WebView signés en mode debug, pas des applications natives finalisées ni des versions Play Store.
- Le test d'installation sur un appareil Android physique reste à effectuer.
- L'application Administration nécessite le rôle d'administrateur plateforme.

## Limites commerciales et actions avant démonstration

- La souscription et le paiement en ligne sont désactivés ; l'onboarding des premières sections doit être manuel.
- La migration Auth0 n'est pas activée en production ; Keycloak reste le fournisseur runtime de la bêta.
- Une vraie connexion utilisateur et une première génération IA doivent être testées avant de présenter le chatbot comme validé.
- Les réponses du benchmark juridique de 15 questions n'ont pas encore de corrigés de référence validés par un humain ; le gate d'évaluation reste incomplet.
- Les services Render gratuits peuvent subir un démarrage à froid. Ouvrir l'application quelques minutes avant la démonstration.

## Décision

La version actuelle est une **bêta démontrable techniquement**, avec authentification Keycloak contrôlée, accès PISTE Production et protections de données vérifiées. Elle ne doit pas être présentée comme une version SaaS finale certifiée : génération IA réelle, validation humaine des réponses, paiement, import documentaire antivirus, Auth0 et pertinence vectorielle restent des chantiers distincts.
