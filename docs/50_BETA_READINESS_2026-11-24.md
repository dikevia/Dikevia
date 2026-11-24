# Dikévia — état de préparation de la bêta

**Contrôle actualisé : 24 novembre 2026, 23:30 UTC**  
**Branche commerciale :** `feature/dikevia-v3.38.5-cgfp-chat`  
**Dernier commit commercial observé en production :** `f9aadba451e67157ae41ade32190d5eaa0e5bed5`

Ce document distingue les contrôles effectués, les limites connues et les validations encore nécessaires. Il ne constitue ni une certification juridique ni une garantie de capacité.

## 1. Production et sécurité opérationnelle

- API commerciale Render : dernier déploiement terminé avec succès ; les contrôles live API/OIDC/site ont réussi sur le code correspondant.
- Identité runtime : `OIDC_PROVIDER=keycloak`, explicitement fixé dans le Blueprint commercial. Auth0 n'est pas activé.
- Smoke tests Keycloak : découverte OIDC, issuer, JWKS, PKCE, configuration navigateur et rejet des appels protégés anonymes ou munis d'un bearer invalide réussis.
- Une connexion avec un véritable compte utilisateur et une session complète dans l'application restent à effectuer.
- Provisionnement automatique : non opérationnel. Le diagnostic du 24/11 a établi `smtp_configured=False` et `keycloak_admin_configured=False`. Les invitations restent manuelles : un administrateur Keycloak doit créer et vérifier le compte avant acceptation du jeton Dikévia.
- Plafond bêta : 100 comptes au total, invitations en attente comprises. Ce plafond ne garantit pas 100 connexions simultanées et ne permet pas de promettre une capacité de 250 clients actifs.
- Les sondes externes PISTE et catalogue IA au démarrage sont désactivées explicitement. Cela évite de consommer des appels externes à chaque redémarrage ; les appels réglementaires nécessaires aux requêtes utilisateurs restent disponibles.
- Mesures Render sur les dernières 24 h : API commerciale, pic CPU observé 0,0071/0,15 vCPU et pic mémoire 86,5 Mo/512 Mo ; service identité Keycloak, pic CPU 0,0826/0,15 vCPU et pic mémoire 473,5 Mo/512 Mo (88,2 %). Le dernier échantillon Keycloak reste autour de 470,8 Mo. Aucun log correspondant à `OutOfMemory`, `OOMKilled` ou `heap space` n'a été trouvé dans la recherche effectuée, mais la marge mémoire Keycloak est faible.
- Render n'a fourni aucun échantillon exploitable de requêtes HTTP ou de latence p95 sur cette période. Il n'existe donc pas de mesure de débit ni de test de charge permettant de garantir 100 ou 250 connexions simultanées. Les deux services sont sur le plan gratuit, une seule instance chacun, avec démarrage à froid possible.
- Les flags de production sont épinglés : recherche vectorielle désactivée, revue IA de documents désactivée, paiement Stripe désactivé, import de documents désactivé tant que le scanner antivirus n'est pas disponible.

## 2. Fournisseur IA et fiabilité conversationnelle

- Fournisseur configuré : API Google Gemini compatible OpenAI, modèle principal `gemini-2.5-flash`, modèle de secours `gemini-2.5-flash-lite`.
- Le catalogue fournisseur a répondu `AVAILABLE` lors du diagnostic du 24/11. Un catalogue accessible ne prouve pas qu'une génération réelle fonctionne.
- La matrice de résilience HTTP a des tests simulés : 401/403/429 sans retry ni bascule, 500 avec retry borné, 503 avec bascule contrôlée vers le modèle de secours. Aucun appel externe ni quota n'est consommé par ces tests.
- Les événements de production du 20 au 22/11 contiennent 16 erreurs fournisseur historiques, antérieures à la configuration directe Google. Les derniers échanges assistant enregistrés avant le changement de fournisseur étaient marqués `NON_VERIFIE`. Aucune génération utilisateur réelle postérieure au changement de fournisseur n'a encore été validée.
- Audit des 196 références conservées dans les 22 derniers messages assistant historiques : 56 réponses PISTE avec texte intégral et version récupérée à la date demandée, 5 explicitement en vigueur à cette date, 38 avec portée temporelle incomplète ; 13 références LODA récupérées à la date demandée, 1 en vigueur et 9 à portée temporelle incomplète ; 60 résultats CETAT de recherche ne contenant que des métadonnées sont explicitement marqués `citation_integrity.valid=false` ; 4 textes CETAT intégraux ont un identifiant apparié mais une portée temporelle incomplète ; 10 extraits du snapshot CGFP sont marqués non vérifiés en direct. Ces résultats de recherche et snapshots ne doivent pas être assimilés à des preuves actuelles.
- 186 références sur 196 ont une URL de source ; 126 ont un statut temporel explicite. Les statuts incomplets sont conservés et doivent conduire à une réponse prudente, pas à une date d'effet supposée.
- Les tests automatisés couvrent le contexte multi-tour, les demandes de clarification, la séparation FPT/FPE/FPH, les citations, l'applicabilité temporelle, le lien affirmations-preuves et l'abstention lorsque les preuves sont insuffisantes.
- Le validateur d'affirmations applique un contrôle fail-closed : identifiant de source exact, citation valide, extrait présent dans le texte intégral, SHA-256 du texte versionné, périmètre FPT/FPE/FPH explicite et statut temporel admissible. Les résultats CETAT limités aux métadonnées et les guidances non normatives sont exclus comme preuves ; le snapshot CGFP n'est admis que dans le chemin de repli explicitement qualifié pour l'information générale. Ce contrôle établit la provenance et la cohérence des citations, pas l'entailment sémantique ni la justesse de l'interprétation juridique : une revue humaine reste nécessaire.
- Dernière CI complète observée : **1 181 tests réussis, 1 avertissement, aucun échec** après ajout de la matrice HTTP fournisseur (401/403/429/500/503). Les contrôles live OIDC/API/site ont également réussi.
- Les recherches ciblées CITIS et temps partiel thérapeutique sont séparées par versant : FPT, FPE et FPH. L'interface permet de préciser le ministère, le rectorat ou l'établissement hospitalier pour les questions FPE/FPH ; la validation serveur interdit les employeurs territoriaux dans ces deux versants.

## 3. Corpus, sources et recherche

### Production

- Légifrance/PISTE est configuré en environnement Production. Les contrôles effectués avant désactivation des sondes de démarrage ont retrouvé des références exactes et des textes intégraux pour plusieurs axes CGFP/IHTS.
- L'image commerciale embarque un snapshot CGFP daté du 31 octobre 2026, 1 024 pages, avec empreinte SHA-256 documentée.
- La base PostgreSQL commerciale ne contient actuellement aucun enregistrement dans `legal_documents` ou `legal_chunks`. Le chatbot s'appuie donc sur les sources officielles interrogées en direct et le snapshot embarqué, pas sur le corpus vectoriel de staging.
- La recherche plein texte CETAT reste désactivée en production en attente de validation métier et de son cadre de consultation.

### Staging

- 4 459 documents, 4 459 versions et 5 640 segments.
- 5 640 embeddings présents, modèle `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, dimension 384.
- Les 4 459 versions ont un texte intégral, un `version_key`, une date de récupération et une empreinte SHA-256. Les champs `valid_from`/`valid_to` et `source_version_id` restent absents ; le statut temporel demeure `UNKNOWN`, sans date d'effet inventée. Pour le CGFP, le `version_key` porte le hash du snapshot et la référence de l'article.
- L'audit a identifié 15 groupes de textes strictement identiques, représentant 20 copies supplémentaires, tous dans le snapshot CGFP mais sous des références d'articles distinctes. Il s'agit d'ancres juridiques distinctes, pas de doublons d'identifiants ; elles sont volontairement conservées pour préserver les citations.
- Index vectoriel HNSW présent et utilisé par le planificateur SQL.
- Métadonnées CGFP staging : les 4 242 articles ont reçu `publisher=Légifrance` et leur référence exacte dans `official_number`, dérivées du champ article déjà présent. Le statut reste `UNKNOWN/IMPORTED_UNVERIFIED` et aucune date d'effet n'a été ajoutée.
- 217 documents de guidance audités : 199 Service Public et 18 ressources institutionnelles. Service Public porte la licence `fr-lo`, l'attribution DILA et une dernière mise à jour de dataset au 21/11/2026 ; son statut de validation juridique reste `NON_VERIFIE`. Les 18 ressources institutionnelles sont autorisées à la réutilisation, mais restent non vérifiées et classées comme guidance non primaire (9 positions syndicales, 8 guides professionnels, 1 guidance administrative officielle).
- Aucune guidance non normative n'est autorisée à soutenir seule une conclusion juridique.
- Les sources importées restent `IMPORTED_UNVERIFIED` : leur présence, leur extraction et leur indexation ne les transforment pas en preuves juridiques certifiées.
- Audit de recherche vectorielle en lecture seule : six questions de contrôle, cinq résultats retournés par question. Ce smoke test vérifie l'exécution et la couverture, pas la pertinence juridique.
- Parité FastEmbed/Transformers.js : 12 vecteurs comparés, similarité cosinus moyenne 0,9999991. La compatibilité numérique est vérifiée ; la pertinence sémantique métier ne l'est pas.
- Le flag vectoriel est activé uniquement sur le service de staging. Il reste désactivé en production tant que le corpus n'est pas validé et importé.

## 4. Documents privés et confidentialité

- L'archive privée Saint-Étienne contient 49 PDF, 382 pages : 44 ont une couche texte exploitable et 5 ont été traités par OCR français/anglais.
- Les OCR des tableaux indiciaires restent non vérifiés : leur confiance moyenne de reconnaissance est un indicateur technique, pas un taux d'exactitude. Les nombres, indices, dates et montants doivent être relus sur les PDF originaux.
- Une archive textuelle privée avec manifeste et empreintes SHA-256 a été produite. Aucun document ni texte de cette archive n'a été importé dans le corpus juridique partagé, la base de staging ou la base de production.
- Les imports de documents personnels et d'organisation restent désactivés. Aucun scanner antivirus dédié n'est déployé sur l'hébergement actuel ; le backend doit rester fail-closed.
- Les documents personnels doivent rester cloisonnés par utilisateur/organisation avec RLS ; aucune pièce locale ne doit devenir une source commune.

## 5. Applications Android

- APK Dikévia Standard et Dikévia Administration reconstruits et vérifiés par GitHub Actions.
- Build Gradle des deux variantes réussi ; artefacts publiés le 24/11.
- APK signés en mode debug, destinés au sideload bêta, pas au Play Store.
- L'application Administration est distincte et réservée au rôle administrateur plateforme ; elle ne contient pas le chatbot agents.
- Le test d'installation et de parcours sur appareil Android physique reste à effectuer.
- Les APK sont des conteneurs WebView : les évolutions de l'interface web apparaissent après déploiement du serveur, sans reconstruire l'APK.

## 6. Auth0, facturation et accès commerciaux

- Le tenant de développement Auth0, l'application SPA et l'API existent ; le code backend prend en charge issuer/audience/JWKS et PKCE.
- Le tenant Auth0 de développement est hébergé en région US-5. Pour un SaaS destiné aux collectivités françaises, ne pas réutiliser ce tenant en production sans analyse préalable de résidence des données, DPA, transferts internationaux, sous-traitants et exigences contractuelles des clients publics. Prévoir un tenant de production distinct dans une région adaptée si l'analyse le requiert.
- Les listes d'URL autorisées Auth0 doivent encore être resserrées. Aucun parcours de connexion Auth0 réel, aucune migration de comptes Keycloak et aucun basculement production ne sont validés.
- Keycloak reste explicitement le fournisseur runtime de la bêta.
- Les quatre offres commerciales sont présentes dans le catalogue de code, mais Stripe et le checkout restent désactivés.
- La fondation SQL du portefeuille de crédits existe ; les débits IA et allocations mensuelles ne sont pas activés, en attente de calibration des coûts et de validation du benchmark.
- Le droit fondateur premium n'est pas attribué dans la table dédiée. Il ne doit être accordé qu'après vérification de l'identité OIDC correspondante.
- L'onboarding de prospects doit donc rester manuel. La bêta actuelle n'est pas un tunnel de souscription autonome.

## 7. Benchmark — volontairement dernier

- Le dataset métier comporte 100 cas FPT ; aucun corrigé de référence n'est actuellement validé.
- Le pilote de 15 cas reste `NOT_EVALUATED`.
- Le benchmark doit être lancé seulement après finalisation des contrôles techniques, corpus, sources, identité et fournisseur IA.
- Gate proposé : 100 cas revus humainement, aucun échec critique, moyenne au moins 8,5/10, pertinence des questions au moins 95 %, support des sources au moins 98 %.
- Aucun score de fiabilité juridique ne doit être annoncé avant cette revue.

## Décision opérationnelle

Dikévia est une **bêta techniquement démontrable** : service commercial déployé, Keycloak/OIDC contrôlé, PISTE Production configuré, protections de données testées, recherche vectorielle évaluée en staging et APK Android disponibles.

Ce n'est pas encore un SaaS commercial entièrement autonome ni un assistant dont l'exactitude juridique est certifiée. Avant de promettre un déploiement à grande échelle, restent notamment : une vraie connexion utilisateur, une génération Gemini réelle post-configuration, la correction des paramètres Auth0, le provisionnement automatisé, le scanner antivirus, le portefeuille de crédits/paiement et, en dernier, le benchmark juridique humain.

Les services Render gratuits peuvent subir un démarrage à froid ; ouvrir les deux applications quelques minutes avant toute démonstration.
