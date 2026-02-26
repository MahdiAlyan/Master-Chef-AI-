import json
import os
from typing import Any, Dict, List

import google.generativeai as genai


class GeminiServiceError(Exception):
    pass


_RESOLVED_MODEL_NAME: str | None = None


def _strip_model_prefix(name: str) -> str:
    return name.replace("models/", "", 1) if name.startswith("models/") else name


def _extract_json(text: str) -> Any:
    value = (text or "").strip()
    if not value:
        raise GeminiServiceError("Gemini returned an empty response")
    try:
        return json.loads(value)
    except Exception:
        pass

    # Handle fenced code blocks like ```json ... ```
    if "```" in value:
        for block in value.split("```"):
            candidate = block.replace("json", "", 1).strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except Exception:
                continue

    first_brace = value.find("{")
    first_bracket = value.find("[")
    starts = [x for x in [first_brace, first_bracket] if x != -1]
    if starts:
        start = min(starts)
        candidate = value[start:].strip()
        for end_char in ("}", "]"):
            end = candidate.rfind(end_char)
            if end != -1:
                snippet = candidate[: end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    continue

    raise GeminiServiceError("Gemini returned non-JSON response")


def _get_model():
    global _RESOLVED_MODEL_NAME

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise GeminiServiceError("GEMINI_API_KEY is not set")
    genai.configure(api_key=api_key)

    if _RESOLVED_MODEL_NAME:
        return genai.GenerativeModel(_RESOLVED_MODEL_NAME)

    preferred = [x.strip() for x in os.getenv("GEMINI_MODEL", "").split(",") if x.strip()]
    preferred.extend(
        [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro-latest",
        ]
    )

    try:
        listed = list(genai.list_models())
    except Exception as e:
        raise GeminiServiceError(
            f"Gemini model discovery failed: {e}. Set GEMINI_MODEL to a valid model name."
        ) from e

    available = []
    for model_info in listed:
        methods = getattr(model_info, "supported_generation_methods", []) or []
        if "generateContent" not in methods:
            continue
        model_name = _strip_model_prefix(getattr(model_info, "name", ""))
        if model_name:
            available.append(model_name)

    if not available:
        raise GeminiServiceError("No Gemini models with generateContent support were found for this API key.")

    chosen = None
    for candidate in preferred:
        normalized = _strip_model_prefix(candidate)
        if normalized in available:
            chosen = normalized
            break
        prefix_matches = [name for name in available if name.startswith(normalized)]
        if prefix_matches:
            chosen = prefix_matches[0]
            break

    if not chosen:
        flash = [name for name in available if "flash" in name]
        chosen = flash[0] if flash else available[0]

    _RESOLVED_MODEL_NAME = chosen
    return genai.GenerativeModel(_RESOLVED_MODEL_NAME)


def _generate_content_text(prompt: str) -> str:
    global _RESOLVED_MODEL_NAME

    model = _get_model()
    try:
        response = model.generate_content(prompt, request_options={"timeout": 20})
    except Exception as e:
        message = str(e)
        should_retry = "is not found" in message or "not supported for generateContent" in message
        if not should_retry:
            raise GeminiServiceError(f"Gemini request failed: {e}") from e

        _RESOLVED_MODEL_NAME = None
        try:
            model = _get_model()
            response = model.generate_content(prompt, request_options={"timeout": 20})
        except Exception as retry_error:
            raise GeminiServiceError(f"Gemini request failed: {retry_error}") from retry_error

    return getattr(response, "text", None) or ""


def generate_recipe(
    available_ingredients: str,
    cuisine_type: str = "",
    dietary_restriction: str = "",
    max_prep_time: int | None = None,
) -> Dict[str, Any]:
    prompt = (
        "You are a helpful chef assistant. Generate a recipe as STRICT JSON with keys: "
        "title (string), description (string), ingredients (array of strings), "
        "instructions (array of strings), prep_time_minutes (integer), servings (integer). "
        "Use the provided ingredients as much as possible. "
        f"Dietary restriction: {dietary_restriction or 'none'}. "
        f"Cuisine type preference: {cuisine_type or 'any'}. "
        f"Max prep time: {max_prep_time if max_prep_time else 'any'} minutes. "
        f"Available ingredients: {available_ingredients}."
    )

    data = _extract_json(_generate_content_text(prompt))

    if not isinstance(data, dict):
        raise GeminiServiceError("Gemini returned invalid JSON structure")

    title = data.get("title")
    ingredients = data.get("ingredients")
    instructions = data.get("instructions")

    if not isinstance(title, str) or not isinstance(ingredients, list) or not isinstance(instructions, list):
        raise GeminiServiceError("Gemini JSON missing required fields")

    prep_time = data.get("prep_time_minutes", 0)
    servings = data.get("servings", 2)
    description = str(data.get("description", "")).strip()

    try:
        prep_time = int(prep_time)
    except Exception:
        prep_time = 0
    try:
        servings = int(servings)
    except Exception:
        servings = 2

    return {
        "title": title.strip(),
        "description": description,
        "ingredients": [str(x).strip() for x in ingredients if str(x).strip()],
        "instructions": [str(x).strip() for x in instructions if str(x).strip()],
        "prep_time_minutes": max(prep_time, 0),
        "servings": max(servings, 1),
    }


def suggest_substitutions(ingredients_text: str) -> List[Dict[str, str]]:
    prompt = (
        "Given the following recipe ingredients, suggest substitutions. "
        "Return STRICT JSON as an array of objects with keys: ingredient, substitution, reason. "
        f"Ingredients: {ingredients_text}"
    )

    data = _extract_json(_generate_content_text(prompt))

    if not isinstance(data, list):
        raise GeminiServiceError("Gemini returned invalid substitutions structure")

    cleaned: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ing = str(item.get("ingredient", "")).strip()
        sub = str(item.get("substitution", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if ing and sub:
            cleaned.append({"ingredient": ing, "substitution": sub, "reason": reason})

    return cleaned


def estimate_nutrition(ingredients_text: str) -> Dict[str, Any]:
    prompt = (
        "Estimate nutrition for a whole recipe given ingredients. "
        "Return STRICT JSON with keys: calories (number), protein_g (number), carbs_g (number), fat_g (number), note (string). "
        f"Ingredients: {ingredients_text}"
    )

    data = _extract_json(_generate_content_text(prompt))

    if not isinstance(data, dict):
        raise GeminiServiceError("Gemini returned invalid nutrition structure")

    return data


def recommend_recipes(user_context: str, candidate_titles: List[str]) -> List[str]:
    prompt = (
        "You are a recommender for recipes. Pick up to 6 recipes to recommend based on user context. "
        "Return STRICT JSON as an array of strings (recipe titles). "
        f"User context: {user_context}. "
        f"Candidate recipes: {candidate_titles}"
    )

    data = _extract_json(_generate_content_text(prompt))

    if not isinstance(data, list):
        raise GeminiServiceError("Gemini returned invalid recommendations structure")

    return [str(x).strip() for x in data if str(x).strip()]


def generate_meal_plan(
    favorites: List[str],
    pantry_ingredients: List[str],
    days: int = 7,
    max_prep_time: int | None = None,
    dietary_restriction: str = "",
) -> List[Dict[str, str]]:
    prompt = (
        "Generate a weekly meal plan as STRICT JSON array of objects with keys: "
        "day, meal, reason. "
        f"Days: {days}. Max prep time: {max_prep_time if max_prep_time else 'any'} minutes. "
        f"Dietary restriction: {dietary_restriction or 'none'}. "
        f"Favorite recipes: {favorites}. Pantry ingredients: {pantry_ingredients}."
    )

    data = _extract_json(_generate_content_text(prompt))
    if not isinstance(data, list):
        raise GeminiServiceError("Gemini returned invalid meal plan structure")

    cleaned: List[Dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        day = str(item.get("day", "")).strip()
        meal = str(item.get("meal", "")).strip()
        reason = str(item.get("reason", "")).strip()
        if day and meal:
            cleaned.append({"day": day, "meal": meal, "reason": reason})
    return cleaned
