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
    tags: str = ""  # bloc texte, tags séparés par virgule (même convention que Task.tags)
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


class RecipeRevision(SQLModel, table=True):
    """Instantané d'une recette juste avant une modification manuelle (voir
    update_recipe dans recipes_routes.py) — permet de consulter les versions
    précédentes après un changement d'ingrédient/quantité."""
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id")
    title: str
    ingredients: str = ""
    steps: str = ""
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    servings: Optional[int] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    tags: str = ""
    edited_by_email: Optional[str] = None
    snapshotted_at: datetime = Field(default_factory=datetime.utcnow)
