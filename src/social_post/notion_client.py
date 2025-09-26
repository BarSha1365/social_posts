# src/social_post/notion_client.py
import json
import datetime as _dt
import requests

from .constants import NOTION_DATABASE_ID, NOTION_TOKEN, NOTION_VERSION

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

# ----------------------------------------
# Hilfen
# ----------------------------------------
def _to_iso(dt: _dt.datetime | None) -> str | None:
    if not dt:
        return None
    # Notion akzeptiert naive ISO-Strings; falls tz-aware, isoformat mit offset
    try:
        return dt.isoformat(timespec="seconds")
    except Exception:
        return None

def _safe_text(x, limit=1900) -> str:
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    s = (s or "").strip()
    return s[:limit]

def _get_db_properties_map():
    """Liest die DB und gibt eine map lower(name)->Originalname zurück."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    props = data.get("properties", {}) or {}
    mp = {}
    for orig in props.keys():
        mp[orig.lower()] = orig
    return mp

_DB_PROPS = None

def _resolve(name_variants: list[str]) -> str | None:
    """Findet den vorhandenen Property-Namen in der DB, case-insensitiv über Synonyme."""
    global _DB_PROPS
    if _DB_PROPS is None:
        _DB_PROPS = _get_db_properties_map()
    for v in name_variants:
        nm = _DB_PROPS.get(v.lower())
        if nm:
            return nm
    return None

# ----------------------------------------
# Öffentliche Funktion
# ----------------------------------------
def create_notion_entry(
    date: _dt.datetime,
    obj: dict,
    post_type: str,
    dry_run: bool = False,
    scheduled_dt: _dt.datetime | None = None,
    media_folder_name: str | None = None,
    media_link: str | None = None,
):
    """
    Legt einen Eintrag in der Notion-Datenbank an.
    Unterstützt Media Folder/Link und geplanten Zeitpunkt.
    """
    global _DB_PROPS
    if _DB_PROPS is None:
        _DB_PROPS = _get_db_properties_map()

    # Property-Synonyme (so robust wie möglich)
    wants = {
        "title":        ["titel", "name"],
        "platform":     ["plattform"],
        "media_type":   ["medientyp"],
        "text":         ["text", "beschreibung"],
        "hashtags":     ["hashtags"],
        "datetime":     ["geplanter zeitpunkt", "datum", "zeitpunkt"],
        "status":       ["status"],
        "post_type":    ["post-typ", "post typ", "typ"],
        # NEU: nur den Carousel-Plan speichern (Legacy-Fallback auf frühere AI-Vorschlag-Spalte)
        "carousel_plan": ["carousel-plan", "carousel plan", "carousel_plan",
                          "AI-Vorschlag", "AI Vorschlag", "ai-vorschlag", "ai vorschlag", "ai"],
        # neue Felder:
        "auto":         ["automatisch posten", "auto posten", "autopost"],
        "media_folder": ["media folder", "ordner", "medienordner"],
        "media_link":   ["media link", "ordner link", "medienlink"],
        "primary_id":   ["primary image fileid", "primary file id", "primary fileid"],
        "carousel_ids": ["carousel fileids", "carousel files", "carousel ids"],
        "posted_at":    ["posted at", "veröffentlicht am"],
        "post_id":      ["post id"],
        "error":        ["error", "fehler"],
    }

    def R(key):
        return _resolve(wants[key])

    props = {}

    # Titel
    if (p := R("title")):
        props[p] = {"title": [{"type": "text", "text": {"content": obj.get("title") or "Post"}}]}

    # Plattform (multi_select): erwartet Liste wie [{"name": "..."}]
    if (p := R("platform")):
        targets = obj.get("platform_targets") or [{"name": "Instagram Post"}]
        props[p] = {"multi_select": targets}

    # Medientyp (select)
    if (p := R("media_type")):
        mt = obj.get("media_type") or "Bild"
        props[p] = {"select": {"name": mt}}

    # Text / Hashtags
    if (p := R("text")):
        props[p] = {"rich_text": [{"type": "text", "text": {"content": obj.get("text") or ""}}]}
    if (p := R("hashtags")):
        props[p] = {"rich_text": [{"type": "text", "text": {"content": obj.get("hashtags") or ""}}]}

    # Geplanter Zeitpunkt
    iso = _to_iso(scheduled_dt) or _to_iso(date.replace(hour=10, minute=0, second=0))
    if (p := R("datetime")) and iso:
        props[p] = {"date": {"start": iso}}

    # Status (select)
    if (p := R("status")):
        props[p] = {"select": {"name": "Entwurf"}}

    # Post-Typ (select)
    if (p := R("post_type")):
        props[p] = {"select": {"name": post_type}}

    # ----------------------------------------
    # Carousel-Plan (NEU): nur den Slide-Plan speichern, keine redundanten Felder
    # Erwartet obj["carousel_plan"] (z. B. {"slides":[...], "hashtags":"..."} )
    # ----------------------------------------
    if (p := R("carousel_plan")):
        payload = {}
        if isinstance(obj, dict) and obj.get("carousel_plan"):
            payload = {"carousel_plan": obj["carousel_plan"]}
        # Falls kein Carousel vorhanden ist, leer schreiben (oder Feld ganz weglassen)
        props[p] = {
            "rich_text": [
                {"type": "text", "text": {"content": _safe_text(payload, 1900)}}
            ]
        }

    # Automatisch posten (checkbox) – default False
    if (p := R("auto")):
        props[p] = {"checkbox": False}

    # Media Folder (rich_text) & Media Link (url)
    if media_folder_name and (p := R("media_folder")):
        props[p] = {"rich_text": [{"type": "text", "text": {"content": str(media_folder_name)}}]}
    if media_link and (p := R("media_link")):
        props[p] = {"url": str(media_link)}

    payload = {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": props}

    if dry_run:
        # Für Debug-Ausgaben in CLI
        keys = ", ".join(props.keys())
        print(date.date(), "📝 DRY-RUN (Properties):", keys)
        if media_folder_name or media_link:
            print("   ↳ Media:", media_folder_name or "-", "|", media_link or "-")
        # Zeig optional, was in Carousel-Plan landen würde:
        cp_prop = R("carousel_plan")
        if cp_prop and cp_prop in props:
            try:
                preview = props[cp_prop]["rich_text"][0]["text"]["content"]
                print("   ↳ Carousel-Plan Preview:", preview[:180], "…")
            except Exception:
                pass
        return

    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Notion create page failed {r.status_code}: {r.text}")
    print(date.date(), "✅ erstellt:", r.json().get("id"))
