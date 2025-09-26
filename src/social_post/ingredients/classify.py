import json, re
from pathlib import Path

META_FILE = Path("data/ingredients_meta.json")

ALCOHOL_HINTS = [
    r"\baperol\b", r"\bcampari\b", r"\bprosecco\b", r"\bgin\b", r"\brum\b",
    r"\bvodka\b", r"\bwhisky\b", r"\bvermut[h]?\b", r"\bliqueur\b", r"\blikör\b",
    r"\bwein\b", r"\bsekt\b", r"\bchampagner\b", r"\bgrappa\b"
]

def load_meta():
    if META_FILE.exists():
        with META_FILE.open("r", encoding="utf-8") as f:
            obj = json.load(f) or {}
        d = {}
        for it in obj.get("meta", []):
            nm = (it.get("name") or "").strip().lower()
            if nm:
                d[nm] = {
                    "category": it.get("category") or "",
                    "cookable": bool(it.get("cookable", True)),
                    "allow_ingredient_post": bool(it.get("allow_ingredient_post", True)),
                }
        return d
    return {}

def classify_name(name: str, meta: dict):
    key = (name or "").strip().lower()
    if key in meta:
        return meta[key]
    # Heuristik: Alkohol?
    if any(re.search(p, key) for p in ALCOHOL_HINTS):
        return {"category": "beverage", "cookable": False, "allow_ingredient_post": True}
    # Default: essbar/kochbar
    return {"category": "food", "cookable": True, "allow_ingredient_post": True}

def is_cookable(name: str, meta: dict) -> bool:
    return bool(classify_name(name, meta).get("cookable", True))

def is_beverage(name: str, meta: dict) -> bool:
    return (classify_name(name, meta).get("category") == "beverage")

def allow_ingredient_post(name: str, meta: dict) -> bool:
    return bool(classify_name(name, meta).get("allow_ingredient_post", True))
