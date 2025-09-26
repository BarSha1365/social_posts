# src/social_post/constants.py
from pathlib import Path
import os
from dotenv import load_dotenv

# ---- ENV laden ----
load_dotenv()

# ---- Pfade (robust relativ zum Repo-Root) ----
# Datei liegt unter src/social_post/constants.py -> Repo-Root ist 2 Ebenen höher
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR     = PROJECT_ROOT / "data"

# Fallback, falls jemand das Paket anders verpackt
if not DATA_DIR.exists():
    DATA_DIR = Path("data")

# ---- Notion ----
NOTION_TOKEN       = os.getenv("NOTION_TOKEN", "").strip()
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "").strip()
NOTION_VERSION     = os.getenv("NOTION_VERSION", "2022-06-28").strip()

# ---- Scheduling / Region ----
POST_TIME_HOUR = int(os.getenv("POST_TIME_HOUR", "10"))
REGION_TZ      = os.getenv("REGION_TZ", "Europe/Berlin").strip()

# ---- Google Drive / Media ----
DRIVE_PARENT_FOLDER_ID = os.getenv("DRIVE_PARENT_FOLDER_ID", "").strip()
GOOGLE_DRIVE_SA_FILE   = os.getenv("GOOGLE_DRIVE_SA_FILE", "").strip()
DRIVE_MAKE_PUBLIC      = os.getenv("DRIVE_MAKE_PUBLIC", "false").strip().lower() == "true"

# ---- Dateien ----
MENU_FILE         = DATA_DIR / "menu.json"
ANLASS_FILE       = DATA_DIR / "anlass_kalender.json"
QUOTES_FILE       = DATA_DIR / "quotes.json"
USED_FILE         = PROJECT_ROOT / "used_products.json"

# Zutaten-Dateien
ING_OVERRIDES_FILE = DATA_DIR / "ingredients_overrides.json"   # bevorzugter Name
ING_AUTO_FILE      = DATA_DIR / "ingredients_auto.json"
ING_META_FILE      = DATA_DIR / "ingredients_meta.json"

# Backwards-Compat (ältere Module nutzten teilweise diese Namen)
ING_OVERRIDES = ING_OVERRIDES_FILE

# ---- Feed-Logik ----
FEED_PATTERN         = ["produkt", "zitat", "ingredient_fact"]   # kein "anlass" in der Rotation
FEED_PATTERN_CLOSED  = ["zitat", "ingredient_fact"]              # Ruhetage
CAT_CYCLE            = ["speisen", "getränke", "desserts"]

# ---- Zutaten-Extraktion (Heuristiken) ----
STOPWORDS = {
    "mit","und","oder","auch","optional","kleines","kleiner","kleine",
    "in","auf","der","die","das","den","dem","des","einem","einer","eines",
    "hausdressing","sauce","soße","dressing","dip","style","scharf","wir","ist"
}
NON_INGREDIENTS = {
    "salat","salatmix","pommes","reis","pasta","tagliatelle","penne",
    "wrap","tortilla","quiche","bowl","brot","croutons","kuchen","eis","wein"
}
REPLACEMENTS = {
    "rote": "rote bete",
    "bete": "rote bete",
    "spinat": "babyspinat",
    "rahm": "joghurt-sahne",
    "hahnchen": "hähnchen",
    "sojabohnen": "edamame",
    "senf": "senf-dill"
}
