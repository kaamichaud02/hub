import os
from sqlmodel import SQLModel, Session, create_engine

from .models import Board, Column, Task

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
    SQLModel.metadata.create_all(engine, tables=[Board.__table__, Column.__table__, Task.__table__])


def get_session():
    with Session(engine) as session:
        yield session
