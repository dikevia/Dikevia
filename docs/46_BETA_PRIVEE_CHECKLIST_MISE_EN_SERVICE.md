# Dikévia — checklist de mise en service de la bêta privée

## Décision de périmètre

Cette bêta est privée, gratuite, réservée au propriétaire et à ses développeurs de confiance. Le benchmark juridique quantitatif du chatbot est reporté à une recette ultérieure par un développeur. Sa fiabilité est une hypothèse de travail, pas un résultat de test ni une certification.

- Aucun paiement Stripe n'est activé.
- Aucune ouverture commerciale ni souscription n'est nécessaire.
- Le plafond global temporaire reste à 1 identité (BETA_MAX_USERS=1).
- Le mode instance privée (PRIVATE_INSTANCE_MODE=true) coupe les routes de paiement et applique le plafond propre à l'instance de 10 adhésions ; le plafond global bêta reste une protection supplémentaire.
- Le mode Android actuel est une WebView de démonstration. Ne pas distribuer l'APK comme application prête à l'emploi avant une authentification Android validée.

## État connu du dépôt

Le dépôt contient le backend FastAPI, le frontend web/PWA, les migrations PostgreSQL, les rôles runtime/ingestion/administration, le flux OIDC PKCE, les conversations persistées, les documents cloisonnés par organisation, le contrôle antivirus ClamAV, les recherches CGFP/Légifrance et les garde-fous juridiques.

La CI historique documentée couvre une base PostgreSQL éphémère et les tests automatisés sur les commits explicitement listés dans les preuves CI. Elle ne prouve pas la disponibilité actuelle de Neon, du fournisseur OIDC, des identifiants PISTE, du fournisseur IA, du stockage objet ou d'un déploiement Render.

## Préconditions techniques à compléter dans l'environnement cible

Ces actions exigent les accès et secrets du propriétaire et ne sont pas réalisées par ce changement documentaire.

### 1. Comptes et coûts
- [ ] Confirmer que les plans Render/Neon/stockage réellement utilisés sont gratuits ou sans coût dans les limites prévues. Ne pas réveiller un compute ni lancer une opération facturable sans vérification.
- [ ] Confirmer que les quotas PISTE et fournisseur IA ne génèrent pas de coût pour la bêta.
- [ ] Garder Stripe non configuré : STRIPE_SECRET_KEY et STRIPE_WEBHOOK_SECRET vides.
- [ ] Ne pas activer l'offre commerciale ni les recharges de crédits.

### 2. PostgreSQL / Neon
- [ ] Vérifier la sauvegarde et la possibilité de restauration avant toute migration.
- [ ] Vérifier la version et l'état des migrations ; appliquer les migrations manquantes dans l'ordre jusqu'à 019, avec le rôle de migration dédié.
- [ ] Vérifier les trois rôles distincts : cfdt_juris_app, cfdt_juris_ingest et cfdt_juris_platform_admin. Aucun ne doit être propriétaire des tables, superutilisateur ou BYPASSRLS.
- [ ] Vérifier DATABASE_URL, LEGAL_CORPUS_INGEST_DATABASE_URL et PLATFORM_ADMIN_DATABASE_URL et leurs privilèges minimaux.
- [ ] Exécuter les tests PostgreSQL/RLS et le test de capacité 019 sur une base jetable, jamais sur les données de la bêta.

### 3. Identité et accès
- [ ] Vérifier issuer, audience, JWKS, HTTPS, PKCE S256, redirect URI et logout avec le véritable fournisseur OIDC.
- [ ] Amorcer l'identité du propriétaire dans platform_admins hors API ; vérifier issuer et subject exacts.
- [ ] Tester connexion, expiration, révocation, accès sans adhésion, utilisateur suspendu, changement d'organisation et récupération d'accès.
- [ ] Ne jamais placer de secret OIDC dans le frontend ou dans Git.
- [ ] Renouveler les secrets qui ont pu être exposés dans des échanges antérieurs.

### 4. Corpus juridique et chatbot
- [ ] Confirmer que le corpus CGFP est présent et que son import a été exécuté dans la base cible avec le rôle ingestion ; contrôler les comptes et statuts.
- [ ] Configurer PISTE sandbox sans activer le texte intégral CETAT tant que le contrat n'est pas validé.
- [ ] Configurer le fournisseur IA uniquement après confirmation explicite de l'absence de coût et de la politique de traitement des données.
- [ ] Garder le benchmark 100 questions reporté ; conserver les garde-fous de citations, temporalité et champ FPT.
- [ ] Présenter clairement les réponses comme une aide documentaire et non comme un avis juridique certifié.

### 5. Documents et confidentialité
- [ ] Vérifier le stockage privé, les permissions, les limites de taille et l'isolation tenant.
- [ ] Vérifier ClamAV réel ; en cas d'indisponibilité, l'import doit échouer fermé.
- [ ] Tester PDF et DOCX propres, fichiers rejetés, fichiers sans texte, documents d'une autre organisation, documents non validés et documents hors période.
- [ ] Garder la transmission des documents locaux à l'IA désactivée par défaut ; ne l'activer qu'avec consentement explicite et validation de confidentialité.
- [ ] Vérifier suppression, rétention, sauvegarde et restauration des documents.

### 6. Interface et appareils
- [ ] Tester les parcours web sur ordinateur et Android : connexion, tableau de bord, chat, citations, historique, recherche, documents, paramètres et déconnexion.
- [ ] Vérifier l'installation PWA et l'écran hors ligne ; aucune donnée privée/API ne doit être mise en cache.
- [ ] Ne pas distribuer l'APK WebView comme version finale. La TWA nécessite domaine HTTPS vérifié, assetlinks.json, package/signature cohérents et authentification testée.

### 7. Recette finale
- [ ] Exécuter la CI complète sur la tête de branche retenue : tests, Ruff, Bandit, pip-audit, migrations PostgreSQL 16, tests RLS, shell, Docker et build Android si conservé.
- [ ] Effectuer une recette manuelle avec le propriétaire et les développeurs autorisés.
- [ ] Vérifier logs, erreurs, limites de débit, sauvegarde et procédure de retour arrière.
- [ ] Consigner les résultats observés, les versions et les anomalies avant de déclarer la bêta opérationnelle.

## Critères de sortie bêta

La bêta ne peut être déclarée opérationnelle que lorsque les préconditions bloquantes ont été vérifiées sur l'environnement réellement utilisé. Un test CI vert ne remplace pas les tests OIDC/PISTE/IA/Neon/stockage réels. Une hypothèse de fiabilité du chatbot ne remplace pas le benchmark reporté.

## Ce que ce dépôt ne peut pas faire sans action du propriétaire

Les secrets et autorisations de comptes, l'amorçage du premier administrateur, les migrations sur Neon, l'import réel du corpus, les configurations PISTE/IA/SMTP/stockage, les sauvegardes et le déploiement nécessitent des décisions et accès externes. Ce document ne les marque pas comme accomplis et ne déclenche aucune opération facturable.