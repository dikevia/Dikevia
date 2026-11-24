# Dikévia — état de préparation de la bêta

**Contrôle actualisé : 24 novembre 2026, 23:30 UTC**  
**Branche commerciale :** `feature/dikevia-v3.38.5-cgfp-chat`  
**Dernier commit commercial observé en production :** `f9aadba451e67157ae41ade32190d5eaa0e5bed5`

Ce document distingue les contrôles effectués, les limites connues et les validations encore nécessaires. Il ne constitue ni une certification juridique ni une garantie de capacité.

## 1. Production et sécurité opérationnelle

- API commerciale Render : dernier déploiement terminé avec succès ; les contrôles live API/OIDC/site ont réussi sur le code correspondant.
- Identité runtime : `OIDC_PROVIDER=keycloak`, explicitement fixé dans le Blueprint commercial. Auth0 n'est pas activé.
- Smoke tests Keycloak : découverte OIDC, issuer, JWKS, PKCE, configuration navigateur et rejet des appels protégés anonymes ou munis d'un bearer invalide réussis.
- Une connexion avec un véritable compte utilisateur et une session complète dans l'application restent à effectuer.
- Provisionnement automatique : non opérationnel. Le diagnostic du 24/11 a établi `smtp_configured=False` et `keycloak_admin_configured=False`. Les invitations restent manuelles : un administrateur Keycloak doit créer et vérifier le compte avant acceptation du jeton Dikévia.
- Plafond bêta : 100 comptes au total, invitations en attente comprises. Ce plafond ne garantit pas 100 connexions simultanées et ne permet pas de promettre une capacité de 250 clients actifs.
- Les sondes externes PISTE et catalogue IA au démarrage sont désactivées explicitement. Cela évite de consommer des appels externes à chaque redémarrage ; les appels réglementaires nécessaires aux requêtes utilisateurs restent disponibles.
- Les flags de production sont épinglés : recherche vectorielle désactivée, revue IA de documents désactivée, paiement Stripe désactivé, import de documents désactivé tant que le scanner antivirus n'est pas disponible.

## 2. Fournisseur IA et fiabilité conversationnelle

- Fournisseur configuré : API Google Gemini compatible OpenAI, modèle principal `gemini-2.5-flash`, modèle de secours `gemini-2.5-flash-lite`.
- Le catalogue fournisseur a répondu `AVAILABLE` lors du diagnostic du 24/11. Un catalogue accessible ne prouve pas qu'une génération réelle fonctionne.
- La matrice de résilience HTTP a des tests simulés : 401/403/429 sans retry ni bascule, 500 avec retry borné, 503 avec bascule contrôlée vers le modèle de secours. Aucun appel externe ni quota n'est consommé par ces tests.
- Les événements de production du 20 au 22/11 contiennent 16 erreurs fournisseur historiques, antérieures à la configuration directe Google. Les derniers échanges assistant enregistrés avant le changement de fournisseur étaient marqués `NON_VERIFIE`. Aucune génération utilisateur réelle postérieure au changement de fournisseur n'a encore été validée.
- Les tests automatisés couvrent le contexte multi-tour, les demandes de clarification, la séparation FPT/FPE/FPH, les citations, l'applicabilité temporelle, le lien affirmations-preuves et l'abstention lorsque les preuves sont insuffisantes.
- Dernière CI complète observée : **1 176 tests réussis, 1 avertissement, aucun échec**. Les contrôles live OIDC/API/site ont également réussi.
- Les recherches ciblées CITIS et temps partiel thérapeutique sont séparées par versant : FPT, FPE et FPH. L'interface permet de préciser le ministère, le rectorat ou l'établissement hospitalier pour les questions FPE/FPH ; la validation serveur interdit les employeurs territoriaux dans ces deux versants.

## 3. Corpus, sources et recherche

### Production

- Légifrance/PISTE est configuré en environnement Production. Les contrôles effectués avant désactivation des sondes de démarrage ont retrouvé des références exactes et des textes intégraux pour plusieurs axes CGFP/IHTS.
- L'image commerciale embarque un snapshot CGFP daté du 31 octobre 2026, 1 024 pages, avec empreinte SHA-256 documentée.
- La base PostgreSQL commerciale ne contient actuellement aucun enregistrement dans `legal_documents` ou `legal_chunks`. Le chatbot s'appuie donc sur les sources officielles interrogées en direct et le snapshot embarqué, pas sur le corpus vectoriel de staging.
- La recherche plein texte CETAT reste désactivée en production en attente de validation métier et de son cadre de consultation.

### Staging

- 4 459 documents, 4 459 versions et 5 640 segments.
- 5 640 embeddings présents, modèle `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, dimension 384.
- 4 459 versions possèdent un texte intégral et une empreinte SHA-256 ; aucun groupe de doublons exacts par hash n'a été détecté dans l'audit.
- Index vectoriel HNSW présent et utilisé par le planificateur SQL.
- 217 documents de guidance audités : 199 Service Public et 18 ressources institutionnelles. Aucune guidance non normative n'est autorisée à soutenir seule une conclusion juridique.
- Les sources importées restent `IMPORTED_UNVERIFIED` : leur présence, leur extraction et leur indexation ne les transforment pas en preuves juridiques certifiées.
- Audit de recherche vectorielle en lecture seule : six questions de contrôle, cinq résultats retournés par question. Ce smoke test vérifie l'exécution et la couverture, pas la pertinence juridique.
- Parité FastEmbed/Transformers.js : 12 vecteurs comparés, similarité cosinus moyenne 0,9999991. La compatibilité numérique est vérifiée ; la pertinence sémantique métier ne l'est pas.
- Le flag vectoriel est activé uniquement sur le service de staging. Il reste désactivé en production tant que le corpus n'est pas validé et importé.

## 4. Documents privés et confidentialité

- L'archive privée Saint-Étienne contient 49 PDF, 382 pages : 44 ont une couche texte exploitable et 5 ont été traités par OCR français/anglais.
- Les OCR des tableaux indiciaires restent non vérifiés : leur confiance moyenne de reconnaissance est un indicateur technique, pas un taux d'exactitude. Les nombres, indices, dates et montants doivent être relus sur les PDF originaux.
- Une archive textuelle privée avec manifeste et empreintes SHA-256 a été produite. Aucun document ni texte de cette archive n'a été importé dans le corpus juridique partagé, la base de staging ou la base de production.
- Les imports de documents personnels et d'organisation restent désactivés. Aucun scanner antivirus dédié n'est déployé sur l'hébergement actuel ; le backend doit rester fail-closed.
- Les documents personnels doivent rester cloisonnés par utilisateur/organisation avec RLS ; aucune pièce locale ne doit devenir une source commune.

## 5. Applications Android

- APK Dikévia Standard et Dikévia Administration reconstruits et vérifiés par GitHub Actions.
- Build Gradle des deux variantes réussi ; artefacts publiés le 24/11.
- APK signés en mode debug, destinés au sideload bêta, pas au Play Store.
- L'application Administration est distincte et réservée au rôle administrateur plateforme ; elle ne contient pas le chatbot agents.
- Le test d'installation et de parcours sur appareil Android physique reste à effectuer.
- Les APK sont des conteneurs WebView : les évolutions de l'interface web apparaissent après déploiement du serveur, sans reconstruire l'APK.

## 6. Auth0, facturation et accès commerciaux

- Le tenant de développement Auth0, l'application SPA et l'API existent ; le code backend prend en charge issuer/audience/JWKS et PKCE.
- Les listes d'URL autorisées Auth0 doivent encore être resserrées. Aucun parcours de connexion Auth0 réel, aucune migration de comptes Keycloak et aucun basculement production ne sont validés.
- Keycloak reste explicitement le fournisseur runtime de la bêta.
- Les quatre offres commerciales sont présentes dans le catalogue de code, mais Stripe et le checkout restent désactivés.
- La fondation SQL du portefeuille de crédits existe ; les débits IA et allocations mensuelles ne sont pas activés, en attente de calibration des coûts et de validation du benchmark.
- Le droit fondateur premium n'est pas attribué dans la table dédiée. Il ne doit être accordé qu'après vérification de l'identité OIDC correspondante.
- L'onboarding de prospects doit donc rester manuel. La bêta actuelle n'est pas un tunnel de souscription autonome.

## 7. Benchmark — volontairement dernier

- Le dataset métier comporte 100 cas FPT ; aucun corrigé de référence n'est actuellement validé.
- Le pilote de 15 cas reste `NOT_EVALUATED`.
- Le benchmark doit être lancé seulement après finalisation des contrôles techniques, corpus, sources, identité et fournisseur IA.
- Gate proposé : 100 cas revus humainement, aucun échec critique, moyenne au moins 8,5/10, pertinence des questions au moins 95 %, support des sources au moins 98 %.
- Aucun score de fiabilité juridique ne doit être annoncé avant cette revue.

## Décision opérationnelle

Dikévia est une **bêta techniquement démontrable** : service commercial déployé, Keycloak/OIDC contrôlé, PISTE Production configuré, protections de données testées, recherche vectorielle évaluée en staging et APK Android disponibles.

Ce n'est pas encore un SaaS commercial entièrement autonome ni un assistant dont l'exactitude juridique est certifiée. Avant de promettre un déploiement à grande échelle, restent notamment : une vraie connexion utilisateur, une génération Gemini réelle post-configuration, la correction des paramètres Auth0, le provisionnement automatisé, le scanner antivirus, le portefeuille de crédits/paiement et, en dernier, le benchmark juridique humain.

Les services Render gratuits peuvent subir un démarrage à froid ; ouvrir les deux applications quelques minutes avant toute démonstration.
