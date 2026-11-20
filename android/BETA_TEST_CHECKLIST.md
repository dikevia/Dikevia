# Dikévia Android beta — checklist de validation

Ce document distingue les contrôles automatisés des validations qui nécessitent un environnement réel. Ne pas cocher une étape sur la seule base d'une compilation.

## 1. Contrôles automatisés (GitHub Actions)

La compilation de l'APK de bêta est déclenchée automatiquement à chaque mise à jour Android de cette branche.

- [ ] Compilation ` :app:assembleDebug` terminée avec succès.
- [ ] Test Compose instrumenté sur émulateur terminé avec succès.
- [ ] APK non vide, archive ZIP valide et artifact téléversé.
- [ ] CI backend : lint, analyse statique, audit des dépendances, tests unitaires/contrats et tests PostgreSQL/RLS réussis.

## 2. Configuration Keycloak — administrateur requis

- [ ] Realm `cfdt` accessible sur l'issuer configuré dans l'application.
- [ ] Client `dikevia-android` de type public, Authorization Code activé, Direct Access Grants et Implicit Flow désactivés.
- [ ] PKCE S256 obligatoire.
- [ ] URI de redirection exacte : `fr.dikevia.commercial:/oauth2redirect`.
- [ ] Audience `cfdt-juris-api` présente dans le jeton d'accès.
- [ ] L'endpoint OIDC de fin de session est publié et accepte l'URI de retour.

Ne jamais embarquer de secret client dans l'APK. Ne pas modifier le realm hébergé sans autorisation explicite.

## 3. Parcours réel sur un appareil Android

- [ ] Installer l'APK debug et vérifier l'ouverture sans crash.
- [ ] Se connecter avec un compte de test autorisé et vérifier le retour navigateur vers l'application.
- [ ] Vérifier le profil et les organisations retournés par l'API.
- [ ] Vérifier qu'un compte membre ne voit pas l'écran Membres et qu'un administrateur y accède.
- [ ] Poser une question juridique de test ; vérifier réponse, statut de vérification, sources et avertissements.
- [ ] Ouvrir une conversation de l'historique, la reprendre, puis vérifier la conservation des messages précédents.
- [ ] Changer d'organisation et vérifier qu'aucun contexte de conversation de l'organisation précédente ne subsiste.
- [ ] Vérifier l'affichage des métadonnées des documents et collectivités.
- [ ] Attendre le renouvellement d'un jeton et confirmer que les appels API continuent sans reconnexion.
- [ ] Se déconnecter et vérifier la fermeture de session du fournisseur d'identité.
- [ ] Relancer l'application après fermeture complète : une reconnexion est attendue dans cette version.

## 4. Validation métier et juridique avant diffusion

- [ ] Faire relire un échantillon représentatif de réponses FPT par un juriste compétent.
- [ ] Vérifier manuellement chaque référence juridique, sa date de validité et la cohérence entre les citations et les affirmations.
- [ ] Tester les cas incomplets, les dates ambiguës, les règles locales et les questions hors périmètre.
- [ ] Confirmer les limites fonctionnelles affichées aux testeurs (documents en métadonnées uniquement, pas de téléchargement).

## État

Une case non testée reste non validée. La compilation et les tests d'interface ne remplacent ni le test OIDC réel, ni les essais sur appareil physique, ni la revue juridique humaine.
