# 06 — Contrat API V3

Base path : `/api/v1`. Les endpoints privés exigent un JWT OIDC Bearer valide. Le fournisseur OIDC héberge le parcours de connexion ; aucune gestion locale de mot de passe n'est ajoutée.

| Méthode | Route | État V3 |
|---|---|---|
| GET | `/health` | Implémenté, public |
| GET | `/api/v1/auth/me` | Implémenté |
| GET | `/api/v1/organizations` | Implémenté, adhésions propres à l'utilisateur |
| POST | `/api/v1/chat/ask` | Implémenté, fail-closed NON_VERIFIE |
| GET | `/api/v1/organizations/me/members` | Implémenté |
| GET | `/api/v1/documents` | Implémenté, lecture |
| GET | `/api/v1/documents/{id}` | Implémenté, lecture cloisonnée |
| POST | invitations / documents | Implémenté, selon rôles et tenant |
| POST | création organisation plateforme | À développer, avec rôle plateforme protégé |
| login / logout OIDC | Parcours IdP à intégrer | À configurer |

## Sélection d'organisation
Envoyer `X-Organization-ID` après avoir récupéré `/organizations`. Ce champ n'est pas une autorisation : le backend revérifie systématiquement l'adhésion active, le statut utilisateur et le statut organisation. Toute requête privée métier installe ensuite le contexte RLS dans une transaction.

## Codes
- 401 : jeton absent, invalide ou expiré.
- 403 : adhésion absente/révoquée, compte désactivé, organisation suspendue ou rôle insuffisant.
- 400 : organisation non sélectionnée ou identifiant mal formé.
- 503 : OIDC ou base non configurés.
- 422 : entrée invalide.

Depuis V3.27, les conversations et leurs messages sont persistés dans PostgreSQL et cloisonnés par organisation et utilisateur OIDC via RLS FORCE. Les réponses précédentes servent de contexte conversationnel limité ; elles ne sont jamais des sources juridiques.


## Routes ajoutées en V3.1
| Méthode | Route | Autorisation | Fonction |
|---|---|---|---|
| POST | `/api/v1/platform/organizations` | Administrateur plateforme | Créer un espace et son premier administrateur local |
| POST | `/api/v1/organizations/me/invitations` | Administrateur local | Créer une invitation à jeton unique |
| DELETE | `/api/v1/organizations/me/invitations/{id}` | Administrateur local | Révoquer une invitation en attente |
| POST | `/api/v1/invitations/accept` | Utilisateur OIDC avec e-mail vérifié | Accepter une invitation |

Le jeton d'invitation n'est stocké qu'en hash et retourné une seule fois à la création. La remise par e-mail n'est pas encore intégrée.


## V3.4 — recherche, rescannage et réindexation documentaire
- `GET /api/v1/documents/search?q={texte}&collectivity_id={uuid}&limit=20` : recherche plein texte dans les documents de l'organisation sélectionnée. Les résultats exposent leur statut juridique sans l'élever automatiquement au rang de document applicable.
- `POST /api/v1/documents/{id}/rescan` : réservé à `ORG_ADMIN` et `LEGAL_EDITOR`, rescane toutes les versions avec ClamAV.
- `POST /api/v1/documents/{id}/reindex` : réservé à `ORG_ADMIN` et `LEGAL_EDITOR`, extrait et indexe les versions dont le scan est `CLEAN`.


| GET | `/api/v1/documents/search` | `ORG_ADMIN`, `LEGAL_EDITOR`, `MEMBER` via adhésion active | Recherche plein texte dans le tenant sélectionné |
| POST | `/api/v1/documents/{id}/rescan` | `ORG_ADMIN`, `LEGAL_EDITOR` | Contrôle antivirus de toutes les versions |
| POST | `/api/v1/documents/{id}/reindex` | `ORG_ADMIN`, `LEGAL_EDITOR` | Extraction et indexation des versions saines |

### Supervision du service (V3.5)

- `GET /health` : endpoint de vivacité, ne vérifie pas les dépendances.
- `GET /ready` : vérifie la connexion PostgreSQL ; renvoie `503` si la base est indisponible.
- En production, `/docs`, `/redoc` et `/openapi.json` sont désactivés.

## V3.9 — garde-fous d'invitation
- Une adresse ne peut avoir qu'une invitation `PENDING` par organisation ; une demande concurrente reçoit HTTP 409.
- L'acceptation d'une invitation ne modifie jamais le rôle d'une adhésion déjà active ; le changement de rôle doit passer par `PATCH /api/v1/organizations/me/members/{user_id}/role`.
- Les acceptations concurrentes du même utilisateur dans la même organisation sont sérialisées au niveau PostgreSQL.

### V3.11 — Recherche CGFP
`GET /api/v1/legal/cgfp/search?q=<question>&limit=8` : recherche dans l'index national du snapshot CGFP, sous authentification et contexte d'organisation. `limit` est plafonné à 20. Retourne `verification_status`, les métadonnées de snapshot, les articles/pages/extraits et un avertissement de vérification officielle.

`GET /api/v1/chat/conversations` liste les conversations privées de l’utilisateur courant ; `POST /api/v1/chat/conversations` en crée une ; `GET /api/v1/chat/conversations/{id}/messages` recharge les messages ; `DELETE /api/v1/chat/conversations/{id}` supprime la conversation et ses messages. Ces routes sont tenant-authentifiées et l’isolation RLS impose aussi l’identifiant utilisateur courant.

`POST /api/v1/chat/ask` accepte `conversation_id` (facultatif) et retourne cet identifiant. Le backend récupère au plus les 12 derniers messages de la conversation, utilise les dernières questions utilisateur pour contextualiser la recherche et transmet le dialogue récent au fournisseur IA en précisant que l’historique n’est pas une source juridique. Interroge désormais cet index national en première étape. Avec résultats, retourne `PARTIELLEMENT_VERIFIE` et les extraits dans `sources`. Sans résultat, retourne `NON_VERIFIE` et précise qu'une recherche infructueuse ne démontre pas l'absence de droit.

## Routes CGFP — V3.12
Toutes ces routes exigent une authentification et un contexte d'organisation actif (`X-Organization-ID`), vérifié côté serveur.

- `GET /api/v1/legal/cgfp/source` : retourne les métadonnées du snapshot local et son statut de vérification.
- `GET /api/v1/legal/cgfp/search?q=...&limit=8` : recherche BM25 dans les articles indexés (limite 1 à 20).
- `GET /api/v1/legal/cgfp/articles/{article_ref}` : retourne le texte intégral extrait d'un article L/R/D, ses pages et la provenance du snapshot.

Les réponses issues du snapshot ne certifient pas la rédaction officielle ni la version applicable à une date donnée. Le backend doit conserver cet avertissement jusqu'au raccordement de la vérification historique Légifrance/PISTE.


## Contrôles CGFP — V3.13
Les routes de recherche et de consultation continuent de fournir des résultats du snapshot. Le endpoint de dialogue applique désormais un contrôle serveur sur chaque citation : article, source, pages et extrait exact (après normalisation des espaces et des ellipses de coupe). Une citation rejetée n'est pas transmise dans la réponse. Ce contrôle ne remplace pas la vérification officielle Légifrance ni l'historique temporel. La date `facts_date` attend `AAAA-MM-JJ`.


## V3.21 — Référentiel juridique national
- `GET /api/v1/legal/knowledge/search?q=...&effective_date=...&limit=12` : recherche dans le corpus public commun ; les résultats signalent l'état du texte, le type de contenu et la complétude temporelle.
- `POST /api/v1/platform/legal-corpus/ingest/regulatory` : import ciblé LEGI/LODA via PISTE, réservé à l'administrateur plateforme.
- `POST /api/v1/platform/legal-corpus/ingest/administrative-case-law` : recherche CETAT et consultation du texte intégral, réservé à l'administrateur plateforme.
- `POST /api/v1/platform/legal-corpus/ingest/circulaires-xml` : import du XML CIRCULAIRES DILA ; statut `IMPORTED_UNVERIFIED` jusqu'à vérification de provenance.
- `GET /api/v1/platform/legal-corpus/ingestion-runs` : journal des opérations d'import.

Les imports utilisent une connexion PostgreSQL dédiée `LEGAL_CORPUS_INGEST_DATABASE_URL`; le compte `cfdt_juris_app` est en lecture seule sur le corpus. Voir `docs/31_V3_21_PERMANENT_LEGAL_KNOWLEDGE.md`.


Depuis V3.28, un utilisateur peut constituer un dossier de travail privé à partir d'une conversation : `POST /api/v1/chat/conversations/{id}/dossier`, le consulter avec `GET` et enregistrer ses modifications avec `PUT`. Le contenu est cloisonné par RLS FORCE selon l'organisation et l'utilisateur. La compilation est fidèle aux messages et métadonnées enregistrés ; elle ne valide pas les faits, ne transforme pas les échanges en sources juridiques et ne récupère pas automatiquement les pièces jointes.
