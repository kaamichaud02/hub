import os
from sqlmodel import Session, create_engine

# Connexion à la base Postgres EXISTANTE de suivi_temps (auth_user,
# timesheets_timesheet, timesheets_timeentry). Ces tables sont gérées par les
# migrations Django historiques, pas par ce module — ne JAMAIS appeler
# create_all() ou toute autre opération DDL sur `engine_st` : ce module est en
# lecture/écriture de DONNÉES uniquement, jamais de schéma.

ST_DB_HOST = os.getenv("ST_DATABASE_HOST", "localhost")
ST_DB_PORT = os.getenv("ST_DATABASE_PORT", "5432")
ST_DB_NAME = os.getenv("ST_DATABASE_NAME", "")
ST_DB_USER = os.getenv("ST_DATABASE_USER", "")
ST_DB_PASSWORD = os.getenv("ST_DATABASE_PASSWORD", "")

ST_DATABASE_URL = f"postgresql+psycopg2://{ST_DB_USER}:{ST_DB_PASSWORD}@{ST_DB_HOST}:{ST_DB_PORT}/{ST_DB_NAME}"

engine_st = create_engine(ST_DATABASE_URL, pool_pre_ping=True)


def get_session_st():
    with Session(engine_st) as session:
        yield session
