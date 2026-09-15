# Extension "Capture de recette"

Capture la recette affichée dans l'onglet actif et l'envoie au hub
(`/api/recipes/extract`), qui utilise Claude pour l'analyser et la
sauvegarder automatiquement — pas d'aperçu, la recette est créée
directement.

## Installation (mode développeur)

1. Ouvrir `chrome://extensions` (ou `edge://extensions`)
2. Activer "Mode développeur" (en haut à droite)
3. "Charger l'extension non empaquetée" → sélectionner ce dossier (`extension/`)
4. L'icône apparaît dans la barre d'outils (icône générique par défaut, pas
   encore d'icône personnalisée)

## Prérequis

- Être déjà connecté au hub dans ce navigateur (l'extension réutilise le
  cookie de session Cloudflare Access existant — pas d'authentification
  séparée)
- `ANTHROPIC_API_KEY` configurée côté serveur (sinon l'extraction échoue,
  badge ✗)

## Utilisation

1. Ouvrir une page de recette
2. Cliquer sur l'icône de l'extension
3. Badge "…" pendant l'analyse, puis "✓" (recette ajoutée) ou "✗" (échec —
   voir la console du service worker via `chrome://extensions` → "Service
   worker" pour le détail de l'erreur)

## Configuration

`HUB_BASE_URL` dans `background.js` pointe sur `https://hubtest.kaa.zone`
par défaut (environnement de test) — à changer pour le domaine de
production une fois disponible, et à ajouter dans `host_permissions` du
`manifest.json` si ce n'est pas déjà `hub.kaa.zone`.
