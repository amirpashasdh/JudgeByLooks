# Deployment Guide

## First time setup

### 1. Run seed script
```bash
python seed_db.py
```
→ creates `style-keywords/fashion_seed.db` (products only, no user data)

### 2. Push to GitHub
```bash
git init          # if not already a repo
git add .
git commit -m "Initial deployment"
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### 3. Create Railway project
- Go to [railway.app](https://railway.app)
- **New Project → Deploy from GitHub repo**
- Select your repository
- Railway auto-detects Python and installs `requirements.txt`

### 4. Set environment variables on Railway
In Railway dashboard → your service → **Variables** tab:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your key from console.anthropic.com |
| `ENVIRONMENT` | `production` |

Railway sets `PORT` automatically — do not override it.

### 5. Deploy
Railway deploys automatically on every `git push`.
Watch the build logs in Railway dashboard for:
```
[Startup] Environment: production
[Startup] Port: XXXX
[Startup] fashion.db connected ✓  (18 products)
```

Your app will be live at:
`https://your-app-name.up.railway.app`

---

## Redeploying after catalog update

```bash
# 1. Run scraper + tagger pipeline locally
# 2. Rebuild seed DB
python seed_db.py

# 3. Commit and push
git add style-keywords/fashion_seed.db
git commit -m "Update product catalog"
git push          # Railway redeploys automatically
```

---

## Local development

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# Use the project venv (has ultralytics + opencv)
source style-keywords/venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000

---

## Production-like local test

```bash
ENVIRONMENT=production uvicorn app.main:app --port 8000
```

Confirm:
- `[Startup] Environment: production` in terminal
- `/health` returns `{"status":"ok","db":"connected","environment":"production"}`
- Full flow: upload → processing → results → browse → thankyou

---

## Checking Railway logs

Railway dashboard → your service → **Deployments** → click a deployment → **View logs**

---

## Architecture notes

### Database layout
| File | Purpose | On Railway |
|---|---|---|
| `style-keywords/fashion_seed.db` | Products + empty user tables | Committed to git, survives redeploy |
| `style-keywords/fashion.db` | Local dev only | Gitignored |
| `style-keywords/keywords.db` | Person analysis vectors | Created fresh per-deploy (ephemeral) |

### Ephemeral data
On Railway's free tier the filesystem resets on redeploy. This means:
- **Products** persist (seeded from git)
- **Ratings, favorites, recommendations** are lost on redeploy — acceptable for now
- **Person analysis** (keywords.db) is lost on redeploy — users re-upload each session

To make user data persistent, replace SQLite with a hosted database:
- Railway PostgreSQL add-on
- PlanetScale (MySQL)
- Supabase (PostgreSQL)

### ANTHROPIC_API_KEY
Without this key the `/api/upload` endpoint will fail.
Set it in Railway Variables before testing the live app.
The analyser uses `claude-sonnet-4-6` by default (see `style-keywords/analyzer.py`).
