import os
from pathlib import Path

# load .env from project root so ANTHROPIC_API_KEY is always available
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.db import get_db, ensure_recommendations_table
from app.routers import upload, recommendations, ratings, favorites, browse

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PORT = int(os.getenv("PORT", 8000))

origins = ["*"] if ENVIRONMENT == "development" else [
    os.getenv("ALLOWED_ORIGIN", "*")
]

app = FastAPI(title="Fashion Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(ratings.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(browse.router, prefix="/api")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.on_event("startup")
async def startup():
    print(f"[Startup] Environment: {ENVIRONMENT}")
    print(f"[Startup] Port: {PORT}")
    ensure_recommendations_table()
    try:
        db = get_db()
        count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        db.close()
        print(f"[Startup] fashion.db connected ✓  ({count} products)")
    except Exception as e:
        print(f"[Startup] fashion.db ERROR: {e}")


@app.get("/health")
def health():
    try:
        db = get_db()
        db.execute("SELECT 1")
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "environment": ENVIRONMENT}
