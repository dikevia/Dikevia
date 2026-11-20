# Dikévia — checklist de mise en service de la bêta privée

## Décision de périmètre

Cette bêta est privée et gratuite, réservée au propriétaire et à ses développeurs de confiance. Le benchmark juridique quantitatif du chatbot est reporté à une recette ultérieure par un développeur. Sa fiabilité est une hypothèse de travail, pas un résultat de test ni une certification.

- Aucun paiement Stripe n'est activé.
- Aucune ouverture commerciale ni souscription n'est nécessaire.
- Le plafond global temporaire reste à 1 identité (BETA_MAX_USERS=1).
- Le mode instance privée (PRIVATE_INSTANCE_MODE=true) coupe les routes de paiement et applique le plafond propre à l'instance de 10 adhésions ; le plafond global bêta reste une protection supplémentaire.
- Le mode Android actuel est une WebView de démonstration. Ne pas distribuer l'APK comme application prête à l'emploi avant une authentification Android validée.

## État du code et des validations observées

La branche de cette PR est basée sur `feature/dikevia-v3.38.5-cgfp-chat`. La CI GitHub Actions n°1264 sur le commit de cette PR a réussi : compilation, audit de configuration, branding, lint, analyse statique de sécurité, audit des dépendances, tests unitaires/contrat, PostgreSQL/RLS jetable, scripts shell, Docker Compose et kit développeur. Le job Live API/OIDC/Render a été ignoré. Cette validation concerne uniquement le code de cette branche et ne valide aucun service externe.

**Attention : plusieurs correctifs de sécurité utiles à la bêta existent encore dans des PR distinctes non fusionnées.** Ils ne doivent pas être considérés comme présents dans la branche de cette PR tant qu'une branche d'intégration n'a pas été constituée et validée :
- PR #11 : cloisonnement explicite des conversations/dossiers par organisation et utilisateur, durcissement contre l'injection de prompt et protections de confidentialité ;
- PR #12 : consentement ponctuel avant transfert de documents locaux à l'IA, contrôle des extractions documentaires et désactivation par défaut des diagnostics externes au démarrage ;
- PR #14 : garde-fous de temporalité des preuves et de périmètre FPT, avec CI documentée à 391 tests ;
- PR #10 : refus des rôles PostgreSQL SUPERUSER/BYPASSRLS sur les pools applicatifs ;
- PR #13 : harmonisation du namespace OIDC Dikévia ;
- PR #5/#7/#8 : PWA, garde de cache hors ligne et préparation de la TWA Android.

Ces PR sont encore ouvertes. Certaines sont empilées les unes sur les autres ; les branches #10 et #11 sont signalées non fusionnables par GitHub à la date de cette vérification. Il faut résoudre leur intégration dans un ordre cohérent, puis relancer la CI sur la branche consolidée. Les succès CI de branches séparées ne prouvent pas que leur combinaison compile ni fonctionne.

Liens de suivi :
- https://github.com/dikevia/Dikevia/pull/10
- https://github.com/dikevia/Dikevia/pull/11
- https://github.com/dikevia/Dikevia/pull/12
- https://github.com/dikevia/Dikevia/pull/13
- https://github.com/dikevia/Dikevia/pull/14
- https://github.com/dikevia/Dikevia/pull/5
- https://github.com/dikevia/Dikevia/pull/7
- https://github.com/dikevia/Dikevia/pull/8

La CI historique documentée couvre des bases PostgreSQL éphémères et les commits explicitement listés dans les preuves CI. Elle ne prouve pas la disponibilité actuelle de Neon, du fournisseur OIDC, des identifiants PISTE, du fournisseur IA, du stockage objet ou d'un déploiement Render.

## Préconditions techniques à compléter dans l'environnement cible

Ces actions exigent les accès et secrets du propriétaire. Elles ne sont pas réalisées par cette PR.

### 1. Comptes et coûts
- [ ] Confirmer que les plans Render/Neon/stockage réellement utilisés sont gratuits ou sans coût dans les limites prévues. Ne pas réveiller un compute ni lancer une opération facturable sans vérification.
- [ ] Confirmer que les quotas PISTE et fournisseur IA ne génèrent pas de coût pour la bêta.
- [ ] Garder Stripe non configuré : STRIPE_SECRET_KEY et STRIPE_WEBHOOK_SECRET vides.
- [ ] Ne pas activer l'offre commerciale ni les recharges de crédits.

### 2. PostgreSQL / Neon
- [ ] Intégrer et valider le garde de rôles de la PR #10 avant la recette réelle.
- [ ] Vérifier la sauvegarde et la possibilité de restauration avant toute migration.
- [ ] Vérifier la version et l'état des migrations ; appliquer les migrations manquantes dans l'ordre jusqu'à 019, avec le rôle de migration dédié.
- [ ] Vérifier les trois rôles distincts : cfdt_juris_app, cfdt_juris_ingest et cfdt_juris_platform_admin. Aucun ne doit être propriétaire des tables, superutilisateur ou BYPASSRLS.
- [ ] Vérifier DATABASE_URL, LEGAL_CORPUS_INGEST_DATABASE_URL et PLATFORM_ADMIN_DATABASE_URL et leurs privilèges minimaux.
- [ ] Exécuter les tests PostgreSQL/RLS et le test de capacité 019 sur une base jetable, jamais sur les données de la bêta.

### 3. Identité et accès
- [ ] Intégrer le correctif OIDC de la PR #13 puis vérifier issuer, audience, JWKS, HTTPS, PKCE S256, redirect URI et logout avec le véritable fournisseur.
- [ ] Amorcer l'identité du propriétaire dans platform_admins hors API ; vérifier issuer et subject exacts.
- [ ] Tester connexion, expiration, révocation, accès sans adhésion, utilisateur suspendu, changement d'organisation et récupération d'accès.
- [ ] Ne jamais placer de secret OIDC dans le frontend ou dans Git.
- [ ] Renouveler les secrets qui ont pu être exposés dans des échanges antérieurs.

### 4. Corpus juridique et chatbot
- [ ] Intégrer les PR #11, #12 et #14 dans une branche consolidée et exécuter la CI complète sur cette combinaison.
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
- [ ] Intégrer et valider la PWA de la PR #5 ; aucune donnée privée/API ne doit être mise en cache.
- [ ] Tester les parcours web sur ordinateur et Android : connexion, tableau de bord, chat, citations, historique, recherche, documents, paramètres et déconnexion.
- [ ] Ne pas distribuer l'APK WebView comme version finale. La TWA nécessite domaine HTTPS vérifié, assetlinks.json, package/signature cohérents et authentification testée.

### 7. Recette finale
- [ ] Exécuter la CI complète sur la tête de branche consolidée : tests, Ruff, Bandit, pip-audit, migrations PostgreSQL 16, tests RLS, scripts shell, Docker et build Android si conservé.
- [ ] Effectuer une recette manuelle avec le propriétaire et les développeurs autorisés.
- [ ] Vérifier logs, erreurs, limites de débit, sauvegarde et procédure de retour arrière.
- [ ] Consigner les résultats observés, les versions et les anomalies avant de déclarer la bêta opérationnelle.

## Critères de sortie bêta

La bêta ne peut être déclarée opérationnelle que lorsque les correctifs de sécurité ont été intégrés, que la CI de la branche consolidée est verte et que les préconditions bloquantes ont été vérifiées sur l'environnement réellement utilisé. Un test CI vert ne remplace pas les tests OIDC/PISTE/IA/Neon/stockage réels. Une hypothèse de fiabilité du chatbot ne remplace pas le benchmark reporté.

## Ce que ce dépôt ne peut pas faire sans action du propriétaire

Les secrets et autorisations de comptes, l'amorçage du premier administrateur, les migrations sur Neon, l'import réel du corpus, les configurations PISTE/IA/SMTP/stockage, les sauvegardes et le déploiement nécessitent des décisions et accès externes. Ce document ne les marque pas comme accomplis et ne déclenche aucune opération facturable.
