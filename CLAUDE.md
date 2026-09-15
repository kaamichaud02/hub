# hub — Contexte du monorepo

Repo : https://github.com/kaamichaud02/hub

**Une seule application** déployée (FastAPI, `hub-app/`). L'ancienne app
Django `suivi_temps/` a été **fusionnée dans hub-app** comme section —
son dossier reste dans le repo pour référence, mais son code n'est plus
déployé ni exécuté depuis ici. Sa base Postgres existante est toujours
utilisée (lue/écrite directement par hub-app).

```
hub/
├── docker-compose.yml            # un seul service : hub
├── .env.example                  # liste toutes les variables requises
├── .github/workflows/
│   └── hub-docker.yml            # CI : build+push ghcr.io/kaamichaud02/hub
│                                  #   tag :dev sur push vers dev, :latest sur master
├── extension/                    # extension navigateur (capture de recette)
│   ├── manifest.json             # Manifest V3, Chrome/Edge
│   ├── background.js             # capture page active + POST au hub
│   └── README.md
├── hub-app/
│   ├── app/
│   │   ├── main.py                    # app FastAPI, /api/whoami, /api/version
│   │   ├── database.py                # engine HUB_DB + migrations idempotentes
│   │   ├── models.py                  # Board, Column, Task (Kanban)
│   │   ├── schemas.py
│   │   ├── timesheets_db.py           # 2e engine, base ST_DATABASE (suivi_temps)
│   │   ├── timesheets_models.py       # AuthUser, TimesheetST, TimeEntryST
│   │   │                              #   (mappent les tables Django EXISTANTES)
│   │   ├── timesheets_auth.py         # JWT Cloudflare Access + auto-provisioning
│   │   ├── timesheets_services.py     # calcul de durée (porté de suivi_temps)
│   │   ├── timesheets_routes.py       # /api/timesheets/*
│   │   ├── timesheets_reports/        # génération PDF/Word (portée de suivi_temps)
│   │   ├── admin_routes.py            # /api/admin/users (gestion comptes, superuser)
│   │   ├── recipes_models.py          # Recipe, RecipeComment, RecipeRevision
│   │   ├── recipes_ai.py              # appels Claude (extraction, correction/conversion)
│   │   ├── recipes_routes.py          # /api/recipes/*
│   │   └── recipes_schemas.py
│   ├── static/
│   │   ├── index.html
│   │   ├── css/style.css              # thème sombre, un seul fichier
│   │   └── js/
│   │       ├── app.js                 # shell : sidebar, sections, whoami, version
│   │       ├── timesheets.js          # section "Suivi de temps"
│   │       └── recipes.js             # section "Recette"
│   ├── tests/                         # pytest (logique de durée, dépendance auth)
│   ├── Dockerfile
│   └── requirements.txt
└── suivi_temps/                  # Django, référence seulement — non déployé
```

## Architecture du hub

**Sidebar avec 3 sections** (SPA JSON+JS vanilla, pas de framework, pas de
build step) :
1. **Kanban** — tuiles de projets → colonnes/tâches drag & drop (`Board`/
   `Column`/`Task`, base `HUB_DB`)
2. **Suivi de temps** — saisie d'heures, résumé hebdomadaire, export PDF/
   Word (porté de l'ancien Django, base `ST_DATABASE` = l'ancienne base
   suivi_temps, tables `auth_user`/`timesheets_timesheet`/
   `timesheets_timeentry` **existantes, jamais recréées**)
3. **Recette** — livre de recettes global avec commentaires, tags,
   recherche, historique des modifications ; extraction IA (Claude) à
   partir de texte collé ou de la capture par l'extension navigateur ;
   images stockées en base (BYTEA)

**Deux bases Postgres séparées** (deux engines SQLAlchemy dans le même
process) :
- `HUB_DB_*` → `Board`/`Column`/`Task`/`Recipe`/`RecipeComment`/
  `RecipeRevision` — tables gérées par hub-app (`database.py::init_db()`)
- `ST_DATABASE_*` → tables Django existantes de l'ancien suivi_temps,
  **jamais de DDL dessus**, lecture/écriture de données seulement

## Authentification — Cloudflare Access

Une seule application Cloudflare Access protège tout le hub (un seul
domaine). `timesheets_auth.py` valide le JWT via JWKS
(`CF_ACCESS_TEAM_DOMAIN` + `CF_ACCESS_AUD`) et résout l'email vers un
compte `auth_user`.

**Auto-provisioning** : la policy Cloudflare Access est la seule
barrière de sécurité (qui peut même atteindre le hub). Un email qui
passe cette policy obtient donc son compte automatiquement à la
première requête (`get_or_create_user`), toujours **sans droits admin**
(`is_superuser=False`) et sans nom — la personne configure son nom via
l'engrenage dans la sidebar (PATCH `/api/whoami`). Promouvoir quelqu'un
admin reste un acte manuel (section Administration, superuser only).

## Déploiement — Arcane + branches Git

- **`dev`** → `hubtest.kaa.zone`, image `ghcr.io/kaamichaud02/hub:dev`
- **`master`** → prod (domaine pas encore configuré), image
  `ghcr.io/kaamichaud02/hub:latest`
- CI (`hub-docker.yml`) build+push sur push vers l'une ou l'autre branche,
  tag selon la branche
- Déploiement via Arcane (sync Git du repo + `docker-compose.yml`),
  redéploiement manuel après un push (pas toujours automatique — parfois
  il faut forcer "Mettre à jour les conteneurs")
- **Workflow de fusion** : dev pour tester, puis merge manuel vers
  master (`git merge dev --no-ff`) — vérifier après merge que
  `docker-compose.yml` garde bien `image: ...:latest` (pas `:dev`), le
  merge peut avoir besoin d'un arbitrage sur cette ligne

## Variables d'environnement (voir `.env.example`)

| Var | Usage |
|---|---|
| `HUB_DB_*` | base Kanban/Recette |
| `CF_ACCESS_TEAM_DOMAIN` | domaine Zero Trust, partagé |
| `CF_ACCESS_AUD` | AUD tag de l'app Cloudflare Access du hub (une seule maintenant, plus de AUD séparé pour suivi_temps) |
| `ST_DATABASE_*` | base suivi_temps existante |
| `ANTHROPIC_API_KEY` | extraction/correction IA (section Recette) |

**Important** : `docker-compose.yml` doit lister explicitement CHAQUE
variable dans `environment:` du service `hub` — les oublier ici est une
source d'erreurs déjà rencontrée (le code lit bien la variable via
`os.getenv()`, mais si elle n'est pas dans `docker-compose.yml`, elle
n'est jamais injectée dans le conteneur).

## Pièges rencontrés (pour éviter de les refaire)

- **`SQLModel.metadata.create_all()` ne crée que les tables manquantes,
  jamais les colonnes manquantes sur une table déjà déployée.** Ajouter
  un champ à un modèle existant nécessite un `ALTER TABLE ... ADD COLUMN
  IF NOT EXISTS` explicite dans `database.py::_ensure_columns()`.
- **Piège Pydantic** : un champ nommé comme son type avec une valeur par
  défaut (`date: Optional[date] = None`) fait que Pydantic résout le
  type comme `NoneType` (la valeur par défaut de classe masque le type
  importé). Importer les types avec un alias (`date as date_`) dans les
  fichiers de schémas.
- **Cloudflare intercepte les réponses 502/504** de l'origine et les
  remplace par sa propre page d'erreur générique — utiliser 422/400/500
  pour les erreurs applicatives, jamais 502/504.
- **Cache Cloudflare (edge) ≠ cache navigateur** : un Ctrl+Shift+R ne
  contourne pas le cache Cloudflare. Purger via Cloudflare > Caching >
  Purge Cache si un changement de CSS/JS semble ne pas s'appliquer alors
  que le déploiement est confirmé à jour (vérifier `v<sha>` sous "Hub"
  dans la sidebar en premier).
- **Arcane ne redéploie pas toujours automatiquement** après un push —
  vérifier/forcer la resynchronisation + "Mettre à jour les conteneurs"
  si le changement ne semble pas pris en compte.

## Prochaines étapes

1. ⬜ **Déploiement production** : nouveau projet Arcane pointant sur
   `master`, nouvelle application Cloudflare Access pour le domaine de
   prod (son propre AUD tag), `.env` avec les vraies valeurs de prod
2. ⬜ Icônes personnalisées pour l'extension navigateur (utilise
   l'icône générique du navigateur pour l'instant)
3. ⬜ Port Firefox de l'extension (actuellement Chrome/Edge, Manifest V3)
4. ⬜ Revoir/nettoyer le board Kanban "suivi_temps" pré-rempli au
   démarrage (`seed_default_data` dans `main.py`) — ses tâches datent
   d'avant la fusion et ne reflètent plus l'état réel du projet
5. Idée en suspens : suppression éventuelle du dossier `suivi_temps/`
   (Django) une fois la fusion validée en prod depuis un moment — le
   garder pour l'instant comme référence/filet de sécurité
