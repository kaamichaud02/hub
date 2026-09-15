# hub — Contexte du monorepo

Repo unique : https://github.com/kaamichaud02/hub

Ce repo contient **deux applications séparées** (chacune son conteneur
Docker), orchestrées ensemble par le `docker-compose.yml` à la racine :

```
hub/
├── docker-compose.yml       # orchestre les deux services ci-dessous
├── .env.example
├── .github/workflows/
│   └── suivi_temps-docker.yml   # CI : build+push l'image suivi_temps sur changement dans suivi_temps/
├── hub-app/                  # App 1 : le hub kanban (FastAPI)
│   ├── app/
│   │   ├── main.py            # routes API (boards, columns, tasks)
│   │   ├── models.py          # SQLModel : Board, Column, Task
│   │   ├── database.py        # connexion Postgres externe
│   │   └── schemas.py
│   ├── static/
│   │   ├── index.html
│   │   ├── css/style.css      # thème sombre
│   │   └── js/app.js          # SortableJS, drag & drop tuiles + kanban
│   ├── Dockerfile
│   └── requirements.txt
└── suivi_temps/               # App 2 : saisie de temps (Django)
    ├── timesheet_project/     # settings, urls racine
    ├── timesheets/
    │   ├── models.py           # Timesheet, TimeEntry
    │   ├── services.py         # calcul de durée centralisé
    │   ├── cf_access.py        # validation JWT Cloudflare Access
    │   ├── auth_backends.py    # CloudflareAccessBackend
    │   ├── middleware.py       # CloudflareAccessMiddleware
    │   ├── reports/            # génération PDF (pdf.py) et Word (docx.py)
    │   ├── views.py
    │   ├── forms.py
    │   ├── tests.py            # 11 tests, tous passent
    │   └── templates/
    ├── Dockerfile
    └── requirements.txt
```

## App 1 : hub-app (kanban)

**Objectif** : outil kanban perso pour suivre l'avancement des projets de
Jean-François (suivi_temps, Factorio, PRTG, etc.). Chaque projet = une
tuile sur la page d'accueil ; cliquer ouvre un tableau kanban (colonnes +
cartes en drag & drop).

**Stack** : FastAPI + SQLModel, PostgreSQL EXTERNE existant (pas de
conteneur dédié — connexion via `HUB_DB_*`), frontend HTML/CSS/JS vanilla
+ SortableJS (CDN), pas de framework JS.

**Modèle de données** : `Board` (projet : nom, icône, couleur,
description, position) → `Column` (colonne kanban) → `Task` (tâche :
titre, description, tags, position).

**État actuel** : code complet généré, un board "suivi_temps" pré-rempli
au démarrage (`seed_default_data` dans `main.py`) — mais **ces tâches de
seed datent d'avant qu'on connaisse le vrai contenu de suivi_temps et
sont probablement à revoir** une fois la section suivi_temps du hub
construite pour de vrai.

**Pas encore fait** : le vrai kanban (colonnes/tâches réelles) pour la
section "suivi_temps" n'a pas été construit — priorité actuelle, une
fois l'authentification unifiée en place (voir plus bas).

## App 2 : suivi_temps (saisie de temps)

**Objectif** : chaque utilisateur entre ses heures jour par jour (heure
début/fin), voit un résumé hebdomadaire, exporte des rapports PDF/Word.

**Comptes existants à préserver** (mapping par email exact, tables
`Timesheet`/`TimeEntry` non touchées par la refonte) :
- `kaamichaud02` (Jean-François, superuser)
- `Marie-Claude` (Charest)
- `amelie.cote@gmail.com` (Amélie Cote)

**Refonte structurelle effectuée** :
- Logique de calcul de durée centralisée dans `services.py` (était
  dupliquée dans models.py + 2 générateurs de rapport)
- Bug corrigé : quart passant minuit en fin de mois plantait
  (`end.replace(day=end.day + 1)` → `end + timedelta(days=1)`)
- Génération PDF/Word séparée en `reports/pdf.py` et `reports/docx.py`,
  données partagées via `reports/common.py`
- 11 tests unitaires (calcul de durée + middleware d'auth), tous passent

## Authentification unifiée — Cloudflare Access (en cours)

**Décision architecturale** : le hub (`hub-app`) doit authentifier pour
**tous les modules**, y compris suivi_temps. Approche retenue : chaque
app valide elle-même le JWT Cloudflare Access (Entra ID SSO déjà en
place sur kaa.zone) plutôt que de construire un serveur d'identité
séparé — Cloudflare fournit déjà la SSO entre sous-domaines kaa.zone.

**Déjà fait pour suivi_temps** :
- Login/signup Django classique **retiré complètement**
- `cf_access.py` valide le JWT via JWKS Cloudflare, extrait l'email
- `auth_backends.py` (`CloudflareAccessBackend`) retrouve le `User`
  Django par email exact, aucun mot de passe vérifié
- `middleware.py` connecte automatiquement l'utilisateur à chaque
  requête ; email inconnu → page "compte non trouvé" (403), pas de
  création automatique — un admin crée le compte via `/admin/`
- Déconnexion redirige vers l'URL de logout Cloudflare Access

**Pas encore fait pour hub-app** : le hub (FastAPI) n'a **aucune**
authentification pour l'instant — à faire avec la même logique (valider
le JWT Cloudflare Access), probablement en adaptant `cf_access.py` pour
FastAPI plutôt que Django.

**Variables d'environnement à renseigner** (Zero Trust dashboard, pas
encore remplies) :
- `CF_ACCESS_TEAM_DOMAIN` — partagé entre tous les modules (Zero Trust >
  Settings > Custom Pages)
- `ST_CF_ACCESS_AUD` — AUD tag spécifique à l'application suivi_temps
  (Zero Trust > Access > Applications)
- Le hub aura son propre AUD tag une fois son auth construite

## État global / prochaines étapes (une chose à la fois)
1. ✅ hub-app : structure + kanban de base (drag & drop tuiles et tâches)
2. ✅ suivi_temps : refonte structurelle (services.py, reports/, tests)
3. ✅ suivi_temps : authentification Cloudflare Access
4. ⬜ Écrire tous les fichiers sur disque dans ce repo (fait par Claude
   Code à partir de ce prompt)
5. ⬜ Remplir `.env`, tester chaque app localement
6. ⬜ Configurer les applications Cloudflare Access (AUD tags)
7. ⬜ git init / commit / push vers kaamichaud02/hub
8. ⬜ Authentification du hub lui-même (FastAPI) via Cloudflare Access
9. ⬜ Construire le vrai kanban de la section "suivi_temps" dans le hub
   (revoir les tâches de seed, actuellement obsolètes)
10. ⬜ Déploiement Portainer sur OVH-BHS, exposition via Cloudflare Tunnel

## Dépôt Git
- Repo : https://github.com/kaamichaud02/hub
- Pas encore initialisé localement — à faire : git init, remote origin,
  commit initial, push
