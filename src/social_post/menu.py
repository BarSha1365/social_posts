from .io_utils import read_json
from .constants import MENU_FILE

def load_menu():
    menu = read_json(MENU_FILE)
    if not menu:
        raise SystemExit(f"Fehlende Karte: {MENU_FILE}. Bitte data/menu.json befüllen.")
    sp = menu.get("speisen") or {}
    gt = menu.get("getränke") or menu.get("getraenke") or {}
    ds = menu.get("desserts") or {}

    def to_dict(x):
        if isinstance(x, dict): return x
        if isinstance(x, list):
            out = {}
            for item in x:
                if isinstance(item, dict) and "name" in item:
                    out[item["name"]] = item.get("beschreibung","")
            return out
        return {}
    sp, gt, ds = to_dict(sp), to_dict(gt), to_dict(ds)
    if not (sp or gt or ds):
        raise SystemExit("menu.json gefunden, aber leer/ohne gültige Struktur.")
    return sp, gt, ds

def get_next_product(used_dict, category_dict, cat_name, current_date):
    unused = [p for p in category_dict if p not in used_dict[cat_name]]
    if unused:
        selected = sorted(unused)[0]
    else:
        sorted_used = sorted(used_dict[cat_name].items(), key=lambda x: x[1])
        selected = sorted_used[0][0]
    used_dict[cat_name][selected] = current_date.strftime("%Y-%m-%d")
    return selected
def find_menu_examples_for_ingredient(name: str, sp: dict, gt: dict, ds: dict, max_examples=2):
    """Sucht Beispiel-Gerichte, deren Beschreibung die Zutat erwähnt."""
    out = []
    needle = (name or "").strip().lower()
    if not needle:
        return out
    for cat in (sp, gt, ds):
        for dish, descr in (cat or {}).items():
            if needle in (descr or "").lower():
                out.append(dish)
                if len(out) >= max_examples:
                    return out
    return out
