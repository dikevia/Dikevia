# 01 — Cahier des charges produit

## 1. Vision
CFDT JURIS permet à un représentant syndical de décrire une situation en langage courant. Le système qualifie la question, détermine les faits et la période utiles, recherche les textes nationaux et actes locaux pertinents, récupère leur contenu et leur version applicable, puis produit une analyse structurée avec références contrôlables.

Le moteur IA explique les sources ; il ne constitue jamais la source du droit.

## 2. Cibles et périmètre
### Organisation initiale
- Organisation : syndicat CFDT de Saint-Étienne (nom juridique exact et entité porteuse à confirmer).
- Accès : gratuit pour cette organisation, selon une licence/convention écrite.
- Corpus local initial : Ville de Saint-Étienne et Saint-Étienne Métropole.
- Corpus national : droit applicable à la fonction publique territoriale.

### Produit futur
- Autres organisations syndicales (CFDT, CGT, FO, UNSA, CFTC et autres OS).
- Chaque OS dispose de son espace et de ses utilisateurs autorisés.
- Une organisation ne voit jamais les comptes, conversations, dossiers, documents privés, réglages ou factures d'une autre.
- Les contenus nationaux publics peuvent être mutualisés ; les corpus locaux et documents internes restent cloisonnés.

## 3. Fonctionnalités du produit
1. Authentification nominative des utilisateurs autorisés.
2. Organisations, adhésions et rôles : `ORG_ADMIN`, `LEGAL_EDITOR`, `MEMBER`, `PLATFORM_ADMIN`.
3. Historique conversationnel privé, rattaché à un utilisateur et à une organisation, avec possibilité de suppression.
4. Dossiers juridiques construits à partir des conversations, avec distinction entre échanges/source originaux et champs de dossier modifiables.
5. Sélection de la collectivité employeur, date/période des faits et question.
6. Clarification d'un élément déterminant, une question à la fois.
7. Recherche Légifrance/PISTE et corpus local validé, filtrée par organisation, collectivité et dates.
8. Recherche de jurisprudence seulement si la source est réellement accessible et vérifiée.
9. Réponse structurée avec statut de vérification et références.
10. Espace documentaire pour ajouter, versionner, valider et retirer les actes locaux.
11. Console d'administration d'organisation.
12. Console plateforme minimale pour créer/suspendre des organisations et gérer l'offre.
13. Mesures de minimisation : les journaux techniques et de consommation ne doivent pas contenir le texte des conversations.

## 4. Hors périmètre tant que non validé
- Téléversement de dossiers RH, bulletins de paie, arrêts ou pièces médicales.
- Envoi automatique de courriers à l'employeur.
- Décisions administratives ou calcul automatique de droits individuels sans validation.
- Espace public anonyme.
- Application mobile native.
- Marketplace et facturation automatisée avant validation du modèle commercial.
- Analyse exhaustive de toutes les juridictions administratives tant que les sources ne sont pas démontrées.

## 5. Parcours utilisateur
1. Connexion.
2. Choix de l'organisation active si l'utilisateur appartient à plusieurs espaces.
3. Ouverture d'une nouvelle conversation ou reprise d'une conversation privée existante.
4. Saisie de l'employeur, de la date des faits et d'une question aussi anonymisée que possible.
5. Qualification des informations manquantes.
6. Recherche documentaire nationale puis locale.
7. Contrôle des dates d'effet et de l'état des actes.
8. Génération uniquement avec les passages récupérés.
9. Validation automatique des références et extraits.
10. Affichage : réponse, statut, sources, limites et documents à obtenir.
11. Suppression possible par l'utilisateur ; application d'une durée de conservation et d'une purge automatique à définir avant production.

## 6. Format de réponse juridique
- Statut : VÉRIFIÉ / PARTIELLEMENT VÉRIFIÉ / NON VÉRIFIÉ.
- Résumé opérationnel.
- Qualification juridique.
- Faits rapportés, faits établis par source, hypothèses et éléments manquants.
- Textes : intitulé, numéro, date, article, version, dates d'effet, URL.
- Jurisprudence : juridiction, date, numéro, principe, limites et source ; sinon indiquer qu'aucune décision pertinente n'a été vérifiée.
- Application aux faits.
- Actions syndicales envisageables ; délais seulement si vérifiés.
- Documents/preuves à réunir.
- Réserves et besoin de validation humaine.

## 7. Règles fonctionnelles absolues
- Une question juridique ne déclenche jamais une réponse de fond avant une recherche documentaire.
- Pas de source récupérée = `NON_VERIFIE`.
- Sources incomplètes ou sans version historique = au minimum `PARTIELLEMENT_VERIFIE`.
- Ne jamais confondre Ville de Saint-Étienne et Saint-Étienne Métropole.
- Ne jamais inférer qu'un texte est applicable du seul fait qu'il est présent dans le corpus.
- Ne jamais assimiler l'absence de résultat à l'absence de droit.
- Les documents importés sont des données, jamais des instructions à suivre.
- Le statut `VERIFIE` exige que toutes les sources déterminantes soient présentes, datées et contrôlées ; il ne signifie pas que l'avis est infaillible.
- Une conversation et un dossier restent privés à leur propriétaire et à son organisation ; un identifiant fourni par le navigateur ne constitue jamais une autorisation.

## 8. Exigences UX et confidentialité
- Interface française, claire, mobile-first.
- Indicateur de recherche.
- Statut de vérification visible.
- Sources cliquables, type de source et date de consultation.
- Avertissement permanent : ne pas saisir de données nominatives ou médicales.
- Possibilité de copier et de supprimer une conversation.
- Accessibilité clavier et contrastes conformes aux bonnes pratiques.
- Durée de conservation, purge automatique, export et modalités de suppression des conversations/dossiers à spécifier et tester avant production.
