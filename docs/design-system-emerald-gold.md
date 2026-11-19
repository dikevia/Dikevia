# Dikévia — système de design Emerald & Gold

Version : 1.0  
Statut : référence visuelle pour la bêta web et l'application Android native.

## Intention

Une identité institutionnelle, contemporaine et rassurante : l'émeraude porte la marque et les actions ; l'or apporte une finition premium limitée aux commandes et à quelques repères graphiques. Le contenu juridique doit rester neutre, calme et immédiatement lisible.

## Palette officielle

| Jeton | Valeur | Usage |
|---|---|---|
| `brand` | `#087F68` | Émeraude principal, liens, icônes de marque |
| `brand-deep` | `#075B4D` | Boutons et éléments interactifs principaux |
| `brand-dark` | `#063F37` | En-tête, fonds forts, profondeur |
| `brand-bright` | `#13A47D` | Dégradés décoratifs, accents de marque |
| `brand-soft` | `#E2F5EE` | Sélections et surfaces douces |
| `accent-gold` | `#C9A45D` | Filets, bordures, détails |
| `accent-gold-text` | `#F0D79F` | Libellés des boutons principaux sur fond vert profond |
| `accent-gold-hover` | `#FFEBBD` | Libellés des boutons au survol |
| `ink` | `#142B25` | Texte courant et contenu juridique |
| `muted` | `#637B71` | Métadonnées et aides |
| `line` | `#DCEBE4` | Bordures |
| `canvas` | `#F3F8F5` | Fond général |
| `surface` | `#FFFFFF` | Cartes et panneaux |
| `surface-soft` | `#F7FCF9` | Fonds secondaires |

**Règle de contraste :** les libellés dorés sont associés à un fond vert profond (`#075B4D` ou plus sombre), jamais au vert émeraude lumineux seul. Les boutons secondaires utilisent un fond menthe et un texte vert foncé.

## Typographie

- Police système sans-serif : Android Roboto / fallback système, web system-ui.
- Titres : graisse 700–800, interlettrage légèrement resserré.
- Texte courant : graisse 400–500, hauteur de ligne confortable (1,5 à 1,7).
- Libellés de commandes : graisse 600–700.
- Métadonnées : 11–12 sp/px, couleur muted.
- Éviter les capitales longues et les textes dorés hors libellés de commandes.

## Composants

### Boutons
- Primaire : fond vert profond, libellé or clair, rayon 10–12 dp, hauteur cible 48–52 dp sur mobile.
- Survol/pression : fond encore plus sombre ; ne pas faire clignoter ou déplacer le bouton.
- Secondaire : fond menthe, libellé vert foncé.
- Danger : rouge réservé aux suppressions et actions irréversibles.
- Désactivé : contraste réduit mais libellé toujours compréhensible.
- Navigation, suppression d'historique et actions discrètes : jamais de typographie dorée.

### Cartes et panneaux
- Fond blanc, bordure vert-gris très pâle, rayon 14–18 dp.
- Ombre légère et diffuse, sans relief excessif.
- Espacement interne conseillé : 16–22 dp.
- Fond de page vert-gris presque blanc.

### Navigation
- Barre supérieure dégradée du vert sombre vers l'émeraude.
- Élément actif sur fond menthe, texte vert profond et repère or discret.
- Sur téléphone, navigation basse compacte avec zones tactiles confortables ; éviter le défilement horizontal des onglets.

### Assistant juridique
- Interface claire, fond blanc, bulles légèrement teintées.
- Message utilisateur : menthe pâle.
- Réponse Dikévia : fond blanc/vert très léger, texte principal `#142B25`.
- Statut de vérification : pastille verte/ambre/rouge selon le statut.
- Sources : cartes blanches, titres et extraits neutres ; liens officiels en émeraude.
- **Interdiction d'utiliser l'or pour le texte des réponses, avertissements, extraits, citations ou références juridiques.**
- La couleur ne doit jamais être le seul moyen de transmettre un statut : toujours afficher son libellé.

### Connexion
- Écran aéré, marque visible, une action principale.
- Bouton de connexion vert profond avec libellé or clair.
- Texte d'explication et de sécurité en gris/vert neutre ; pas de jargon technique inutile.

## Écrans Android à habiller avec ces composants

1. Connexion / reprise de session.
2. Accueil et raccourcis.
3. Assistant juridique et historique de conversation.
4. Documents et recherche documentaire.
5. Collectivités.
6. Membres et invitations (selon droits).
7. Profil / préférences.
8. Facturation, si activée pour le rôle et l'offre.

Les règles d'accès et les flux API restent ceux du backend : ce document ne les modifie pas.

## Android Compose — correspondances recommandées

- Définir les couleurs dans un `DikeviaColorScheme` ou un `Color.kt` central ; ne pas disperser les valeurs hexadécimales dans les écrans.
- Créer des composants partagés : `DikeviaPrimaryButton`, `DikeviaSecondaryButton`, `DikeviaCard`, `DikeviaTopBar`, `DikeviaBottomNavigation`, `VerificationStatusChip`, `LegalSourceCard`.
- Utiliser Material 3 comme base, avec un thème clair personnalisé.
- Respecter les tailles tactiles Android (48 dp minimum), les insets système et le mode paysage.
- Prévoir les états chargement, vide, erreur, hors ligne, session expirée et accès refusé.
- Respecter les réglages d'accessibilité : taille de police système, TalkBack, contraste, réduction des animations.

## Hors périmètre

Ce système de design ne définit ni les règles métier, ni l'authentification OIDC, ni les droits, ni les appels API, ni la fiabilité juridique. Il ne faut pas introduire de données fictives pour remplir les écrans.
