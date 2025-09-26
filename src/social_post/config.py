from dotenv import load_dotenv
import os
load_dotenv()

OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN         = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID   = os.getenv("NOTION_DATABASE_ID")
OPENAI_MODEL         = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
NOTION_VERSION       = os.getenv("NOTION_VERSION", "2022-06-28")
POST_TIME_HOUR       = int(os.getenv("POST_TIME_HOUR", "10"))
REGION_TZ            = os.getenv("REGION_TZ", "Europe/Berlin")
AUTO_POST_TIME       = bool(int(os.getenv("AUTO_POST_TIME", "1")))       # 1=auto, 0=fixed
POST_JITTER_MINUTES  = int(os.getenv("POST_JITTER_MINUTES", "17"))       # ±Jitter in Minuten


# Hinweis: Validierung erfolgt zur Laufzeit (CLI).

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}