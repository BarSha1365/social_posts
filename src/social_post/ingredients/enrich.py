# src/social_post/ingredients/enrich.py
import re, time
from ..openai_client import call_openai

def is_too_short(text, min_chars=100):
    return not isinstance(text, str) or len(text.strip()) < min_chars

ING_ENRICH_SYS = (
    "Du bist Ernährungsredakteur:in. Schreibe faktenbasiert, präzise, deutsch, werbefrei. "
    "Keine Heilversprechen, keine Markennamen."
)

def build_ingredient_prompt(name: str, menu_examples: list[str] | None = None) -> str:
    ctx = ""
    if menu_examples:
        ctx = "\nBeispiel aus unserer Karte: " + "; ".join(menu_examples[:2])
    return (
        f"Zutat: {name}\n"
        "Schreibe 90–130 Wörter über Geschmack, typische Verwendung in der Küche, "
        "nährwertebezogene Hinweise (ohne Heilsversprechen) und ggf. Verträglichkeit/Allergiehinweise. "
        "Klar, sachlich, ohne Marketing. Keine Listen, nur Fließtext." + ctx
    )

def enrich_ingredient_with_ai(name: str, menu_examples=None) -> str:
    content = call_openai(
        [{"role": "system", "content": ING_ENRICH_SYS},
         {"role": "user", "content": build_ingredient_prompt(name, menu_examples)}],
        retries=3, backoff=2.0, temperature=0.5
    )
    txt = (content or "").strip()
    # Markdown/JSON-Klammern grob entfernen
    txt = re.sub(r"^[`>{\[]+|[`}\]]+$", "", txt).strip()
    return txt

def enrich_overrides(approved_names: list[str], overrides_by_name: dict, menu_examples_map: dict[str, list[str]], min_chars=100):
    """
    Ergänzt/verbessert 'fact' in overrides_by_name für approved Zutaten.
    Schreibt NICHT auf disk – Rückgabe ist das aktualisierte Dict.
    """
    for nm in approved_names:
        key = (nm or "").strip().lower()
        ex = overrides_by_name.get(key, {"name": nm, "fact": ""})
        fact = ex.get("fact", "")
        if is_too_short(fact, min_chars=min_chars):
            try:
                enriched = enrich_ingredient_with_ai(ex.get("name") or nm, menu_examples_map.get(key, []))
                if not is_too_short(enriched, min_chars=60):
                    ex["fact"] = enriched
                    overrides_by_name[key] = {"name": ex["name"], "fact": ex["fact"]}
            except Exception:
                # still keep old fact
                pass
    return overrides_by_name
