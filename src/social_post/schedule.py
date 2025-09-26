# src/social_post/schedule.py
import random
from datetime import datetime, timedelta
from .config import POST_TIME_HOUR, REGION_TZ, AUTO_POST_TIME, POST_JITTER_MINUTES

# Baseline-Strategie pro Wochentag & Post-Typ (Lokale Zeit, Mo=0 .. So=6)
# Ziel: Mittag/Feierabend-Spitzen, Ruhetage etwas früher (Info-Content)
_BASE = {
    "produkt": {
        0: (11, 45),  # Mo
        1: (10, 30),  # Di (Ruhetag → früher Info/Top-of-mind)
        2: (10, 30),  # Mi (Ruhetag)
        3: (11, 45),  # Do
        4: (17, 45),  # Fr (After-Work)
        5: (17, 30),  # Sa (Abend)
        6: (11, 30),  # So (Brunch/Mittag)
    },
    "zitat": {
        0: (9, 30), 1: (9, 30), 2: (9, 30), 3: (9, 30), 4: (9, 30), 5: (10, 0), 6: (10, 0),
    },
    "ingredient_fact": {
        0: (14, 30), 1: (11, 0), 2: (11, 0), 3: (14, 30), 4: (15, 0), 5: (12, 0), 6: (12, 0),
    },
    "anlass": {  # neutrale, frühere Zeit
        0: (10, 0), 1: (10, 0), 2: (10, 0), 3: (10, 0), 4: (10, 0), 5: (10, 0), 6: (10, 0),
    },
}

def _base_time(dt: datetime, post_type: str):
    wd = dt.weekday()
    pt = (post_type or "").lower()
    if pt in _BASE and wd in _BASE[pt]:
        h, m = _BASE[pt][wd]
    else:
        # Fallback: fester POST_TIME_HOUR aus .env
        h, m = POST_TIME_HOUR, 0
    return h, m

def _stable_jitter_minutes(dt: datetime, post_type: str, span: int) -> int:
    """
    deterministischer Jitter in Minuten im Bereich [-span, +span]
    abhängig von Datum & Post-Typ → reproduzierbar, aber nicht „immer gleich rund“.
    """
    seed = int(dt.strftime("%Y%m%d")) ^ hash(post_type)
    rnd = random.Random(seed)
    return rnd.randint(-span, span)

def _stable_seconds(dt: datetime, post_type: str) -> int:
    seed = (int(dt.strftime("%Y%m%d")) << 1) ^ hash("sec:" + str(post_type))
    rnd = random.Random(seed)
    return rnd.randint(0, 59)

def compute_scheduled_datetime(dt: datetime, post_type: str) -> datetime:
    """
    Liefert eine geplante Zeit für Notion:
    - Wenn AUTO_POST_TIME=1 → intelligente Baseline je Wochentag/Posttyp
    - Sonst → fester POST_TIME_HOUR
    - In beiden Fällen: deterministischer Jitter ±POST_JITTER_MINUTES + zufällige Sekunden
    """
    if AUTO_POST_TIME:
        h, m = _base_time(dt, post_type)
    else:
        h, m = POST_TIME_HOUR, 0

    base = dt.replace(hour=h, minute=m, second=0, microsecond=0)
    # deterministischer Jitter
    j = _stable_jitter_minutes(dt, post_type, POST_JITTER_MINUTES)
    scheduled = base + timedelta(minutes=j)

    # Sekunden leicht variieren
    scheduled = scheduled.replace(second=_stable_seconds(dt, post_type))
    return scheduled
