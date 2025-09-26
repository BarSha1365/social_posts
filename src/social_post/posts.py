import re, json
from .openai_client import call_openai

SYSTEM = (
    "Du erstellst Social-Media-Posts für ein Restaurant. "
    'Gib ausschließlich valides JSON zurück mit genau diesen Feldern: '
    '{ "title": "", "text": "", "hashtags": "", "platform_suggestion": "", "media_type": "Bild|Video", "image_idea": "" } '
    "Ohne Erklärtext, kein Markdown."
)

# -----------------------------
# Helpers
# -----------------------------
def _to_str(x) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        return x.get("name") or x.get("title") or x.get("author") or x.get("text") or ""
    if x is None:
        return ""
    return str(x)

def parse_json_or_fallback(s: str):
    s = (s or "").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {"title": "", "text": "", "hashtags": "", "platform_suggestion": "", "media_type": "", "image_idea": ""}

def get_cross_platform_targets(suggestion):
    v = (suggestion or "").lower()
    if "carousel" in v:
        return [{"name": "Instagram Carousel"}]
    if "reel" in v or "video" in v:
        return [{"name": "Instagram Reel"}, {"name": "TikTok"}, {"name": "Facebook Video"}]
    if "feed" in v or "post" in v:
        return [{"name": "Instagram Post"}, {"name": "Facebook"}, {"name": "Google Business Profile"}]
    return [{"name": "Instagram Post"}]

def _sanitize_post_obj(obj: dict) -> dict:
    """Trim, Standardwerte, Typ-Robustheit."""
    out = dict(obj or {})
    out["title"] = (_to_str(out.get("title"))).strip()[:120] or "Idee für den Tag"
    out["text"] = (_to_str(out.get("text"))).strip()[:300]
    out["hashtags"] = (_to_str(out.get("hashtags"))).strip()[:300]
    out["platform_suggestion"] = (_to_str(out.get("platform_suggestion")) or "Instagram Post").strip()
    mt = (_to_str(out.get("media_type")) or "Bild").strip().lower()
    out["media_type"] = "Video" if "video" in mt else "Bild"
    out["image_idea"] = (_to_str(out.get("image_idea"))).strip()[:300]
    out["platform_targets"] = get_cross_platform_targets(out["platform_suggestion"])
    return out



def _apply_anlass_overrides(obj: dict, extras: dict | None) -> dict:
    """Bei Anlass: optionale Overrides (Hashtags/Bildidee/CTA) anwenden und Titel sinnvoll setzen."""
    out = dict(obj or {})
    extras = extras or {}

    anlass_name = _to_str(extras.get("anlass_name")).strip()
    if anlass_name:
        # Titel sollte den Anlass enthalten
        if anlass_name.lower() not in (out.get("title", "").lower()):
            out["title"] = (f"{anlass_name} – Kaspio")[:120]

        # Hashtags-Override
        ov_hash = _to_str(extras.get("hashtags_override")).strip()
        if ov_hash:
            out["hashtags"] = ov_hash[:300]

        # Bildidee-Override
        ov_img = _to_str(extras.get("image_idea_override")).strip()
        if ov_img and not _to_str(out.get("image_idea")).strip():
            out["image_idea"] = ov_img[:300]

        # Optionaler CTA, wenn Platz
        cta = _to_str(extras.get("cta_override")).strip()
        if cta:
            base = _to_str(out.get("text")).strip()
            out["text"] = (f"{base} {cta}".strip() if base else cta)[:300]

    return out

def _has_cooking_claims(text: str) -> bool:
    """Erkennt typische Koch-/Zutat-Behauptungen (deutsch)."""
    if not text:
        return False
    pattern = r"\b(koch\w*|brat\w*|back\w*|rezept\w*|gericht\w*|zutat\w*|zubereit\w*)\b"
    return re.search(pattern, text.lower()) is not None

# -----------------------------
# Prompt Builder (mit extras)
# -----------------------------
def build_prompt(date, gericht, beschreibung, post_type, extras=None):
    d_str = date.strftime("%d.%m.%Y")
    extras = extras or {}
    cat = (_to_str(extras.get("category")) or "").lower()
    cookable = bool(extras.get("cookable", True))
    menu_example = _to_str(extras.get("menu_example"))

    if post_type == "anlass":
        anlass_name = (_to_str(extras.get("anlass_name")) or _to_str(gericht) or "").strip()
        return (
            "Du erstellst einen Social-Media-Post für Restaurant Kaspio (Stade). "
            f"ANLASS (muss wörtlich vorkommen): \"{anlass_name}\" am {d_str}. "
            "Schreibe einen kompakten, freundlichen Text (max 300 Zeichen), der GENAU diesen Anlass erwähnt, "
            "mit 1 Satz Kontext und 1 kurzen Call-to-Action. Keine generischen Saison-Texte."
        )
    if post_type == "zitat":
        return (
            f"Erstelle einen Social-Media-Post ({d_str}) für Restaurant Kaspio mit diesem leichten, fröhlichen Zitat. "
            f"Nenne das Zitat im Text, max. 300 Zeichen.\n\n{beschreibung}"
        )

    if post_type == "ingredient_fact":
        # 🥤 Beverage / nicht kochbar → kein Kochen suggerieren
        if cat == "beverage" or not cookable:
            hint = " (Optionaler Kontext: " + menu_example + ")" if menu_example else ""
            return (
                f"Erstelle einen kurzen Post ({d_str}) über das Getränk/den Likör '{gericht}'. "
                f"Nutze diesen Hinweistext: {beschreibung}{hint}. "
                "Fokussiere auf Geschmack, Servierempfehlung und Anlass (z. B. Aperitivo). "
                "Keine Aussagen, dass man damit kocht oder Gerichte zubereitet. "
                "Keine Heilsversprechen. Max 300 Zeichen, freundlich-informativ, 1–2 Sätze."
            )
        # Standard-Zutat (kochbar)
        return (
            f"Erstelle einen kurzen Post ({d_str}) mit einem sympathischen Fact zur Zutat '{gericht}': {beschreibung}. "
            "Max 300 Zeichen, freundlich-informativ, 1–2 Sätze."
        )

    # produkt
    return (
        f"Erstelle einen Instagram-Post für {d_str}. Produkt: {gericht}. "
        f"Beschreibung: {beschreibung or ''}. Max 300 Zeichen im Feld 'text'."
    )

# -----------------------------
# Hauptfunktion
# -----------------------------
def generate_post_content(date, gericht, beschreibung, post_type, extras=None):
    content = call_openai(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(date, gericht, beschreibung, post_type, extras=extras)},
        ],
        temperature=0.8,
    )
    obj = parse_json_or_fallback(content)
    obj = _sanitize_post_obj(obj)

    
    if post_type == "anlass":
        obj = _apply_anlass_overrides(obj, extras or {})
# 🚧 Guardrails für Getränke / nicht kochbar
    cat = (_to_str((extras or {}).get("category")) or "").lower()
    cookable = bool((extras or {}).get("cookable", True))
    if cat == "beverage" or not cookable:
        if _has_cooking_claims(obj.get("text", "")):
            # Fallback: nutze den gegebenen beschreibungstext als sicheren, kompakten Post
            safe = build_short_fact({"fact": _to_str(beschreibung)}, max_chars=280)
            obj["text"] = safe
        if not obj.get("image_idea"):
            obj["image_idea"] = (
                f"Close-up von '{gericht}' im Glas mit Eis und Orangenscheibe; "
                "Aperitivo-Stimmung (Terrasse, golden hour), dezenter Bokeh."
            )
        # Wenn Suggestion unpassend, auf Post setzen (kein Reel nötig)
        if obj.get("platform_suggestion", "").lower() in ("instagram reel", "tiktok"):
            obj["platform_suggestion"] = "Instagram Post"
            obj["platform_targets"] = get_cross_platform_targets(obj["platform_suggestion"])

    return obj

# -----------------------------
# Zitate & Facts
# -----------------------------
def load_quotes(read_json, QUOTES_FILE):
    data = read_json(QUOTES_FILE, [])
    out = []
    for q in data or []:
        author = (q.get("author") or "").strip()
        quote = (q.get("quote") or "").strip()
        source = (q.get("source") or "").strip() or "Hauszitat"
        if author and quote:
            out.append({"author": author, "quote": quote, "source": source})
    return out

def build_short_fact(item: dict, max_chars=420):
    txt = (_to_str(item.get("fact")) or "Frische Zutat – aromatisch und vielseitig in der Küche einsetzbar.").strip()
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:max_chars] + "…") if len(txt) > max_chars else txt
