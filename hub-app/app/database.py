import os
from sqlmodel import SQLModel, Session, create_engine

DB_HOST = os.getenv("HUB_DB_HOST", "localhost")
DB_PORT = os.getenv("HUB_DB_PORT", "5432")
DB_NAME = os.getenv("HUB_DB_NAME", "hub_kaa_zone")
DB_USER = os.getenv("HUB_DB_USER", "hub")
DB_PASSWORD = os.getenv("HUB_DB_PASSWORD", "")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
