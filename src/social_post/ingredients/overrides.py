# src/social_post/ingredients/overrides.py
from ..io_utils import read_json, write_json
from ..constants import ING_OVERRIDES

def load_ingredients_overrides():
    data = read_json(ING_OVERRIDES, {"ingredients": []})
    by_name = {}
    for it in data.get("ingredients", []):
        name = (it.get("name") or "").strip()
        fact = (it.get("fact") or "").strip()
        if name:
            by_name[name.lower()] = {"name": name, "fact": fact}
    return by_name

def save_ingredients_overrides(overrides_by_name: dict) -> str:
    """Speichert das Dict dauerhaft nach data/ingredients_overrides.json."""
    items = []
    for key, obj in overrides_by_name.items():
        name = (obj.get("name") or key).strip()
        fact = (obj.get("fact") or "").strip()
        if not name:
            continue
        items.append({"name": name, "fact": fact})
    items.sort(key=lambda x: x["name"].lower())
    write_json(ING_OVERRIDES, {"ingredients": items})
    return str(ING_OVERRIDES)
