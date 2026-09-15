from typing import Optional, List
from pydantic import BaseModel


class RecipeCreate(BaseModel):
    title: str
    ingredients: str = ""
    steps: str = ""
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    servings: Optional[int] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None


class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    ingredients: Optional[str] = None
    steps: Optional[str] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    servings: Optional[int] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None


class RecipeExtractRequest(BaseModel):
    content: str
    source_url: Optional[str] = None
    title_hint: Optional[str] = None


class CommentCreate(BaseModel):
    body: str


class ExtractedRecipe(BaseModel):
    """Schéma de sortie structurée demandé à Claude (client.messages.parse)."""
    title: str
    ingredients: List[str]
    steps: List[str]
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    servings: Optional[int] = None
    image_url: Optional[str] = None
