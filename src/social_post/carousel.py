# src/social_post/carousel.py
import json, re
from .openai_client import call_openai

CAROUSEL_SYS = (
    "Du bist Social-Media-Redakteur:in. Erstelle faktenbasierte, knappe IG-Karussell-Texte in Deutsch. "
    "Kein Markdown, keine Emojis, keine Listen-Formatierung mit '-' oder '*'. "
    "Stilvorgaben für die Bildserien: "
    "— Slide 1 IMMER im Serien-Stil:\n"
    "   • Lose Zutaten (z. B. Safran, Blaubeeren, Berberitzen) = fotorealistisch in einer rustikalen Holz-/Keramikschale.\n"
    "   • Flüssige/Flaschenprodukte (z. B. Aperol, Öl, Wein) = realistische Flasche.\n"
    "   • Hintergrund: beige #f3d68d  #f2deaa für Hintergrundschattierungenmit dunkelgrüner #14452f Line-Art + optional Schwarz (#000000) für Konturen.\n"
    "   • Immer mit kulturell passenden Ornamenten: Safran/Berberitzen = persische Muster, "
    "Aperol = italienische Architektur/Landschaft, Blaubeeren = Wald/Strauch.\n"
    "   • Quadratisch 1024x1024, weiches Studiolicht, dezente Tiefenschärfe.\n"
    "— Ab Slide 2: Infografiken/Rezepte/Nährwerte/Tipps – Flat-Design, Farben #14452f/#000000 auf #f3d68d.\n"
    "— Typografie: klare Sans-Serif, dunkelgrün. "
)

def _build_carousel_prompt(ingredient_name: str, fact_text: str, menu_example: str, num_slides: int):
    """
    Liefert einen Prompt, der ein JSON mit Slides erzwingt.
    """
    guide = (
        "Erzeuge ein JSON-Objekt mit genau diesen Feldern:\n"
        '{ "slides": [ { "heading": "", "caption": "", "visual_idea": "", "alt_text": "" } , ... ], "hashtags": "" }\n'
        "Regeln:\n"
        f"- Anzahl Slides: {num_slides}\n"
        "- Slide 1 = Serien-Stil:\n"
        "  • Lose Zutaten (z. B. Safran, Blaubeeren, Berberitzen) = fotorealistisch in einer rustikalen Holz-/Keramikschale.\n"
        "  • Flüssige/Flaschenprodukte (z. B. Aperol, Öl, Wein) = realistische Flasche.\n"
        "  • Hintergrund: beige #f3d68d  #f2deaa für Hintergrundschattierungen mit dunkelgrüner #14452f Line-Art + optional Schwarz (#000000) für Konturen.\n"
        "  • Hintergrund-Elemente müssen kulturell/ästhetisch passen: "
        "Safran/Berberitzen = persische Ornamente/Muster, "
        "Aperol = italienische Architektur/Landschaft, "
        "Blaubeeren = Wald/Strauch-Skizzen, usw.\n"
        "  • Quadratisch 1024x1024, fotorealistische Darstellung im Vordergrund, stilisierte Zeichnungen im Hintergrund.\n"
        "- Slides 2–4: 2–3 präzise Fakten (Anbau, Eigenschaften, Nährwerte) – kurze Captions, keine Heilversprechen. "
        "Infografik-Stil, 2D-icons mit wölbung in #14452f/#000000 auf #f3d68d.\n"
        "- 1 Slide: Pairings/Verwendung oder Rezept (knapp, praktisch).\n"
        f"- 1 Slide: Restaurant-Bezug (Menübeispiel: {menu_example}) + knappe CTA.\n"
        "- Jede 'caption' 120–180 Zeichen, sachlich.\n"
        "- 'visual_idea': präzises Fotobriefing (inkl. 1024x1024, Farben, Regeln oben).\n"
        "- 'alt_text': max. 140 Zeichen, klare Bildbeschreibung.\n"
        "- 'hashtags': 5–8 relevante Hashtags. Keine Emojis, kein Markdown.\n"
    )
    context = (
        f"Zutat: {ingredient_name}\n"
        f"Faktenbasis:\n{fact_text}\n"
        f"Menübeispiel: {menu_example or '—'}\n"
    )
    return context + "\n" + guide

def _parse_json(s: str):
    s = (s or "").strip()
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"slides": [], "hashtags": ""}

def generate_carousel_plan(ingredient_name: str, fact_text: str, menu_example: str = "", num_slides: int = 6, temperature: float = 0.4):
    """
    Ruft das LLM auf und liefert einen strukturierten Karussell-Plan:
    { "slides": [ {heading, caption, visual_idea, alt_text}, ... ], "hashtags": "..." }
    """
    content = call_openai(
        messages=[
            {"role": "system", "content": CAROUSEL_SYS},
            {"role": "user", "content": _build_carousel_prompt(ingredient_name, fact_text, menu_example, num_slides)},
        ],
        retries=3,
        backoff=2.0,
        temperature=temperature,
    )
    obj = _parse_json(content)
    # Guards: Kappen & säubern
    slides = []
    for sl in obj.get("slides", [])[:num_slides]:
        heading = (sl.get("heading") or "").strip()[:90]
        caption = (sl.get("caption") or "").strip()
        caption = re.sub(r"\s+", " ", caption)[:220]
        visual = (sl.get("visual_idea") or "").strip()[:400]  # etwas länger für genauere Briefings
        alt_tx = (sl.get("alt_text") or "").strip()[:140]
        slides.append({
            "heading": heading,
            "caption": caption,
            "visual_idea": visual,
            "alt_text": alt_tx
        })
    hashtags = (obj.get("hashtags") or "").strip()[:200]
    return {"slides": slides, "hashtags": hashtags}

def build_placeholder_carousel(ingredient_name: str, fact_text: str, menu_example: str = "", num_slides: int = 6):
    """
    Schneller, KI-freier Fallback – generiert simple, saubere Slides.
    """
    slides = []
    hook = f"{ingredient_name}: kurz erklärt"
    slides.append({
        "heading": hook[:90],
        "caption": (fact_text[:200] + "…") if len(fact_text) > 200 else fact_text,
        "visual_idea": (
            f"{ingredient_name} im Serien-Stil: "
            "lose Zutaten in Schale, flüssige Zutaten in Flasche. "
            "Beiger Hintergrund (#f3d68d) mit dunkelgrüner Line-Art (#14452f) + optional schwarze Konturen. "
            "Kulturelle Ornamente je nach Zutat (persisch, italienisch, waldig)."
        ),
        "alt_text": f"{ingredient_name} in Nahaufnahme."
    })
    if menu_example:
        slides.append({
            "heading": "So nutzen wir’s",
            "caption": f"In unserer Karte: {menu_example}. Kurz, präzise eingesetzt – balanciert und aromatisch.",
            "visual_idea": "Serviertes Gericht/Drink mit Fokus auf die Zutat, Flat-Design-Stil auf beige Hintergrund.",
            "alt_text": f"Gericht/Drink mit {ingredient_name}."
        })
    for _ in range(len(slides), num_slides):
        slides.append({
            "heading": "Fakt",
            "caption": "Kurzer, informativer Hinweis zur Zutat. Ohne Floskeln, klar formuliert.",
            "visual_idea": "Infografik auf #f3d68d mit Flat-Icons in #14452f/#000000, klares Layout.",
            "alt_text": "Detailansicht der Zutat."
        })
    return {"slides": slides[:num_slides], "hashtags": "#food #wissen #gastronomie #restaurant"}
