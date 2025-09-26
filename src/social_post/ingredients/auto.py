import hashlib, re
from collections import Counter
from datetime import datetime
from ..io_utils import read_json, write_json
from ..constants import STOPWORDS, NON_INGREDIENTS, REPLACEMENTS, ING_AUTO_FILE

def _norm_ing(nm: str) -> str:
    nm = (nm or "").strip().lower()
    synonyms = {"alioli": "aioli", "allioli": "aioli"}
    nm = synonyms.get(nm, nm)
    nm = REPLACEMENTS.get(nm, nm)
    return nm

def compute_menu_signature(sp: dict, gt: dict, ds: dict) -> str:
    base = {"speisen": sp, "getränke": gt, "desserts": ds}
    blob = re.sub(r"\s+", " ", str(sorted(base.items())))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

def extract_ingredients_with_counts(sp: dict, gt: dict, ds: dict):
    tokens = []
    for menu in (sp, gt, ds):
        for descr in (menu or {}).values():
            if not descr: continue
            parts = re.split(r"[,\u2022;/]| und | mit ", (descr or "").lower())
            for p in parts:
                t = re.sub(r"[^a-zäöüß\- ]", "", p).strip()
                t = re.sub(r"\s+", " ", t)
                if not t: continue
                for w in t.split():
                    if len(w) < 3: continue
                    if w in STOPWORDS: continue
                    w2 = _norm_ing(w)
                    if w2 in NON_INGREDIENTS: continue
                    tokens.append(w2)
    counts = Counter(tokens)
    items = []
    for w, c in counts.most_common():
        name = w[:1].upper() + w[1:]
        items.append({"name": name, "count": int(c), "approved": False, "note": ""})
    return items

def load_auto_ingredients():
    return read_json(ING_AUTO_FILE, {"menu_signature":"", "generated_at":"", "ingredients":[]})

def save_auto_ingredients(payload: dict):
    write_json(ING_AUTO_FILE, payload)

def ensure_auto_ingredients(sp: dict, gt: dict, ds: dict, *, force=False, verbose=False) -> dict:
    sig = compute_menu_signature(sp, gt, ds)
    existing = load_auto_ingredients()
    if not force and existing.get("menu_signature") == sig and existing.get("ingredients"):
        if verbose: print("📄 Menü unverändert – verwende vorhandene auto-Zutaten.", flush=True)
        return existing

    new_items = extract_ingredients_with_counts(sp, gt, ds)
    prev = { (it.get("name") or "").strip().lower(): it for it in existing.get("ingredients", []) }
    for it in new_items:
        key = (it["name"] or "").strip().lower()
        if key in prev:
            it["approved"] = bool(prev[key].get("approved", False))
            it["note"] = prev[key].get("note", "")

    payload = {"menu_signature": sig, "generated_at": datetime.now().strftime("%Y-%m-%d"), "ingredients": new_items}
    save_auto_ingredients(payload)
    if verbose: print(f"📝 Auto-Zutaten aktualisiert: {ING_AUTO_FILE}", flush=True)
    return payload