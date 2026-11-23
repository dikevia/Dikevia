# Dikévia — checklist de mise en service de la bêta privée

**État documentaire : 23 novembre 2026.** Cette checklist distingue le code validé par CI, les contrôles réellement exécutés sur le staging et les opérations qui restent à faire. Elle ne constitue ni une certification juridique ni une déclaration de mise en production.

## 1. Périmètre bêta

- Bêta privée et gratuite, limitée aux personnes expressément autorisées.
- La configuration applicative prévoit par défaut `BETA_MAX_USERS=1`, `PRIVATE_INSTANCE_MODE=false`, `STRIPE_BILLING_ENABLED=false`. Ces valeurs sont des valeurs par défaut du code ; vérifier les variables réellement injectées dans chaque environnement avant toute ouverture.
- Ne pas activer Stripe, les recharges, les allocations automatiques de crédits ou les droits fondateur sans décision et vérification explicites.
- L'accès fondateur est lié à une identité OIDC vérifiée (`issuer` + `subject`), jamais à une adresse e-mail seule. La migration 026 ne donne aucun droit par elle-même : aucune attribution ne doit être supposée.
- Le benchmark juridique doit rester distinct des tests techniques. Les tests automatisés ne constituent pas une certification de fiabilité juridique.

## 2. État du code et de la CI

- La branche de référence est `main`. La branche de consolidation `feature/dikevia-free-vector-search-poc` a été réalignée sur le commit de `main) après intégration de la PR #65.
- La CI du 23 novembre 2026 a réussi : **841 tests passés, 1 avertissement**. La suite comprend les tests unitaires, contrats, tests PostgreSQL/RLS, lint, analyse statique de sécurité, audit des dépendances, scripts, Docker Compose et construction du kit développeur.
- La CI a également vérifié le staging Neon dédié : rôle d'ingestion attendu, schéma `vector(384)), et **5 640 fragments sur 5 640 avec vecteur**, sans incohérence de modèle/dimension.
- Le job d'embeddings n'a rien recalculé : il a constaté qu'aucun fragment n'était dépourvu de vecteur.
- Les tests live API/OIDC/Render et le parcours commercial ont été ignorés. La CI verte ne les remplace pas.

## 3. PostgreSQL et Neon

- Les migrations versionnées vont jusqu'à 026. La CI les applique à une base PostgreSQL jetable ; cela ne signifie pas qu'elles ont été appliquées à la base Neon réelle.
- Avant toute migration réelle : vérifier la branche Neon cible, l'état des migrations, la sauvegarde restaurable, les rôles et les droits minimaux.
- Ne jamais exécuter un import de corpus ou une migration sur la base de production sans contrôle préalable et autorisation explicite.
- Maintenir trois identités distinctes : application, ingestion du corpus et administration plateforme. Les rôles applicatifs ne doivent pas être propriétaires des tables, SUPERUSER ou BYPASSRLS.
- Le corpus staging contrôlé par la CI possède 5 640 fragments et 5 640 embeddings 384 dimensions au moment de la vérification. Ce constat ne prouve pas que le corpus est exhaustif, juridiquement à jour ou intégralement pertinent.

## 4. Identité, accès et Keycloak

- Vérifier en conditions réelles issuer, audience, JWKS, expiration, PKCE S256, URI de redirection, logout, révocation et restauration de session.
- Tester les comptes sans adhésion, suspendus, invités, administrateurs et changements d'organisation.
- La récupération d'administrateur Keycloak est une opération hors ligne qui exige l'arrêt de tous les nœuds connectés à la base. La procédure est documentée dans `deploy/keycloak/ADMIN-RECOVERY.md`.
- La procédure n'a pas été exécutée. Le workflow de récupération reste volontairement en brouillon ; il ne doit pas être lancé avant configuration des secrets, validation de la connectivité, plan de retour arrière et fenêtre d'interruption.
- Ne jamais activer l'auto-inscription publique pour contourner un problème d'administration.

## 5. Chatbot et qualité juridique

- Vérifier que chaque réponse distingue les faits, les hypothèses, les règles applicables et les points restant à confirmer.
- Contrôler les références officielles, leur version temporelle, leur champ FPT/FPE/FPH et l'adéquation entre l'extrait cité et l'affirmation.
- Les sources éditoriales (CIG, CDG, CNFPT, etc.) doivent rester distinguées des textes normatifs et de la jurisprudence.
- Tester les relances conversationnelles, les réponses courtes, les demandes ambiguës, les situations composées et la conservation du contexte.
- Effectuer un benchmark juridique avec un jeu de cas documenté et une revue humaine. Ne pas annoncer un taux de fiabilité sans protocole, corpus de référence et résultats reproductibles.
- Vérifier les réponses lorsque PISTE ou le fournisseur IA est indisponible ; les erreurs externes ne doivent pas produire de références inventées ni de fausse assurance.

## 6. Documents et confidentialité

- Vérifier le stockage privé, les permissions tenant, les limites de taille, l'analyse antivirus et les procédures de suppression/rétention.
- La transmission de documents locaux à un fournisseur IA doit rester désactivée par défaut et soumise à un consentement explicite pour la demande concernée.
- Tester les fichiers malformés, sans texte, trop volumineux, non validés, hors période ou appartenant à une autre organisation.
- Les diagnostics externes au démarrage doivent rester opt-in et expurger les secrets et données personnelles.

## 7. Render et mise en service

- Le service staging `dikevia-vector-beta-staging` est configuré avec déploiement automatique désactivé. Il pointe encore vers `feature/dikevia-free-vector-search-poc`, branche qui doit rester disponible tant que Render la référence.
- Le dernier déploiement staging observé précédait la consolidation finale. Un nouveau déploiement manuel du staging est requis pour tester le commit consolidé ; aucun déploiement de production n'est autorisé par cette checklist.
- L'API commerciale `dikevia-commercial-api-l2r8` reste sur sa branche dédiée. Ne pas modifier sa branche, ses variables ou son déploiement dans le cadre de la recette staging.
- Exécuter les contrôles live de readiness, chat, authentification, OIDC, citations, historique, documents, facturation désactivée et parcours administrateur.
- Vérifier les journaux et métriques, les erreurs 4xx/5xx, les redémarrages, la mémoire et la disponibilité du service après déploiement.

## 8. Critères de sortie

La bêta ne peut être déclarée prête que lorsque les points suivants sont documentés comme réussis :

- [ ] Déploiement du commit consolidé sur le staging, puis vérification de readiness.
- [ ] Tests live OIDC et authentification réelle.
- [ ] Tests live du chatbot avec contrôle des citations et des relances.
- [ ] Vérification PISTE et du fournisseur IA, y compris leur indisponibilité.
- [ ] Vérification de l'isolation des comptes, conversations, organisations et documents.
- [ ] Vérification des paramètres réels de coût, de facturation et de plafond de comptes.
- [ ] Recette juridique humaine sur un jeu de situations représentatif.
- [ ] Procédure de sauvegarde, restauration et retour arrière testée.
- [ ] Confirmation écrite du périmètre des personnes autorisées.

**État à la date de rédaction : non prête à être déclarée opérationnelle.** Les validations CI et le contrôle des embeddings staging sont réussis, mais les contrôles live OIDC/API, la recette juridique humaine et le déploiement final staging restent à effectuer.
