from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class Recipe(SQLModel, table=True):
    """Une recette, dans la base du hub (HUB_DB) — même base que Kanban,
    livre de recettes global partagé entre tous les utilisateurs du hub."""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    ingredients: str = ""  # bloc texte, un ingrédient par ligne
    steps: str = ""  # bloc texte, une étape par ligne
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    servings: Optional[int] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    added_by_email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RecipeComment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    author_email: str
    author_name: str = ""
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
