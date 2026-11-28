# Dikévia — état fonctionnel et recette de la réunion du 28 novembre 2026

Ce document est un relevé technique du dépôt `main` consulté le 28 novembre 2026. Il distingue le code présent, les appels réellement raccordés et les validations encore nécessaires. Il ne vaut pas recette sur appareil ni preuve de disponibilité des services externes.

## 1. Application Android Standard : point d'entrée réel

- `android/app/build.gradle.kts` fixe `ENABLE_NATIVE_PREVIEW=false` en debug et release.
- `MainActivity.kt` démarre donc la WebView et charge `BuildConfig.APP_URL`, actuellement le frontend staging `https://dikevia-vector-beta-staging.onrender.com/?dikevia_app=standard`.
- L'écran Compose `NativeHomeScreen.kt` et `NativePreviewActivity.kt` sont des éléments de prévisualisation isolés ; ils ne sont pas l'interface utilisée par l'APK Standard construit avec cette configuration.
- En conséquence, toute recette des boutons doit être faite dans le frontend Web embarqué par la WebView. Le prototype Compose ne doit pas servir de preuve de fonctionnement de l'APK livré.

## 2. Parcours CST / CAP / CCP / F3SCT présent dans le frontend

Fichier principal : `frontend/index.html`.

- La navigation « Instances » mène à `#view-instances`.
- Quatre cartes portent `data-instance-choice` : CST, CAP, CCP et FS (libellé utilisateur F3SCT).
- Un gestionnaire de clic sélectionne l'instance dans `#instanceType`, déclenche le changement d'instance, met la carte active en évidence et fait défiler vers le formulaire.
- Le bouton `#prepareInstance` appelle `POST /api/v1/instances/{instance}/prepare`.
- Le résultat affiche les points de préparation, questions et documents, les qualifications CST/FS, les contrôles de calendrier disponibles et les recherches de sources juridiques.
- Le bouton « Continuer avec JURIS » transmet une synthèse de la préparation au chatbot général pour approfondissement. Cela conserve un chatbot unique.

### Spécificités déjà présentes

- CST : demande d'inscription à l'ordre du jour, effectifs de titulaires, délais de convocation et de transmission des documents, demandes de réunion, périodicité, articulation CST/FS et certains contrôles de procédure.
- FS/F3SCT : existence de la formation spécialisée, périodicité, consultation du secrétaire, échéances et questions de santé-sécurité.
- CAP : référentiel lexical et fiches de préparation comprenant notamment des cas de discipline, carrière et situations individuelles.
- CCP : référentiel lexical et fiches de préparation portant notamment sur les agents contractuels, discipline, licenciement, réemploi et recours.

## 3. Limite métier majeure : ce que fait réellement le backend

Fichiers : `backend/app/instances.py`, `backend/app/main.py`, tests `backend/tests/test_instances_legal_research.py`.

- L'endpoint est bien implémenté et appelle `prepare_instance_with_legal_sources`.
- Le moteur de préparation construit d'abord une checklist à partir de règles structurées et de mots-clés.
- Si PISTE Légifrance est configuré, trois familles de recherche sont exécutées : articles du CGFP, textes réglementaires et jurisprudence administrative.
- Si PISTE n'est pas configuré, le résultat le signale explicitement (`NOT_CONFIGURED`) et conserve uniquement la fiche lexicale.
- La recherche peut être partielle ou indisponible ; ces statuts sont renvoyés au frontend.
- Le module indique explicitement qu'il ne produit pas de conclusion juridique et ne détermine pas automatiquement la compétence ou la légalité.
- Le test existant vérifie que `legal_conclusion` reste faux et que la jurisprudence dont le texte intégral n'est pas récupéré est signalée comme métadonnée/extrait uniquement.
- L'endpoint dépend de `require_syndicate_subscription` : l'accès effectif dépend donc des droits et de l'organisation du compte.

**Conclusion :** les quatre entrées et un premier parcours de préparation existent. Ce n'est pas encore un système complet d'analyse d'un dossier d'instance. En particulier, la checklist et les recherches de sources ne remplacent pas l'analyse des pièces importées, la qualification juridique contradictoire, la rédaction complète d'un avis syndical ni la génération de tous les livrables PDF attendus.

## 4. Authentification Android

- Le lanceur Android livré est actuellement une WebView vers staging.
- La configuration Android inclut aussi un SDK Auth0 natif et des modules Compose, mais ils ne sont pas le point d'entrée actif dans cette variante.
- Le comportement Auth0 doit donc être testé sur l'APK Standard réellement installé, en observant le retour de connexion, la session, les appels API authentifiés et les erreurs réseau.
- Aucun changement de tenant Auth0 ni de secret n'est inclus dans cette recette.

## 5. JURIS, retrieval et reranking

État établi par l'audit précédent du code :

- Le reranker déterministe est appelé dans l'orchestrateur.
- Le cross-encoder ONNX est optionnel et désactivé par défaut ; son activation n'est pas présumée.
- La configuration du code active la recherche vectorielle par défaut, mais un paramètre d'environnement Render peut la désactiver.
- Le frontend calcule un embedding 384 dimensions via le worker navigateur et le transmet au backend.
- La parité numérique réelle entre le worker navigateur et le pipeline Python, ainsi que la pertinence sémantique du retrieval, ne sont pas certifiées.
- Le mécanisme de fallback en cas de HTTP 429 a été corrigé et les tests CI associés ont réussi.
- Les logs privacy-safe de l'orchestrateur doivent être consultés pour confirmer, requête par requête, si la recherche vectorielle est réellement exécutée.

## 6. Recette de réunion — ordre conseillé

### A. APK Standard et navigation (10 minutes)
1. Identifier la version exacte de l'APK installée.
2. Ouvrir l'application, terminer la connexion et accéder à « Instances ».
3. Cliquer successivement sur CST, CAP, CCP et F3SCT ; vérifier sélection, formulaire et changement d'instance.
4. Vérifier si l'action est bloquée par l'authentification, les droits ou l'absence d'organisation.

### B. Préparation des instances (20 minutes)
1. Tester un sujet représentatif par instance.
2. Vérifier la réponse HTTP, le contenu de la checklist et les statuts de recherche.
3. Vérifier que les sources sont datées, officielles et accessibles ; distinguer texte intégral et simple métadonnée de jurisprudence.
4. Cliquer « Continuer avec JURIS » et vérifier que le contexte de préparation est bien transmis au chatbot.

### C. Authentification (15 minutes)
1. Connexion initiale et retour dans la WebView.
2. Rechargement / fermeture / réouverture et persistance de session.
3. Vérifier les appels API, les statuts 401/403 et la reconnaissance du compte fondateur.
4. Noter l'écran exact et le message exact en cas d'échec ; ne jamais désactiver les vérifications OIDC.

### D. Chatbot et recherche (20 minutes)
1. Question simple : « C'est quoi l'IFSE ? »
2. Question de droit individuel avec date et statut d'agent.
3. Question de préparation CST ou F3SCT avec un ordre du jour réel anonymisé.
4. Vérifier sources, dates de validité, citations, demande de précision et continuité conversationnelle.
5. Contrôler dans les logs staging si pgvector s'est exécuté et si le fallback IA a été utilisé.

## 7. Critères de sortie

Un parcours n'est déclaré :
- **développé** que si le code correspondant existe ;
- **déployé** que si le commit est effectivement présent sur l'environnement ciblé ;
- **testé** qu'après une recette observable avec résultat reproductible.

Ne pas déclarer la fonctionnalité « opérationnelle » sur la seule base d'un écran visible ou d'un test unitaire isolé.

## 8. Périmètre de sécurité de cette tranche

Aucun déploiement Render, aucune modification de variable d'environnement ou de secret, aucune modification du tenant Auth0, aucune migration de base de données et aucune dépense de service tiers ne sont autorisés par ce document.
