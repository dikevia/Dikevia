# Dikévia — Plan de mise en route, conformité et modèle de rémunération

**Statut : référence produit et commerciale validée par le porteur du projet le 19 novembre 2026.**  
Les durées sont indicatives. Les prix sont exprimés hors taxes (HT). Les coûts d'IA sont des estimations à confirmer en bêta. Ce document ne constitue pas un avis juridique : CGU, CGV, AIPD, statut de l'activité et obligations fiscales doivent être validés par un juriste, un avocat ou un DPO selon le sujet.

## 1. Plan de mise en route en six phases

Chaque phase possède un critère de sortie. Le passage à la phase suivante suppose que ce critère soit atteint. La sécurité peut avancer en parallèle de la phase 1.

### Phase 1 — Fiabiliser le moteur (2 à 4 semaines)
- Corriger la sélection sur référence précise : référence détectée sans correspondance exacte = abstention, sans repli sur la recherche sémantique.
- Normaliser les formats de référence (L111-1, L. 111-1, tirets spéciaux).
- Constituer un jeu de test d'environ 30 références, dont 10 inexistantes, et un cas « date des faits absente ».
- N'appeler l'IA que lorsqu'une source exacte existe.

**Critère de sortie :** zéro source parasite sur les références inexistantes ; L111-1 renvoie le texte officiel avec identifiant, source et date.

### Phase 2 — Sécurité (en parallèle de la phase 1)
- Rotation de tous les secrets exposés (Neon, Keycloak, PISTE, Gemini, GitHub) et nettoyage de l'historique Git.
- Passer le dépôt GitHub en privé au moment prévu par le porteur du projet, après la fin du développement.
- Tests d'isolation entre sections et utilisateurs (conversations, documents, dossiers).
- Limites de débit : 20 questions par accès et par jour, 100 par section, plus un plafond par minute.
- Audit des dépendances, CORS, durée de vie des tokens et journaux sans contenu des questions.

**Critère de sortie :** rapport d'isolation sans faille ouverte ; secrets renouvelés.

### Phase 3 — RGPD et suppression à 24 h (2 à 3 semaines)
- Suppression réelle de la question et de la réponse : base, logs, cache, files d'attente et sauvegardes.
- Surveillance : alerte si un élément dépasse 24 h, et test automatisé de la purge.
- Utiliser l'offre payante de Gemini (jamais le palier gratuit), choisir une région UE si possible et signer l'accord de traitement.
- Rédiger l'AIPD, le registre des traitements et la politique de confidentialité.
- Message dans l'interface invitant à ne saisir ni noms ni situations identifiables.
- Séparer les données de facturation de celles des conversations.
- Export gratuit des données personnelles sur demande (le PDF payant reste une option de confort).

**Critère de sortie :** preuve qu'une conversation disparaît entièrement en 24 h ; documents RGPD relus par un DPO ou un juriste.

### Phase 4 — Fonctions et offre commerciale (3 à 4 semaines)
- Blocage des captures d'écran : Android avec FLAG_SECURE ; limites documentées pour iOS (détection seulement) et web (impossible).
- Génération de PDF à la volée, sans stockage serveur et sans envoi par e-mail.
- Quotas visibles dans l'interface, avec packs de questions supplémentaires.
- Paiement et abonnements selon la grille ci-dessous ; résiliation aussi simple que la souscription.
- CGU, CGV et mentions légales relues par un juriste, avec l'avertissement « ne remplace pas un conseil juridique ».
- Choisir le statut juridique de l'activité et souscrire une assurance responsabilité civile professionnelle.

**Critère de sortie :** un client peut s'abonner, payer, utiliser et résilier sans aide.

### Phase 5 — Bêta fermée (4 à 8 semaines)
- Ouvrir à la section (5 accès) et à quelques sections amies.
- Mesurer : coût réel par question, nombre de questions par accès, erreurs et temps de réponse.
- Ajuster le modèle Gemini, les quotas et les prix selon les mesures.
- Préparer le support : FAQ, guide de démarrage et canal unique de contact.
- Tester la montée en charge (hébergement, quotas Gemini) bien au-delà de l'usage prévu.

**Critère de sortie :** plusieurs semaines sans erreur grave ; coût IA sous 20 à 25 % du revenu par section.

### Phase 6 — Présentation à Interco et au national (après la phase 5)
- Informer officiellement les instances de l'intérêt financier du porteur du projet ; ne participer à aucune décision qui le concerne.
- Démonstration au secrétaire général : L111-1 (réponse sourcée), puis L999-999 (abstention).
- Dossier court : fonctionnement, protection des données, tarifs et limites.
- Formaliser l'accès gratuit d'un an du conseil interco : périmètre (5 accès), dates précises, tarif de l'année 2 et contrepartie attendue (retours d'usage).
- Prévoir un tarif pour les grandes structures, dégressif, sans exclusivité.
- Déploiement par étapes : départements ou fédérations pilotes, puis élargissement.

**Critère de sortie :** accord écrit, pilote lancé et support dimensionné.

## 2. Modèle de rémunération

Principe : une rentrée importante à l'adhésion (paiement annuel d'avance), complétée par de petits revenus mensuels récurrents grâce aux options.

### Grille d'abonnement validée

| Offre | Prix HT | Équivalent par accès et par mois | Remarque |
|---|---:|---:|---|
| 1 accès, mensuel | 15 € / mois | 15 € | Sans engagement |
| 1 accès, annuel | 170 € / an | Environ 14,20 € | Paiement d'avance |
| 5 accès, annuel | 790 € / an | Environ 13,20 € | Offre principale pour les sections |

Cinq abonnements individuels annuels représentent 850 € : le forfait cinq accès à 790 € reste donc plus avantageux dès que la section compte plusieurs utilisateurs.

### Quotas et packs de questions
- Quota inclus : 20 questions par accès et par jour ; plafond de section : 100 questions par jour pour cinq accès.
- Pack « +100 questions par jour » (+20 par accès) : 19 € HT par mois, sans engagement.
- Variantes possibles : +50 par jour pour 10 € ; +200 par jour pour 35 €.
- Le pack n'est rentable qu'avec un modèle Gemini de type Flash ; ne pas l'associer au modèle Pro par défaut.

### Options complémentaires
| Option | Prix indicatif HT | Contenu |
|---|---:|---|
| Pack Confort | 9 à 15 € / mois / section | Export PDF, veille et alertes |
| Veille juridique mensuelle FPT | Inclus dans Confort | Veille sans données personnelles |
| Alertes sur textes ou thèmes suivis | Inclus dans Confort | Notification en cas d'évolution |
| Modèles de courriers et recours | Inclus dans Confort | Contenus Dikévia mis à jour |
| Accès supplémentaires | Exemple : +5 accès à 590 € / an | Évite de reprendre un forfait complet |
| Support prioritaire | À fixer | Réponse sous 24 h |
| Formation / prise en main en visio | Forfait ou à l'acte | Accompagnement |

### Repères financiers
- 790 € payés d'avance couvrent 12 mois : environ 66 € de revenu mensuel par section. Ne pas dépenser la somme au départ.
- Objectif de maîtrise : coût IA sous 20 à 25 % du revenu par section (environ 160 à 200 € par an).
- Estimations IA à confirmer sur la tarification officielle Google : pour 6 000 jetons en entrée et 800 en sortie par question, Flash-Lite environ 0,0025 € par question ; Flash 3 environ 0,005 € ; Flash 3.6 environ 0,007 € ; Pro 3.1 environ 0,02 €. Les noms et tarifs de modèles doivent être revérifiés avant engagement.
- Pire cas annuel d'une section (100 questions par jour, 365 jours) : environ 90 € avec Flash-Lite, 180 € avec Flash 3, 275 € avec Flash 3.6, 730 € avec Pro. Le raisonnement interne (« thinking ») facturé en sortie peut augmenter ces chiffres.
- Frais de paiement : prévoir quelques pourcents par transaction ; vérifier que 15 € par mois reste rentable.

### Leviers de réduction du coût IA
- Cache des textes d'articles indexé par référence d'article (jamais par texte de question).
- Cache de contexte Gemini pour les consignes fixes (économie annoncée à vérifier selon les conditions du fournisseur).
- Modèle économique par défaut ; modèle plus puissant uniquement pour les questions d'interprétation.
- Abstention sans appel à l'IA quand aucune source exacte n'existe.

### Règles à intégrer aux CGU et CGV
- Prix HT, TVA applicable en plus ; information claire avant achat sur les inclusions et exclusions, notamment le PDF.
- Résiliation du mensuel aussi simple que la souscription ; annuel payable d'avance ; délai de garantie à définir (14 à 30 jours conseillé).
- Conversion d'un accès individuel vers le forfait cinq accès avec crédit au prorata.
- Quotas affichés dans l'offre : ne jamais annoncer un accès « illimité ».
- Droit d'accès aux données personnelles toujours gratuit, indépendamment de l'option PDF.

### Offre de lancement pour le conseil interco
- Accès gratuit pendant 12 mois à partir d'une date précise, pour cinq accès avec les mêmes quotas.
- Tarif de l'année 2 annoncé dès le départ : 790 € pour cinq accès ou tarif négocié.
- Contrepartie écrite (retours d'usage, témoignage) et accord conservé par écrit.
- Offre ouverte à d'autres organisations dans les mêmes conditions ; aucune exclusivité.

## 3. Règles permanentes et risques

### Invariants
- Aucun secret dans le dépôt ni dans les échanges.
- Aucun accès des administrateurs (porteur du projet compris) au contenu des conversations.
- Jamais de test sur la base principale.
- Les logs ne contiennent ni questions ni réponses.
- Statut du produit : aide à la recherche documentaire, jamais « validation juridique définitive ».

### Risques et parades

| Risque | Parade |
|---|---|
| Article inventé ou source parasite | Abstention stricte ; jeu de test avant chaque mise en production |
| Copie de données survivant à 24 h (sauvegardes, logs, cache, fournisseur IA) | Audit de toute la chaîne ; surveillance automatique de la purge |
| Montée en charge supérieure aux capacités du support | Déploiement par étapes ; FAQ ; quotas ; hébergement testé |
| Dépendance à un seul client (Interco) | Offre ouverte à d'autres organisations ; pas d'exclusivité |
| Conflit d'intérêts entre mandat syndical et activité commerciale | Transparence auprès des instances ; retrait des décisions concernées |
| Consultation juridique rémunérée / activité encadrée | CGU relues par un avocat ; avertissement visible ; vocabulaire « aide documentaire » |
| Palier gratuit Gemini | Offre payante uniquement ; accord de traitement ; région UE si possible |

### Points à faire valider par un professionnel
- Statut juridique de l'activité, TVA applicable et conditions comptables.
- AIPD, registre des traitements et contrats de sous-traitance (Render, Neon, Google, prestataire de paiement).
- CGU, CGV, mentions légales et formulation de l'offre (information documentaire et non conseil juridique).
- Règles internes de l'organisation concernant les achats et les conflits d'intérêts.
- Assurance responsabilité civile professionnelle.

## 4. Règles de pilotage du développement

- Ce document est la référence produit, conformité et commerciale pour la suite du projet ; toute évolution doit être explicitement arbitrée.
- Les phases se valident sur leurs critères de sortie, pas sur la seule réalisation apparente d'une tâche.
- Les tarifs sont validés comme grille cible, mais les paiements ne doivent pas être activés tant que les produits du prestataire, la TVA, les CGU/CGV et les parcours de résiliation ne sont pas alignés.
- La validation de ce document ne vaut pas validation juridique ni preuve de conformité effective.
