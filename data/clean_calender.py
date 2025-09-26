import json
from datetime import datetime
import re

JAHR = 2025
INPUT_FILE = "kalender_roh.txt"
BEREINIGT_FILE = "kalender_bereinigt.txt"
OUTPUT_FILE = "anlass_kalender.json"

# === Schritt 1: Bereinige Textdatei ===
with open(INPUT_FILE, encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

bereinigt = []
for line in lines:
    if re.match(r"^\d{1,2} [A-Za-zäöüÄÖÜ]+", line):
        print(f"📅 Neue Zeile erkannt: {line}")
        bereinigt.append(line)
    elif bereinigt:
        print(f"↪️  An vorherige Zeile anhängen: {line}")
        bereinigt[-1] += ", " + line  # an letzte Zeile anhängen
    else:
        print(f"⚠️  Zeile übersprungen (keine vorherige Zeile zum Anhängen): {line}")

# Speichern für Debug
with open(BEREINIGT_FILE, "w", encoding="utf-8") as f:
    for line in bereinigt:
        f.write(line + "\n")

# === Schritt 2: Erzeuge JSON ===
monatsnamen = {
    "Januar": "01", "Februar": "02", "März": "03", "April": "04",
    "Mai": "05", "Juni": "06", "Juli": "07", "August": "08",
    "September": "09", "Oktober": "10", "November": "11", "Dezember": "12"
}

anlaesse = {}
for line in bereinigt:
    match = re.match(r"^(\d{1,2}) ([A-Za-zäöüÄÖÜ]+)\s+(.*)", line)
    if match:
        tag, monat, text = match.groups()
        monat = monat.strip()
        if monat in monatsnamen:
            datum = f"{JAHR}-{monatsnamen[monat]}-{int(tag):02d}"
            anlaesse[datum] = {
                "beschreibung": text.strip(),
                "kategorie": "Sonstiges"
            }
            print(f"✅ {datum}: {text.strip()}")
        else:
            print(f"❌ Unbekannter Monatsname: {monat}")
    else:
        print(f"❌ Kein gültiges Datumsformat gefunden in Zeile: {line}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(anlaesse, f, indent=2, ensure_ascii=False)

print(f"✅ Bereinigt gespeichert in {BEREINIGT_FILE}")
print(f"✅ Anlasskalender gespeichert in {OUTPUT_FILE} mit {len(anlaesse)} Einträgen.")
