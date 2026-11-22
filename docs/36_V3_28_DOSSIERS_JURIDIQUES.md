# V3.28 — Constitution de dossiers juridiques à partir des échanges

## Objectif
Permettre à l'utilisateur de transformer une conversation juridique multi-tours en dossier de travail structuré, modifiable et imprimable.

## Contenu assemblé
- Intitulé de la conversation et employeur le plus récemment indiqué.
- Dates des faits communiquées dans les échanges.
- Questions et éléments rapportés par l'utilisateur, repris sans les présenter comme des faits vérifiés.
- Réponses précédentes, avec leur statut de vérification.
- Sources et points restant à vérifier enregistrés dans les métadonnées des réponses.
- Zones éditables pour l'objet, la chronologie, les pièces, la conclusion provisoire et le plan d'action.

## API
- `POST /api/v1/chat/conversations/{id}/dossier` : crée le dossier s'il n'existe pas ; retourne le dossier existant sans écraser les modifications.
- `GET /api/v1/chat/conversations/{id}/dossier` : récupère le dossier.
- `PUT /api/v1/chat/conversations/{id}/dossier` : enregistre les champs édités après validation de structure et de taille.

## Sécurité
La table `legal_dossiers` possède RLS et FORCE RLS. Les politiques imposent l'organisation et l'utilisateur OIDC courant et vérifient l'appartenance de la conversation. Les droits SQL sont limités au rôle applicatif. La suppression de la conversation supprime le dossier par cascade.

## Limites et prudence
Le dossier est initialement `BROUILLON_A_VALIDER`. Il ne constitue pas une expertise juridique, ne certifie pas les déclarations de l'utilisateur et ne valide pas les analyses. Les sources restent celles enregistrées par le moteur au moment des réponses. Les fichiers/pièces joints au corpus de l'organisation ne sont pas automatiquement sélectionnés comme pièces du dossier ; l'utilisateur doit les référencer et les vérifier. La fonction d'impression du navigateur permet un enregistrement PDF.

## Déploiement
Après sauvegarde, exécuter `scripts/upgrade_with_backup.sh`. Le migrateur checksum-tracked applique `013_legal_dossiers.sql`. Vérifier sur recette la création, la reprise, l'édition, l'impression, le refus d'accès croisé entre utilisateurs/organisations et la suppression en cascade.
