# Dikévia — identité visuelle JARVIS

Statut : direction visuelle de référence retrouvée dans le code de `main`.  
Source d'implémentation : `frontend/dikevia-chat-theme.css`, notamment le bloc final `DIKEVIA JARVIS`, ainsi que `android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt`.

## 1. Direction retenue

Dikévia utilise l'identité visuelle surnommée **JARVIS** : une présence IA matérialisée par une sphère lumineuse, avec un mouvement subtil et vivant. Ce n'est pas une identité Émeraude & Or.

La palette finale de l'application standard est explicitement décrite dans le CSS comme « glacier / acier / bleu nuit ». Le thème final est clair, avec surfaces blanches, bleus glacier, bleus acier et texte bleu nuit. L'administration reprend la même identité avec une interface de pilotage dédiée.

## 2. Couleurs observées dans le code

Les valeurs ci-dessous proviennent du bloc final JARVIS de `frontend/dikevia-chat-theme.css`, pas d'une proposition nouvelle :

| Rôle | Valeur |
|---|---|
| Fond général | `#f3f7fb` |
| Texte principal | `#17283b` |
| Surface principale | `#ffffff` |
| Surface secondaire | `#f5f9fd` |
| Bordure | `#dce6f0` |
| Bleu principal | `#287fbd` |
| Bleu lumineux | `#54b5ed` |
| Bleu clair | `#eaf3fb` |
| Accent de focus | `#68b4df` |

L'or et l'émeraude ne sont pas des couleurs de marque dans cette direction. Des couches CSS historiques les contiennent encore plus haut dans le fichier, mais le bloc final JARVIS les neutralise pour les surfaces de l'application standard. Ne pas réactiver ces anciennes couches.

## 3. Sphère JARVIS : éléments effectivement présents

Le code actuel comporte déjà plusieurs éléments de cette identité :

- Sphère d'accueil `.juris-welcome-icon` : cercle de 86 px, centre lumineux radial, anneaux concentriques et halo bleu.
- Animation `jarvis-core-pulse` : pulsation de 3,8 secondes avec légère variation d'échelle et de luminosité.
- Icône de marque dans l'en-tête : centre lumineux et anneaux circulaires.
- Marque de l'administration : motif radial circulaire avec halo bleu.
- Anciennes animations `dikevia-breathe` et `dikevia-orbit` : respiration et rotation d'anneau.
- Avatar assistant : noyau lumineux bleu, avec styles `is-generating` et `is-speaking` prévus pour une pulsation plus rapide.

La feuille de style prévoit également la désactivation des animations de la sphère d'accueil lorsque `prefers-reduced-motion: reduce` est actif.

## 4. Écart entre l'existant et l'objectif produit

Le code actuel démontre l'identité visuelle, mais ne prouve pas encore une sphère IA persistante et réellement pilotée par les états de l'assistant.

- La grande sphère est principalement affichée dans l'écran d'accueil de conversation.
- Les états CSS `is-generating` et `is-speaking` existent, mais leur activation effective par le JavaScript doit être vérifiée.
- Aucun lien vérifié n'établit actuellement une animation synchronisée avec les phases réelles du moteur (écoute, compréhension, recherche juridique, génération, erreur, réponse terminée).
- Le rendu observé est une animation CSS 2D ; ne pas le présenter comme une sphère 3D ou un moteur audio-réactif.

## 5. Cible d'évolution

La cible est une sphère JARVIS interactive, animée et réactive à l'état réel de l'IA, sans inventer d'activité :

| État de l'assistant | Comportement visuel cible |
|---|---|
| Inactif / prêt | Respiration lente, halo discret |
| Écoute / saisie vocale | Pulsation légère synchronisée avec l'entrée audio, si une fonction vocale est effectivement active |
| Analyse / recherche | Mouvement orbital plus marqué, sans prétendre que l'IA réfléchit si le backend n'a pas démarré |
| Génération | Pulsation plus rapide et lumineuse |
| Réponse terminée | Retour progressif à l'état prêt |
| Erreur / indisponibilité | État visuel distinct, sobre, avec message textuel accessible |

Les états doivent être pilotés par des événements d'interface/backend fiables, pas par une animation qui simulerait une recherche ou une réflexion inexistante. La sphère doit rester décorative pour les technologies d'assistance (`aria-hidden` si non interactive) ou fournir un libellé accessible si elle reçoit des interactions.

## 6. Portage mobile

- Android natif : réimplémenter le langage visuel avec Jetpack Compose et Canvas/animations Compose ; ne pas encapsuler le site dans une WebView pour prétendre à une expérience native.
- iOS natif : réimplémenter le même comportement avec SwiftUI/Canvas et des animations équivalentes.
- Partager les règles d'état, les durées, les couleurs et les comportements, sans exiger une implémentation graphique identique au pixel près.
- Respecter les réglages de réduction des animations, la consommation énergétique, la fréquence d'images et les performances sur appareils modestes.
- L'application Administration conserve la même identité visuelle, mais ne reçoit pas le chatbot ni la sphère conversationnelle comme écran de conversation.

## 7. Règle de consolidation

Toute branche contenant une ancienne identité Émeraude & Or, un logo juridique statique ou un thème concurrent doit être traitée comme historique. La référence est le bloc final JARVIS actuellement présent dans `frontend/dikevia-chat-theme.css`. Toute modification doit être évaluée contre cette source de vérité et testée sur les éditions standard et administration.
