# Dikévia Android — préversion bêta

Le projet Android fournit actuellement une coque de démonstration qui ouvre l'application web commerciale Dikévia en HTTPS dans une WebView.

- Identifiant d'application de debug : `fr.dikevia.commercial.beta` (suffixe de debug)
- SDK de compilation : Android 35
- Android minimum : API 24
- Version de base Gradle : `0.1.0-beta` ; le suffixe de build debug ajoute actuellement `-beta`.
- Construction actuelle : APK `debug`, signé automatiquement avec la clé debug de l'environnement de compilation.

## Statut de l'APK

La PR de préparation CI #8 ajoute une compilation Android automatisée et publie, après fusion de cette PR et exécution réussie du workflow, l'artefact :

- Nom : `dikevia-android-debug-signed`
- Fichier : `app-debug.apk`
- Conservation GitHub Actions : 7 jours

Cet artefact est destiné exclusivement aux essais techniques internes. La clé debug est éphémère et ne constitue pas une signature de distribution. Ne pas publier cet APK sur un store ni le considérer comme une version de production.

## Authentification et architecture cible

L'authentification actuellement documentée repose sur le client web OIDC Authorization Code + PKCE. La coque WebView ne constitue pas à elle seule une architecture Android de production validée.

La voie cible proposée est une Trusted Web Activity (TWA), sous réserve de confirmer :
- le domaine HTTPS définitif de l'application ;
- l'identifiant de paquet de publication ;
- le certificat de signature définitif et son empreinte SHA-256 ;
- le fichier Digital Asset Links (`/.well-known/assetlinks.json`) ;
- le parcours OIDC et les retours d'authentification sur un appareil réel.

Une authentification native AppAuth serait une autre architecture et demanderait un client OIDC Android dédié ainsi qu'une conception sécurisée du pont de session. Aucun de ces choix ne doit être simulé avec des valeurs fictives.

## Conditions avant distribution

- [ ] Décider et valider l'architecture TWA ou native.
- [ ] Fixer le domaine HTTPS et vérifier Digital Asset Links.
- [ ] Générer et conserver une clé de signature de publication dans un processus sécurisé, hors du dépôt.
- [ ] Tester sur un appareil Android physique : connexion, expiration de session, déconnexion, liens externes et pièces jointes.
- [ ] Vérifier la configuration de sécurité et les secrets de l'environnement cible.
- [ ] Produire une version release signée et contrôler son empreinte avant toute distribution.

Tant que ces points ne sont pas validés, Dikévia Android reste une préversion de démonstration non distribuable.
