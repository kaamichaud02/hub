"""Extraction d'une recette structurée à partir du contenu brut d'une page
web (texte visible, ou JSON-LD schema.org/Recipe si l'extension l'a trouvé —
voir extension/content-extract.js) via l'API Claude.

Nécessite ANTHROPIC_API_KEY dans l'environnement. Voir le skill claude-api du
repo pour les conventions SDK (modèle par défaut claude-opus-5, sorties
structurées via client.messages.parse)."""
import anthropic

from .recipes_schemas import ExtractedRecipe

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


SYSTEM_PROMPT = (
    "Tu extrais une recette de cuisine structurée à partir du contenu brut "
    "d'une page web (texte visible de la page, ou un bloc JSON-LD "
    "schema.org/Recipe si présent — dans ce cas fie-toi en priorité à ce "
    "JSON-LD, il est plus fiable que le texte environnant). Ignore la "
    "navigation, les publicités, les commentaires de lecteurs et tout "
    "contenu qui n'est pas la recette elle-même. Les ingrédients et les "
    "étapes doivent être des listes d'éléments courts et clairs, un par "
    "ingrédient / une par étape. Les temps sont en minutes (convertis les "
    "heures si besoin). Si une information est absente, laisse le champ "
    "correspondant vide/null plutôt que d'inventer."
)


class RecipeExtractionError(Exception):
    pass


def extract_recipe(content: str, source_url: str | None, title_hint: str | None = None) -> ExtractedRecipe:
    user_text = ""
    if source_url:
        user_text += f"URL source : {source_url}\n"
    if title_hint:
        user_text += f"Titre de la page : {title_hint}\n"
    user_text += f"\nContenu :\n{content}"

    try:
        response = _get_client().messages.parse(
            model="claude-opus-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
            output_format=ExtractedRecipe,
        )
    except anthropic.APIError as e:
        raise RecipeExtractionError(str(e)) from e

    if response.parsed_output is None:
        raise RecipeExtractionError("Claude n'a pas réussi à extraire une recette de ce contenu")

    return response.parsed_output
