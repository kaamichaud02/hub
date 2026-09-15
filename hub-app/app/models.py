from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class Board(SQLModel, table=True):
    """Un projet (ex: suivi_temps, Factorio, PRTG...). Représenté par une tuile sur le hub."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    icon: Optional[str] = Field(default="📋")  # emoji ou petit label pour la tuile
    color: Optional[str] = Field(default="#5865f2")
    description: Optional[str] = Field(default="")
    position: int = Field(default=0)  # ordre des tuiles sur le hub
    created_at: datetime = Field(default_factory=datetime.utcnow)

    columns: List["Column"] = Relationship(back_populates="board", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Column(SQLModel, table=True):
    """Une colonne kanban à l'intérieur d'un board (ex: À faire / En cours / Terminé)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    board_id: int = Field(foreign_key="board.id")
    name: str
    position: int = Field(default=0)

    board: Optional[Board] = Relationship(back_populates="columns")
    tasks: List["Task"] = Relationship(back_populates="column", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class Task(SQLModel, table=True):
    """Une tâche (tuile déplaçable) dans une colonne."""
    id: Optional[int] = Field(default=None, primary_key=True)
    column_id: int = Field(foreign_key="column.id")
    title: str
    description: Optional[str] = Field(default="")
    tags: Optional[str] = Field(default="")  # liste de tags séparés par virgule
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    column: Optional[Column] = Relationship(back_populates="tasks")
