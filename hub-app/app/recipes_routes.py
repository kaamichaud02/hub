from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Response
from sqlmodel import Session, select

from .database import get_session
from .recipes_models import Recipe, RecipeComment, RecipeRevision
from .recipes_schemas import RecipeCreate, RecipeUpdate, RecipeExtractRequest, CommentCreate
from .timesheets_auth import get_current_user
from .timesheets_schemas import CurrentUser
from . import recipes_ai

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 Mo


def _serialize_recipe_summary(r: Recipe) -> dict:
    return {
        "id": r.id, "title": r.title, "image_url": r.image_url,
        "has_uploaded_image": r.image_data is not None,
        "prep_minutes": r.prep_minutes, "cook_minutes": r.cook_minutes,
        "servings": r.servings, "tags": r.tags,
    }


def _serialize_recipe_detail(r: Recipe, comments: list[RecipeComment]) -> dict:
    return {
        "id": r.id, "title": r.title, "ingredients": r.ingredients, "steps": r.steps,
        "prep_minutes": r.prep_minutes, "cook_minutes": r.cook_minutes,
        "servings": r.servings, "source_url": r.source_url, "image_url": r.image_url,
        "has_uploaded_image": r.image_data is not None,
        "tags": r.tags, "added_by_email": r.added_by_email,
        "comments": [
            {"id": c.id, "author_email": c.author_email, "author_name": c.author_name,
             "body": c.body, "created_at": c.created_at}
            for c in comments
        ],
    }


def _serialize_revision(rev: RecipeRevision) -> dict:
    return {
        "id": rev.id, "title": rev.title, "ingredients": rev.ingredients, "steps": rev.steps,
        "prep_minutes": rev.prep_minutes, "cook_minutes": rev.cook_minutes,
        "servings": rev.servings, "source_url": rev.source_url, "image_url": rev.image_url,
        "tags": rev.tags, "edited_by_email": rev.edited_by_email,
        "snapshotted_at": rev.snapshotted_at,
    }


def _get_recipe_or_404(session: Session, recipe_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if not recipe:
        raise HTTPException(404, "Recette introuvable")
    return recipe


@router.get("")
def list_recipes(
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipes = session.exec(select(Recipe).order_by(Recipe.title)).all()
    return [_serialize_recipe_summary(r) for r in recipes]


@router.post("")
def create_recipe(
    payload: RecipeCreate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    data = payload.model_dump()
    if data.get("ingredients"):
        lines = [l for l in data["ingredients"].split("\n") if l.strip()]
        data["ingredients"] = "\n".join(recipes_ai.normalize_units(lines))

    recipe = Recipe(**data, added_by_email=user.email)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return _serialize_recipe_detail(recipe, [])


@router.post("/extract")
def extract_recipe(
    payload: RecipeExtractRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Appelée à la fois par l'extension navigateur et par "Coller une
    recette" côté hub — extrait une recette structurée via Claude (unités
    déjà normalisées en métrique par le prompt d'extraction) et la
    sauvegarde directement (pas d'aperçu, décision produit)."""
    try:
        extracted = recipes_ai.extract_recipe(payload.content, payload.source_url, payload.title_hint)
    except recipes_ai.RecipeExtractionError as e:
        # 422 plutôt que 502/504 : Cloudflare intercepte ces codes "origine
        # injoignable" et les remplace par sa propre page d'erreur, ce qui
        # masquerait le vrai message envoyé par le backend.
        raise HTTPException(422, f"Extraction impossible : {e}")

    recipe = Recipe(
        title=extracted.title,
        ingredients="\n".join(extracted.ingredients),
        steps="\n".join(extracted.steps),
        prep_minutes=extracted.prep_minutes,
        cook_minutes=extracted.cook_minutes,
        servings=extracted.servings,
        source_url=payload.source_url,
        image_url=extracted.image_url,
        tags=", ".join(extracted.tags),
        added_by_email=user.email,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return _serialize_recipe_detail(recipe, [])


@router.get("/{recipe_id}")
def get_recipe(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    comments = session.exec(
        select(RecipeComment).where(RecipeComment.recipe_id == recipe_id).order_by(RecipeComment.created_at)
    ).all()
    return _serialize_recipe_detail(recipe, comments)


@router.get("/{recipe_id}/image")
def get_recipe_image(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    if not recipe.image_data:
        raise HTTPException(404, "Aucune image téléversée pour cette recette")
    return Response(content=recipe.image_data, media_type=recipe.image_content_type or "application/octet-stream")


@router.post("/{recipe_id}/image")
async def upload_recipe_image(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    file: UploadFile = File(...),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(422, "Le fichier doit être une image")

    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(422, f"Image trop volumineuse (max {MAX_IMAGE_SIZE // (1024 * 1024)} Mo)")

    recipe.image_data = data
    recipe.image_content_type = file.content_type
    recipe.updated_at = datetime.utcnow()
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    comments = session.exec(
        select(RecipeComment).where(RecipeComment.recipe_id == recipe_id).order_by(RecipeComment.created_at)
    ).all()
    return _serialize_recipe_detail(recipe, comments)


@router.delete("/{recipe_id}/image")
def delete_recipe_image(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    recipe.image_data = None
    recipe.image_content_type = None
    session.add(recipe)
    session.commit()
    return {"ok": True}


@router.get("/{recipe_id}/revisions")
def list_revisions(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _get_recipe_or_404(session, recipe_id)
    revisions = session.exec(
        select(RecipeRevision)
        .where(RecipeRevision.recipe_id == recipe_id)
        .order_by(RecipeRevision.snapshotted_at.desc())
    ).all()
    return [_serialize_revision(rev) for rev in revisions]


@router.patch("/{recipe_id}")
def update_recipe(
    recipe_id: int,
    payload: RecipeUpdate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    updates = payload.model_dump(exclude_unset=True)

    if updates:
        # Instantané de l'état actuel avant modification, pour pouvoir
        # consulter les versions précédentes (voir GET .../revisions).
        session.add(RecipeRevision(
            recipe_id=recipe.id, title=recipe.title, ingredients=recipe.ingredients,
            steps=recipe.steps, prep_minutes=recipe.prep_minutes, cook_minutes=recipe.cook_minutes,
            servings=recipe.servings, source_url=recipe.source_url, image_url=recipe.image_url,
            tags=recipe.tags, edited_by_email=user.email,
        ))

    if "ingredients" in updates and updates["ingredients"]:
        lines = [l for l in updates["ingredients"].split("\n") if l.strip()]
        updates["ingredients"] = "\n".join(recipes_ai.normalize_units(lines))

    for field, value in updates.items():
        setattr(recipe, field, value)
    recipe.updated_at = datetime.utcnow()
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    comments = session.exec(
        select(RecipeComment).where(RecipeComment.recipe_id == recipe_id).order_by(RecipeComment.created_at)
    ).all()
    return _serialize_recipe_detail(recipe, comments)


@router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    _: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    recipe = _get_recipe_or_404(session, recipe_id)
    for comment in session.exec(select(RecipeComment).where(RecipeComment.recipe_id == recipe_id)).all():
        session.delete(comment)
    for revision in session.exec(select(RecipeRevision).where(RecipeRevision.recipe_id == recipe_id)).all():
        session.delete(revision)
    session.delete(recipe)
    session.commit()
    return {"ok": True}


@router.post("/{recipe_id}/comments")
def add_comment(
    recipe_id: int,
    payload: CommentCreate,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _get_recipe_or_404(session, recipe_id)
    comment = RecipeComment(
        recipe_id=recipe_id,
        author_email=user.email,
        author_name=f"{user.first_name} {user.last_name}".strip() or user.email,
        body=payload.body,
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return {
        "id": comment.id, "author_email": comment.author_email,
        "author_name": comment.author_name, "body": comment.body,
        "created_at": comment.created_at,
    }


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    comment = session.get(RecipeComment, comment_id)
    if not comment:
        raise HTTPException(404, "Commentaire introuvable")
    if comment.author_email.lower() != user.email.lower() and not user.is_superuser:
        raise HTTPException(403, "Tu ne peux supprimer que tes propres commentaires")
    session.delete(comment)
    session.commit()
    return {"ok": True}
