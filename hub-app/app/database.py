import os
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import text

from .models import Board, Column, Task
from .recipes_models import Recipe, RecipeComment, RecipeRevision

DB_HOST = os.getenv("HUB_DB_HOST", "localhost")
DB_PORT = os.getenv("HUB_DB_PORT", "5432")
DB_NAME = os.getenv("HUB_DB_NAME", "hub_kaa_zone")
DB_USER = os.getenv("HUB_DB_USER", "hub")
DB_PASSWORD = os.getenv("HUB_DB_PASSWORD", "")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db():
    # SQLModel.metadata est un registre global partagé par TOUTES les classes
    # table=True du process, y compris les modèles suivi_temps (timesheets_models.py)
    # qui pointent vers une base Postgres différente (ST_DATABASE_*). On limite donc
    # explicitement create_all() aux tables possédées par le hub — les tables
    # suivi_temps existent déjà et ne doivent jamais être créées/modifiées ici.
    SQLModel.metadata.create_all(engine, tables=[
        Board.__table__, Column.__table__, Task.__table__,
        Recipe.__table__, RecipeComment.__table__, RecipeRevision.__table__,
    ])
    _ensure_columns()


def _ensure_columns():
    """create_all() ne crée que les tables manquantes, jamais les colonnes
    manquantes sur une table déjà existante — un champ ajouté à un modèle
    après son premier déploiement (ex. Recipe.tags) doit être ajouté ici
    explicitement. ADD COLUMN IF NOT EXISTS : idempotent, sûr à rejouer à
    chaque démarrage."""
    statements = [
        f"ALTER TABLE {Recipe.__tablename__} ADD COLUMN IF NOT EXISTS tags TEXT NOT NULL DEFAULT ''",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def get_session():
    with Session(engine) as session:
        yield session
