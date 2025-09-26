# src/social_post/cli.py
import argparse, datetime, re
from dateutil.rrule import rrule, DAILY

from .io_utils import read_json, write_json, test_database_connection
from .constants import (
    ANLASS_FILE, QUOTES_FILE, USED_FILE,
    FEED_PATTERN, FEED_PATTERN_CLOSED, CAT_CYCLE,
    DRIVE_PARENT_FOLDER_ID, GOOGLE_DRIVE_SA_FILE
)
from .menu import load_menu, get_next_product, find_menu_examples_for_ingredient
from .notion_client import create_notion_entry
from .posts import generate_post_content, load_quotes, build_short_fact
from .ingredients.overrides import load_ingredients_overrides, save_ingredients_overrides
from .ingredients.auto import ensure_auto_ingredients
from .ingredients.merge import merge_auto_with_overrides
from .ingredients.enrich import enrich_overrides
from .schedule import compute_scheduled_datetime
from .carousel import generate_carousel_plan, build_placeholder_carousel
from .notion_schema import ensure_notion_schema

# ✅ optionaler, fehlertoleranter Import für Klassifizierung (z. B. Getränke)
try:
    from .ingredients.classify import load_meta, classify_name, allow_ingredient_post
    _HAS_CLASSIFY = True
except Exception:
    _HAS_CLASSIFY = False
    def load_meta(): return {}
    def classify_name(name, meta): return {"category": "food", "cookable": True, "allow_ingredient_post": True}
    def allow_ingredient_post(name, meta): return True

# ✅ Drive lazy import (damit --setup-notion-fields auch ohne Google-Libs läuft)
def _lazy_drive():
    if not (DRIVE_PARENT_FOLDER_ID and GOOGLE_DRIVE_SA_FILE):
        return None, None
    try:
        from .google_drive import get_drive_service, ensure_folder_path
        svc = get_drive_service()
        return svc, ensure_folder_path
    except Exception as e:
        print(f"⚠️ Drive deaktiviert: {e}")
        return None, None

def load_used():
    return read_json(USED_FILE, {"speisen": {}, "getränke": {}, "desserts": {}})

def save_used(data):
    write_json(USED_FILE, data)

def _to_str(x) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        # häufige Felder sinnvoll abbilden
        return x.get("name") or x.get("title") or x.get("author") or x.get("text") or ""
    if x is None:
        return ""
    return str(x)

def _slug(s: str) -> str:
    s = _to_str(s).lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s

def _build_placeholder_post(date, titel, beschreibung, post_type):
    title_in = _to_str(titel)
    desc_in  = _to_str(beschreibung)
    title = (title_in or (post_type.title() if isinstance(post_type, str) else "Post")).strip()[:120]
    text  = (desc_in or title).strip()[:300]
    return {
        "title": title or "Idee für den Tag",
        "text": text,
        "hashtags": "",
        "platform_suggestion": "Instagram Post",
        "media_type": "Bild",
        "image_idea": "",
        # Platzhalter — wird unten (nach evtl. Carousel-Plan) überschrieben
        "platform_targets": [
            {"name": "Instagram Post"},
            {"name": "Facebook"},
            {"name": "Google Business Profile"},
        ],
    }

# ✅ Hilfsfunktion: Plattform korrekt für Carousel/Nicht-Carousel setzen
def _platform_targets_for(has_carousel: bool, extra: list[str] | None = None):
    """
    Liefert eine Liste für Notion multi_select.
    has_carousel=True  → Instagram Carousel
    sonst              → Instagram Post
    Optional weitere Plattformen via extra=["Facebook", ...]
    """
    targets = [{"name": "Instagram Carousel"}] if has_carousel else [{"name": "Instagram Post"}]
    if extra:
        for x in extra:
            if x and isinstance(x, str):
                targets.append({"name": x})
    return targets

def _generate_with_fallback(date, gericht, beschreibung, post_type, extras=None):
    try:
        return generate_post_content(date, gericht, beschreibung, post_type, extras=extras)
    except TypeError:
        # falls posts.generate_post_content noch keine extras unterstützt
        return generate_post_content(date, gericht, beschreibung, post_type)

# ✅ Neu: nie zwei Tage hintereinander derselbe Posttyp
def pick_from_pool(pool, idx, prev_type):
    """
    Wählt aus pool einen Typ, der sich vom Vortag (prev_type) unterscheidet.
    Gibt (chosen_type, next_idx) zurück. idx ist der rotierende Zeiger.
    """
    if not pool:
        return None, idx
    n = len(pool)
    for step in range(n):
        pt = pool[(idx + step) % n]
        if pt != prev_type:
            return pt, idx + step + 1
    # Falls alle gleich (Pool-Länge 1 o.ä.)
    return pool[idx % n], idx + 1

def main():
    parser = argparse.ArgumentParser(
        prog="social_post",
        description="Planer für Social Posts (Notion + Zutaten-Workflow)"
    )
    # Startdatum nur in normalen Modi erforderlich
    parser.add_argument("--start", required=False, help="Startdatum YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=30, help="Anzahl Tage (Standard 30)")
    parser.add_argument("--dry-run", action="store_true", help="Nur erzeugen, nicht in Notion schreiben")
    parser.add_argument("--regen-auto-ingredients", action="store_true",
                        help="Auto-Zutaten aus Karte neu generieren (auch wenn Menü unverändert)")
    parser.add_argument("--export-auto-ingredients", action="store_true",
                        help="Nur Auto-Zutaten erzeugen/aktualisieren und dann beenden")
    parser.add_argument("--verbose", action="store_true", help="Mehr Fortschrittsausgaben")

    # Ingredient-Enrichment & Kontrolle
    parser.add_argument("--enrich-ingredients", action="store_true",
                        help="Approved Zutaten mit KI anreichern (nur zu kurze/fehlende 'fact'-Texte).")
    parser.add_argument("--enrich-only", action="store_true",
                        help="Nur Zutaten anreichern und beenden (keine Posts erzeugen).")
    parser.add_argument("--enrich-limit", type=int, default=8,
                        help="Max. Anzahl Zutaten für KI-Anreicherung in diesem Lauf (0 = unbegrenzt).")
    parser.add_argument("--skip-ai", action="store_true",
                        help="Keine OpenAI-Aufrufe (schneller Testlauf mit Platzhalter-Posts).")
    parser.add_argument("--write-enriched-overrides", action="store_true",
                        help="Angereicherte Texte dauerhaft in data/ingredients_overrides.json speichern.")

    # Carousel
    parser.add_argument("--carousel-ingredients", action="store_true",
                        help="Ingredient-Posts als Instagram-Karussell planen (Carousel-Plan enthält Slide-Plan).")
    parser.add_argument("--carousel-slides", type=int, default=6,
                        help="Anzahl Slides pro Ingredient-Karussell (z. B. 5–7).")

    # Notion-Felder automatisch anlegen/ergänzen
    parser.add_argument("--setup-notion-fields", action="store_true",
                        help="Fehlende Notion-Properties & Select-Optionen automatisch anlegen/ergänzen und beenden.")

    args = parser.parse_args()

    # Notion erreichbar?
    test_database_connection()

    # Optionaler Schema-Setup-Modus (früh raus)
    if args.setup_notion_fields:
        ensure_notion_schema(verbose=True)
        return

    # Startdatum nur in normalen Modi erforderlich
    if not args.start and not args.export_auto_ingredients and not args.enrich_only:
        parser.error("--start ist erforderlich (außer bei --setup-notion-fields, --export-auto-ingredients oder --enrich-only).")

    # Menü laden
    sp, gt, ds = load_menu()

    # Zutaten-Workflow (Auto & Overrides)
    overrides_by_name = load_ingredients_overrides()
    auto_payload = ensure_auto_ingredients(
        sp, gt, ds,
        force=args.regen_auto_ingredients,
        verbose=args.verbose
    )

    if args.export_auto_ingredients:
        print("📦 Auto-Zutaten exportiert (für Review): data/ingredients_auto.json")
        return

    approved_auto_names = [it["name"] for it in auto_payload.get("ingredients", []) if it.get("approved")]

    # (optional) Klassifizierung laden & filtern (z. B. Getränke nicht als Ingredient-Post)
    meta = load_meta()
    approved_auto_names = [n for n in approved_auto_names if allow_ingredient_post(n, meta)]

    # Menü-Beispiele je Zutat
    menu_examples_map = {}
    for nm in approved_auto_names:
        key = (nm or "").strip().lower()
        menu_examples_map[key] = find_menu_examples_for_ingredient(nm, sp, gt, ds)

    # Optional: KI-Anreicherung (RAM)
    if args.enrich_ingredients and not args.skip_ai:
        enrich_targets = approved_auto_names
        if args.enrich_limit and args.enrich_limit > 0:
            enrich_targets = enrich_targets[:args.enrich_limit]
        if args.verbose:
            print(f"🧠 Anreicherung starten: {len(enrich_targets)} Zutaten (Limit={args.enrich_limit})")
        overrides_by_name = enrich_overrides(
            enrich_targets, overrides_by_name, menu_examples_map, min_chars=100
        )
        if args.write_enriched_overrides:
            path = save_ingredients_overrides(overrides_by_name)
            print(f"💾 Overrides aktualisiert: {path}")
    elif args.enrich_ingredients and args.skip_ai and args.verbose:
        print("🧠 Anreicherung übersprungen (--skip-ai aktiv).")

    if args.enrich_only:
        print("🔎 Vorschau angereicherter Zutaten (Top 10 der Approved):")
        for nm in approved_auto_names[:10]:
            key = nm.strip().lower()
            ex = overrides_by_name.get(key)
            if ex:
                text = ex.get("fact", "") or ""
                print(f"- {ex['name']}: {text[:120]}{'…' if len(text) > 120 else ''}")
        return

    # Merge: Nur approved Auto-Zutaten + passende Overrides (die im Menü vorkommen)
    INGREDIENTS = merge_auto_with_overrides(approved_auto_names, overrides_by_name, max_items=60)

    QUOTES = load_quotes(read_json, QUOTES_FILE)
    anlass = read_json(ANLASS_FILE, {})
    used = load_used()

    start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d")
    end_exclusive = start_date + datetime.timedelta(days=args.days)

    # Drive vorbereiten (falls konfiguriert)
    drive_service, ensure_folder_path = _lazy_drive()

    i_open = i_closed = i_quotes = i_ingredients = 0
    # ⬇️ Neu: wir merken uns den Posttyp von gestern
    prev_post_type = None

    for dt in rrule(DAILY, dtstart=start_date, until=end_exclusive - datetime.timedelta(days=1)):
        weekday = dt.weekday()
        ruhetag = weekday in (1, 2)  # Di, Mi
        datum_str = dt.strftime("%Y-%m-%d")

        post_type = None
        gericht = ""
        beschreibung = ""
        extras = {}
        carousel_plan = None

        # Vorrang: Anlass
        if datum_str in anlass:
            post_type = "anlass"
            ev = anlass[datum_str]
            anlass_name = ""
            anlass_cat  = ""
            hashtags_override = ""
            image_idea_override = ""
            cta_override = ""

            if isinstance(ev, dict):
                anlass_name = (ev.get("beschreibung") or ev.get("titel") or "").strip()
                anlass_cat  = (ev.get("kategorie") or "").strip()
                hashtags_override = (ev.get("hashtags") or "").strip()
                image_idea_override = (ev.get("image_idea") or "").strip()
                cta_override = (ev.get("cta") or "").strip()
            else:
                anlass_name = str(ev).strip()

            gericht = anlass_name or "Besonderer Anlass"
            beschreibung = f"Heute ist ein besonderer Tag: {gericht}"
            extras = {
                **extras,
                "anlass_name": anlass_name,
                "anlass_cat": anlass_cat,
                "hashtags_override": hashtags_override,
                "image_idea_override": image_idea_override,
                "cta_override": cta_override,
            }

        # Ruhetage (kein Produkt)
        elif ruhetag:
            # ⬇️ statt stumpfer Rotation: wähle einen anderen Typ als gestern
            post_type, i_closed = pick_from_pool(FEED_PATTERN_CLOSED, i_closed, prev_post_type)
            if args.verbose:
                print(f"📅 {dt.date()} (Ruhetag) → {post_type}")

            if post_type == "zitat":
                quotes = QUOTES or [{"author": "Kaspio", "quote": "Gutes Essen. Guter Tag.", "source": "Hauszitat"}]
                q = quotes[i_quotes % len(quotes)]; i_quotes += 1
                gericht = q["author"]
                beschreibung = f'{q["quote"]} — {q["source"]}'
            else:  # ingredient_fact
                if INGREDIENTS:
                    ing = INGREDIENTS[i_ingredients % len(INGREDIENTS)]; i_ingredients += 1
                    gericht = ing["name"]
                    beschreibung = build_short_fact(ing, max_chars=420)
                    c = classify_name(gericht, meta)
                    ex = menu_examples_map.get(gericht.strip().lower()) or []
                    example = ex[0] if ex else ""
                    extras = {
                        "menu_example": example,
                        "category": c.get("category"),
                        "cookable": c.get("cookable", True),
                    }
                    if args.carousel_ingredients:
                        if args.skip_ai:
                            carousel_plan = build_placeholder_carousel(gericht, beschreibung, example, num_slides=args.carousel_slides)
                        else:
                            carousel_plan = generate_carousel_plan(gericht, beschreibung, example, num_slides=args.carousel_slides)
                else:
                    gericht = "Frische Zutat"
                    beschreibung = "Kurz & knackig zubereitet schmeckt’s am besten."

        # Normale (offene) Tage
        else:
            # ⬇️ statt stumpfer Rotation: wähle einen anderen Typ als gestern
            post_type, i_open = pick_from_pool(FEED_PATTERN, i_open, prev_post_type)
            if args.verbose:
                print(f"📅 {dt.date()} → {post_type}")

            if post_type == "produkt":
                cat_name = CAT_CYCLE[dt.day % 3]
                prod_dict = sp if cat_name == "speisen" else gt if cat_name == "getränke" else ds
                gericht = get_next_product(used, prod_dict, cat_name, dt)
                beschreibung = (prod_dict.get(gericht, "") or "").strip()

            elif post_type == "zitat":
                quotes = QUOTES or [{"author": "Kaspio", "quote": "Gutes Essen. Guter Tag.", "source": "Hauszitat"}]
                q = quotes[i_quotes % len(quotes)]; i_quotes += 1
                gericht = q["author"]
                beschreibung = f'{q["quote"]} — {q["source"]}'

            else:  # ingredient_fact
                if INGREDIENTS:
                    ing = INGREDIENTS[i_ingredients % len(INGREDIENTS)]; i_ingredients += 1
                    gericht = ing["name"]
                    beschreibung = build_short_fact(ing, max_chars=420)
                    c = classify_name(gericht, meta)
                    ex = menu_examples_map.get(gericht.strip().lower()) or []
                    example = ex[0] if ex else ""
                    extras = {
                        "menu_example": example,
                        "category": c.get("category"),
                        "cookable": c.get("cookable", True),
                    }
                    if args.carousel_ingredients:
                        if args.skip_ai:
                            carousel_plan = build_placeholder_carousel(gericht, beschreibung, example, num_slides=args.carousel_slides)
                        else:
                            carousel_plan = generate_carousel_plan(gericht, beschreibung, example, num_slides=args.carousel_slides)
                else:
                    gericht = "Frische Zutat"
                    beschreibung = "Kurz & knackig zubereitet schmeckt’s am besten."

        # --- String-Normalisierung (sicher gegen dict/None) ---
        gericht_str = _to_str(gericht)
        beschreibung_str = _to_str(beschreibung)

        # --- Inhalt erzeugen ---
        if args.skip_ai:
            obj = _build_placeholder_post(dt, gericht_str or (post_type.title() if isinstance(post_type, str) else "Post"), beschreibung_str, post_type)
        else:
            obj = _generate_with_fallback(dt, gericht_str, beschreibung_str, post_type, extras=extras)

        # Wenn wir ein Karussell haben: Plan dazu packen
        if carousel_plan:
            obj["platform_suggestion"] = "Instagram Carousel"
            obj["carousel_plan"] = carousel_plan  # wird in Notion als "Carousel-Plan" gespeichert

        # ⬇️ Plattform **immer** nach evtl. Carousel-Plan final setzen (überschreibt Placeholder)
        obj["platform_targets"] = _platform_targets_for(
            has_carousel=bool(carousel_plan),
            # Falls du weitere Plattformen mitpflegen willst, hier ergänzen:
            # extra=["Facebook", "Google Business Profile"]  # optional
            extra=None
        )

        # --- Zeit berechnen ---
        scheduled_dt = compute_scheduled_datetime(dt, post_type)

        # --- Drive-Ordner erzeugen (privat), Link & Name für Notion ---
        media_folder_name = ""
        media_link = ""
        if drive_service and ensure_folder_path:
            try:
                seg_month = dt.strftime("%Y-%m")
                leaf = f"{dt.strftime('%Y-%m-%d')}_{post_type}_{_slug(gericht_str)[:40] or 'post'}"
                folder_id, link = ensure_folder_path(drive_service, DRIVE_PARENT_FOLDER_ID, [seg_month, leaf])
                media_folder_name = f"{seg_month}/{leaf}"
                media_link = link
                if args.verbose:
                    print(f"📁 Drive-Ordner bereit: {media_folder_name} → {media_link}")
            except Exception as e:
                print(f"{dt.date()} ⚠️ Drive-Ordner konnte nicht erstellt werden: {e}")

        # --- Nach Notion (oder Dry-Run) ---
        try:
            create_notion_entry(
                dt, obj, post_type,
                dry_run=args.dry_run,
                scheduled_dt=scheduled_dt,
                media_folder_name=media_folder_name,
                media_link=media_link
            )
        except Exception as e:
            print(dt.date(), f"❌ Notion Fehler:", e)

        # ⬇️ Gestern merken, um doppelte Typen zu vermeiden
        prev_post_type = post_type

    write_json(USED_FILE, used)

if __name__ == "__main__":
    main()
