"""Extraction d'une recette structurée à partir du contenu brut d'une page
web (texte visible, ou JSON-LD schema.org/Recipe si l'extension l'a trouvé —
voir extension/background.js) via l'API Claude. Contient aussi la conversion
impérial -> métrique des ingrédients saisis manuellement.

Nécessite ANTHROPIC_API_KEY dans l'environnement. Voir le skill claude-api du
repo pour les conventions SDK (modèle par défaut claude-opus-5, sorties
structurées via client.messages.parse)."""
import anthropic

from .recipes_schemas import ExtractedRecipe, NormalizedIngredients

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class RecipeExtractionError(Exception):
    pass


UNITS_INSTRUCTION = (
    "Pour chaque ingrédient exprimé en unité impériale (cups/tasses, tsp, "
    "tbsp, oz, lb, °F, pouces, ...), convertis-le en unité métrique (ml, g, "
    "kg, °C, cm) comme valeur principale, et garde la valeur impériale "
    "d'origine entre parenthèses à la fin — ex. \"250 g de farine (2 cups)\", "
    "\"180°C (350°F)\". Les conversions poids/volume pour les ingrédients "
    "secs sont approximatives (dépendent de la densité) — utilise les "
    "équivalences courantes en cuisine, une approximation raisonnable "
    "suffit. Un ingrédient déjà en métrique, ou sans unité de mesure (ex. "
    "\"1 oignon\", \"sel au goût\"), reste inchangé."
)

SYSTEM_PROMPT = (
    "Tu extrais une recette de cuisine structurée à partir du contenu brut "
    "d'une page web (texte visible de la page, ou un bloc JSON-LD "
    "schema.org/Recipe si présent — dans ce cas fie-toi en priorité à ce "
    "JSON-LD, il est plus fiable que le texte environnant). Ignore la "
    "navigation, les publicités, les commentaires de lecteurs et tout "
    "contenu qui n'est pas la recette elle-même. Les ingrédients et les "
    "étapes doivent être des listes d'éléments courts et clairs, un par "
    "ingrédient / une par étape. Les temps sont en minutes (convertis les "
    "heures si besoin). Propose aussi 1 à 5 tags courts pertinents (type de "
    "plat, cuisine, régime alimentaire — ex. \"dessert\", \"végétarien\", "
    "\"italien\"). Si une information est absente, laisse le champ "
    "correspondant vide/null plutôt que d'inventer.\n\n" + UNITS_INSTRUCTION
)

NORMALIZE_SYSTEM_PROMPT = (
    "On te donne une liste d'ingrédients de recette, un par ligne, saisis "
    "manuellement. Renvoie exactement la même liste, dans le même ordre, "
    "sans rien ajouter ni retirer, en appliquant uniquement la règle "
    "suivante :\n\n" + UNITS_INSTRUCTION
)


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


def normalize_units(ingredient_lines: list[str]) -> list[str]:
    """Convertit les unités impériales en métrique (impérial gardé entre
    parenthèses) dans une liste d'ingrédients saisis manuellement. Renvoie la
    liste telle quelle si vide, ou si l'appel Claude échoue (on ne bloque pas
    la sauvegarde d'une recette pour un souci de conversion cosmétique)."""
    if not ingredient_lines:
        return ingredient_lines

    try:
        response = _get_client().messages.parse(
            model="claude-opus-5",
            max_tokens=2048,
            system=NORMALIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(ingredient_lines)}],
            output_format=NormalizedIngredients,
        )
    except anthropic.APIError:
        return ingredient_lines

    if response.parsed_output is None or len(response.parsed_output.ingredients) != len(ingredient_lines):
        return ingredient_lines

    return response.parsed_output.ingredients
