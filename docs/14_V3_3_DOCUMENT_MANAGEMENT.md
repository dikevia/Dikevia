# V3.3 — Gestion documentaire

## Fonctions livrées dans le code
- Gestion des collectivités par organisation : liste et création réservée à l'administrateur local.
- Import PDF et DOCX, contrôles de taille, extension, type MIME et structure/signature.
- Stockage privé sur volume dédié, clé générée côté serveur, sans chemin fourni par le navigateur.
- Calcul SHA-256, métadonnées et version initiale.
- Dépôt de nouvelles versions, historique et téléchargement de chaque version.
- Validation métier réservée au rôle `LEGAL_EDITOR` ou `ORG_ADMIN`, avec auteur, date et journal d'audit.
- Contrôle du tenant sur les requêtes SQL et accès aux fichiers uniquement après autorisation.

## Routes
- `GET/POST /api/v1/collectivities`
- `GET /api/v1/documents` et `GET /api/v1/documents/{id}`
- `POST /api/v1/documents` (multipart : champs descriptifs + `file`)
- `POST /api/v1/documents/{id}/versions`
- `GET /api/v1/documents/{id}/versions`
- `GET /api/v1/documents/{id}/download`
- `GET /api/v1/documents/{id}/versions/{version}/download`
- `PUT /api/v1/documents/{id}` (mise à jour des métadonnées)
- `PATCH /api/v1/documents/{id}/validation`

## Limites et sécurité opérationnelle
- Formats admis : PDF et DOCX uniquement ; limite par défaut : 20 Mo.
- Le stockage local Docker est persistant mais doit être remplacé ou monté sur un stockage privé sauvegardé en production.
- Aucun antivirus, OCR, extraction de texte, indexation plein texte ni analyse de macros n'est intégré à cette livraison. Les contrôles de structure ne constituent pas une analyse antivirus.
- Les documents déposés sont initialement `COLLECTED_UNVERIFIED`. Le dépôt ne signifie jamais que le document est juridiquement applicable.
- Les fichiers déjà stockés avant V3.3 ne sont pas rétroactivement déplacés : prévoir une migration contrôlée si une ancienne clé de stockage existe.

## Migration
Sur une base existante V3.2, appliquer `004_document_management.sql` avec le rôle de migration, puis réexécuter les grants complémentaires (ou l'intégralité de `grant_runtime_permissions.sql`) en DBA.

## Exemple d'utilisation HTTP

Après obtention d'un jeton OIDC et sélection d'une organisation, les appels nécessitent `Authorization: Bearer <token>` et `X-Organization-ID: <uuid>`.

```bash
curl -X POST "$API/api/v1/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -F "title=Règlement intérieur" \
  -F "document_type=REGLEMENT" \
  -F "collectivity_id=$COLLECTIVITY_ID" \
  -F "file=@reglement-interieur.pdf;type=application/pdf"
```

La réponse fournit l'identifiant du document, le numéro de version initial, l'empreinte SHA-256 et le statut `COLLECTED_UNVERIFIED`. Les téléchargements repassent par l'API authentifiée ; ne jamais exposer le volume de stockage via un serveur web statique.


## V3.4 — Antivirus et recherche plein texte

- Chaque nouveau PDF/DOCX est envoyé à ClamAV via le protocole INSTREAM avant tout enregistrement. Si ClamAV est indisponible, l'import est refusé (fail closed). Un fichier détecté comme malveillant est rejeté.
- Les téléchargements sont bloqués tant que le statut antivirus n'est pas `CLEAN`. La route `POST /api/v1/documents/{id}/rescan` permet à un responsable juridique de recontrôler toutes les versions d'un document, notamment les fichiers historiques qui ont le statut `NOT_SCANNED`.
- Extraction de texte PDF via pypdf et DOCX via XML interne, sans exécution de macros ni de contenu embarqué. Taille de texte plafonnée à 2 millions de caractères. Les PDF image-only ne produisent pas de texte : ils restent disponibles après scan mais sont marqués `NO_TEXT`. OCR non inclus.
- Texte extrait indexé dans `document_text`, protégé par RLS/FORCE RLS, avec index PostgreSQL GIN et dictionnaire français. Recherche par organisation et, facultativement, par collectivité via `GET /api/v1/documents/search?q=...`. La route `POST /api/v1/documents/{id}/reindex` permet de reconstruire l’index des versions historiques après scan antivirus.
- Les résultats affichent toujours le statut juridique (`COLLECTED_UNVERIFIED`, `VERIFIED_APPLICABLE`, etc.). La recherche plein texte ne valide jamais automatiquement un document et n'est pas encore branchée au moteur de réponse juridique.

### Migration V3.4
Après les migrations 001 à 004, appliquer `database/migrations/005_document_scanning_and_search.sql`, puis réexécuter `database/grant_runtime_permissions.sql` avec le rôle DBA. Mettre à jour `.env` avec `CLAMAV_HOST=clamav`, `CLAMAV_PORT=3310` et `CLAMAV_TIMEOUT_SECONDS=8`. Docker Compose démarre ClamAV et attend son healthcheck avant de lancer l'API.

Les documents déjà présents sont marqués `NOT_SCANNED` par défaut et ne peuvent pas être téléchargés tant qu'ils n'ont pas été rescannés. L'extraction et l'indexation des anciens documents nécessitent une opération de réindexation distincte ; aucune extraction historique automatique n'est prétendue dans cette version.
