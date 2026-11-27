# Dikévia — système de design Émeraude & Or

Version : 1.0  
Statut : référence visuelle à appliquer au web complémentaire et aux applications mobiles natives.

## Intention

Une identité institutionnelle, contemporaine et rassurante : l'émeraude porte la marque et les actions ; l'or apporte une finition premium limitée aux libellés de certaines commandes et à quelques repères graphiques. Le contenu juridique reste neutre, calme et immédiatement lisible.

## Palette

| Jeton | Valeur | Usage |
|---|---|---|
| `brand` | `#087F68` | Émeraude principal, liens, icônes de marque |
| `brand-deep` | `#075B4D` | Boutons et éléments interactifs principaux |
| `brand-dark` | `#063F37` | En-tête, fonds forts, profondeur |
| `brand-bright` | `#13A47D` | Accents de marque limités |
| `brand-soft` | `#E2F5EE` | Sélections et surfaces douces |
| `accent-gold` | `#C9A45D` | Filets, bordures et détails |
| `accent-gold-text` | `#F0D79F` | Libellés des boutons principaux sur fond vert profond |
| `accent-gold-hover` | `#FFEBBD` | Libellés des boutons au survol |
| `ink` | `#142B25` | Texte courant et contenu juridique |
| `muted` | `#637B71` | Métadonnées et aides |
| `line` | `#DCEBE4` | Bordures |
| `canvas` | `#F3F8F5` | Fond général |
| `surface` | `#FFFFFF` | Cartes et panneaux |
| `surface-soft` | `#F7FCF9` | Fonds secondaires |

### Règles d'usage et de contraste

- Les libellés dorés sont associés à un fond vert profond (`#075B4D` ou plus sombre), jamais à l'émeraude lumineux seul.
- L'or ne devient pas une couleur de fond générale, de carte, de panneau ou de navigation.
- Les boutons secondaires utilisent un fond menthe et un texte vert foncé.
- Les libellés dorés sont réservés aux commandes principales ; ils ne sont pas utilisés pour la navigation, la suppression d'historique ou les actions discrètes.
- Le texte juridique, les avertissements, les extraits, les citations et les références restent dans des couleurs neutres. L'or ne doit jamais être utilisé pour ces contenus.
- La couleur ne doit jamais être le seul moyen de transmettre un statut : toujours afficher un libellé explicite.

## Typographie

- Police système sans-serif : Roboto sur Android, fallback système sur iOS et system-ui sur le web.
- Titres : graisse 700–800, interlettrage légèrement resserré.
- Texte courant : graisse 400–500, hauteur de ligne confortable (1,5 à 1,7).
- Libellés de commandes : graisse 600–700.
- Métadonnées : 11–12 sp/px, couleur muted.
- Éviter les capitales longues et les textes dorés hors libellés de commandes principales.

## Composants

### Boutons
- Primaire : fond vert profond, libellé or clair, rayon 10–12 dp, hauteur cible 48–52 dp sur mobile.
- Survol/pression : fond encore plus sombre ; aucun déplacement ou clignotement.
- Secondaire : fond menthe, libellé vert foncé.
- Danger : rouge réservé aux suppressions et actions irréversibles.
- Désactivé : contraste réduit mais libellé toujours compréhensible.

### Cartes et panneaux
- Fond blanc, bordure vert-gris très pâle, rayon 14–18 dp.
- Ombre légère et diffuse, sans relief excessif.
- Espacement interne conseillé : 16–22 dp.
- Fond de page vert-gris presque blanc.

### Navigation
- Barre supérieure pouvant utiliser un dégradé du vert sombre vers l'émeraude.
- Élément actif sur fond menthe, texte vert profond et repère or discret.
- Sur téléphone, navigation basse compacte avec zones tactiles confortables ; éviter le défilement horizontal des onglets.

### Assistant juridique
- Interface claire, fond blanc, bulles légèrement teintées.
- Message utilisateur : menthe pâle.
- Réponse Dikévia : fond blanc/vert très léger, texte principal `#142B25`.
- Statut de vérification : indicateur vert/ambre/rouge selon le statut, accompagné de son libellé.
- Sources : cartes blanches, titres et extraits neutres ; liens officiels en émeraude.
- L'or est exclu des réponses, avertissements, extraits, citations et références juridiques.

### Connexion
- Écran aéré, marque visible, une action principale.
- Bouton de connexion vert profond avec libellé or clair.
- Texte d'explication et de sécurité en gris/vert neutre ; éviter le jargon technique inutile.

## Écrans mobiles à habiller avec ces composants

1. Connexion et reprise de session.
2. Accueil et raccourcis.
3. Assistant juridique et historique de conversation.
4. Documents et recherche documentaire.
5. Collectivités.
6. Membres et invitations selon les droits.
7. Profil et préférences.
8. Facturation uniquement si elle est activée pour le rôle et l'offre.

## Architecture UI native

- Android : centraliser les couleurs dans un thème Material 3 (`DikeviaColorScheme` / `Color.kt`) ; ne pas disperser les valeurs hexadécimales dans les écrans.
- iOS : centraliser les couleurs et styles dans un thème SwiftUI partagé.
- Créer des composants réutilisables : bouton primaire/secondaire, carte, barre supérieure, navigation basse, indicateur de vérification et carte de source juridique.
- Respecter les zones tactiles d'au moins 48 dp, les insets système, le mode paysage et les tailles de texte système.
- Prévoir les états chargement, vide, erreur, hors ligne, session expirée et accès refusé.
- Respecter TalkBack/VoiceOver, le contraste, l'accessibilité et la réduction des animations.

## Hors périmètre

Ce système de design ne définit ni les règles métier, ni l'authentification OIDC, ni les droits, ni les appels API, ni la fiabilité juridique. Il ne faut pas introduire de données fictives pour remplir les écrans.
