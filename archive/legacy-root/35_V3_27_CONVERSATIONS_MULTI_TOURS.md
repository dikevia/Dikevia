# V3.27 — Conversations juridiques multi-tours

## Fonctionnement
Les conversations sont persistées dans PostgreSQL. Elles sont rattachées à une organisation et à l'utilisateur OIDC qui les a créées. L'interface peut lister, reprendre et supprimer les conversations de l'utilisateur connecté. La suppression d'une conversation entraîne celle de ses messages.

## Isolation et sécurité
- Les tables `chat_conversations` et `chat_messages` activent et forcent RLS.
- Chaque politique impose simultanément `app.current_org_id` et `app.current_user_id`.
- Le middleware tenant renseigne ces paramètres uniquement après validation de l'identité OIDC et de l'appartenance active à l'organisation.
- Le jeton OIDC reste géré par le module navigateur existant ; aucun jeton ni historique juridique n'est stocké dans `localStorage`.
- Les messages ne sont jamais partagés avec les autres membres de la même organisation par défaut.

## Contexte IA
À chaque question, le backend récupère au plus les 12 derniers messages de cette conversation. Les derniers messages de l'utilisateur aident à reformuler une recherche documentaire lorsque la question courante contient une référence implicite. L'historique récent est aussi transmis au fournisseur IA comme contexte de dialogue. Le prompt précise que les réponses précédentes ne sont pas des sources juridiques et ne peuvent pas établir une règle. Les références juridiques doivent toujours provenir des sources récupérées et contrôlées par le moteur.

Le contexte est limité en taille et en nombre de messages. Il peut être incomplet pour les conversations longues ; l'utilisateur doit rappeler les faits déterminants si nécessaire. Changer d'organisation change immédiatement la liste et la conversation affichée.

## API
- `GET /api/v1/chat/conversations` : liste les conversations de l'utilisateur courant dans l'organisation sélectionnée.
- `POST /api/v1/chat/conversations` : crée une conversation.
- `GET /api/v1/chat/conversations/{id}/messages` : récupère les messages d'une conversation appartenant à l'utilisateur courant.
- `DELETE /api/v1/chat/conversations/{id}` : supprime la conversation et ses messages.
- `POST /api/v1/chat/ask` : accepte `conversation_id` facultatif et le retourne dans la réponse.

## Migration et recette
La migration `012_persistent_chat_conversations.sql` crée les tables, index, politiques RLS et privilèges. Son rollback est dans `database/migrations/rollback/`. La CI PostgreSQL applique les migrations 012 et 013 et vérifie l'isolation entre organisations et entre deux utilisateurs d'une même organisation. Exécuter `scripts/upgrade_with_backup.sh` sur la recette après sauvegarde, puis vérifier création, reprise, suppression, changement d'organisation et questions de suivi.

La persistance des échanges implique une politique de conservation à définir par l'exploitant (durée, information des utilisateurs, sauvegardes et purge). Aucun mécanisme automatique de rétention n'est activé dans cette version.
