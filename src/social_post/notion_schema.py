# src/social_post/notion_schema.py
import os, json, requests
from typing import Dict, Any, List, Tuple

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
NOTION_VERSION = os.getenv("NOTION_VERSION", "2022-06-28")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

# 🔧 Gewünschtes Schema (korrekte Notion-Form)
# Schlüssel = Property-Name in der DB
SCHEMA_DEF: Dict[str, Dict[str, Any]] = {
    # Basis (Titel existiert idR. bereits – wir fügen nur, wenn wirklich fehlt)
    "Titel":               {"title": {}},
    "Text":                {"rich_text": {}},
    "Hashtags":            {"rich_text": {}},
    "AI-Vorschlag":        {"rich_text": {}},
    "Geplanter Zeitpunkt": {"date": {}},
    "Status":              {"select": {
        "options": [
            {"name": "Entwurf"}, {"name": "Bereit"}, {"name": "Geplant"},
            {"name": "Gepostet"}, {"name": "Fehlgeschlagen"}
        ]
    }},
    "Post-Typ":            {"select": {
        "options": [
            {"name": "produkt"}, {"name": "zitat"},
            {"name": "ingredient_fact"}, {"name": "anlass"}
        ]
    }},
    "Medientyp":           {"select": {
        "options": [{"name": "Bild"}, {"name": "Video"}, {"name": "Instagram Carousel"}]
    }},
    "Plattform":           {"multi_select": {
        "options": [
            {"name": "Instagram Post"}, {"name": "Instagram Reel"}, {"name": "Instagram Carousel"},
            {"name": "Facebook"}, {"name": "Facebook Video"}, {"name": "Google Business Profile"},
            {"name": "TikTok"}
        ]
    }},
    "Automatisch posten":  {"checkbox": {}},

    # Medien-Workflow
    "Media Folder":        {"rich_text": {}},
    "Media Link":          {"url": {}},
    "Primary Image FileId":{"rich_text": {}},
    "Carousel FileIds":    {"rich_text": {}},
    "Media Status":        {"select": {
        "options": [{"name": "todo"}, {"name": "ready"}, {"name": "posted"}, {"name": "failed"}]
    }},

    # Tracking
    "Posted At":           {"date": {}},
    "Post ID":             {"rich_text": {}},
    "Error":               {"rich_text": {}},
}

def _get_db() -> Dict[str, Any]:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def _patch_db(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        # Hilfreiches Debugging
        try:
            print("❌ Notion PATCH error:", r.status_code, r.text)
        except Exception:
            pass
        raise
    return r.json()

def _get_existing_props(db_json: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return db_json.get("properties", {}) or {}

def _missing_properties(existing: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    missing = {}
    for name, schema in SCHEMA_DEF.items():
        if name not in existing:
            missing[name] = schema
    return missing

def _select_key(prop_def: Dict[str, Any]) -> str | None:
    """Ermittelt 'select' oder 'multi_select' für eine Schema-Def, sonst None."""
    if "select" in prop_def: return "select"
    if "multi_select" in prop_def: return "multi_select"
    return None

def _missing_select_options(existing_prop: Dict[str, Any], desired_prop: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Für select/multi_select: finde Options, die fehlen.
    expected shape: existing_prop['select']['options'] / ['multi_select']['options']
    """
    key = _select_key(desired_prop)
    if not key:
        return []
    desired_opts = [o["name"] for o in desired_prop[key].get("options", [])]
    current_opts = [o["name"] for o in (existing_prop.get(key, {}) or {}).get("options", [])]
    return [{"name": n} for n in desired_opts if n not in current_opts]

def ensure_notion_schema(verbose: bool = True) -> Tuple[bool, bool]:
    """
    Legt fehlende Properties an und ergänzt fehlende Select/Multi-Select Optionen.
    Rückgabe: (props_added, options_added)
    """
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        raise RuntimeError("NOTION_TOKEN/NOTION_DATABASE_ID fehlen.")

    db = _get_db()
    existing = _get_existing_props(db)

    # 1) Fehlende Properties anlegen
    missing = _missing_properties(existing)
    props_added = False
    if missing:
        if verbose:
            print("🧩 Lege fehlende Properties an:", ", ".join(missing.keys()))
        _patch_db({"properties": missing})
        props_added = True
        # Aktualisierte DB laden
        db = _get_db()
        existing = _get_existing_props(db)

    # 2) Fehlende Select/Multi-Select-Optionen ergänzen
    to_add: Dict[str, Any] = {"properties": {}}
    for name, desired in SCHEMA_DEF.items():
        key = _select_key(desired)
        if not key: 
            continue
        if name in existing:
            missing_opts = _missing_select_options(existing[name], desired)
            if missing_opts:
                to_add["properties"][name] = {key: {"options": missing_opts}}

    options_added = False
    if to_add["properties"]:
        if verbose:
            ks = ", ".join([f"{k} (+{len(v[list(v.keys())[0]]['options'])} Optionen)"
                            for k, v in to_add["properties"].items()])
        # Patch senden
        _patch_db(to_add)
        options_added = True
        if verbose:
            print("🎛️ Fehlende Optionen ergänzt.", ks if 'ks' in locals() else "")

    if verbose and not props_added and not options_added:
        print("✅ Notion-DB ist bereits vollständig konfiguriert.")
    return props_added, options_added
