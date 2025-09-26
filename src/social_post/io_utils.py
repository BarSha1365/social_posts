import json, requests
from pathlib import Path
from .config import NOTION_DATABASE_ID, HEADERS

def read_json(path: Path, default=None):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def test_database_connection():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200:
        print("✅ Notion-Datenbank erreichbar.")
    else:
        raise SystemExit(f"❌ Notion DB Fehler {r.status_code}: {r.text}")