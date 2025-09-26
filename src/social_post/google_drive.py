# src/social_post/google_drive.py
from __future__ import annotations
import os, re
from typing import List, Tuple, Optional

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Scopes: Vollzugriff auf Drive-Inhalte (für Ordner anlegen, Permissions setzen)
SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service(sa_file: Optional[str] = None):
    """
    Baut einen Drive-Service mit Service-Account-Credentials.
    Nutzt GOOGLE_DRIVE_SA_FILE aus .env, wenn sa_file nicht übergeben wird.
    """
    sa_path = sa_file or os.getenv("GOOGLE_DRIVE_SA_FILE", "").strip()
    if not sa_path:
        raise RuntimeError("GOOGLE_DRIVE_SA_FILE ist nicht gesetzt.")
    if not os.path.isfile(sa_path):
        raise RuntimeError(f"Service-Account-Datei nicht gefunden: {sa_path}")

    creds = Credentials.from_service_account_file(sa_path, scopes=SCOPES)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service

def extract_folder_id_from_link(url: str) -> Optional[str]:
    """
    Holt die Folder-ID aus einer Drive-URL:
    https://drive.google.com/drive/folders/<ID>[?...]
    """
    if not url:
        return None
    m = re.search(r"/folders/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None

def _find_child_folder(service, name: str, parent_id: str) -> Optional[dict]:
    """
    Sucht einen Unterordner mit exakt gleichem Namen unter parent_id.
    Kein 'param' Argument, stattdessen listen + Python-Filter.
    """
    q = (
        "mimeType='application/vnd.google-apps.folder' "
        "and trashed=false "
        f"and '{parent_id}' in parents"
    )
    page_token = None
    while True:
        resp = service.files().list(
            q=q,
            spaces="drive",
            fields="nextPageToken, files(id,name,webViewLink)",
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            corpora="allDrives",
        ).execute()
        for f in resp.get("files", []):
            if f.get("name") == name:
                return f
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return None

def _create_folder(service, name: str, parent_id: str) -> Tuple[str, str]:
    """
    Legt einen Unterordner unter parent_id an. Gibt (id, webViewLink) zurück.
    """
    file_metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    f = service.files().create(
        body=file_metadata,
        fields="id,name,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return f["id"], f.get("webViewLink", "")

def ensure_folder_path(service, parent_id: str, segments: List[str]) -> Tuple[str, str]:
    """
    Erstellt (falls nötig) die gesamte Ordnerstruktur unter parent_id.
    Gibt (final_folder_id, final_webViewLink) zurück.
    """
    current_id = parent_id
    web_link = ""
    for seg in segments:
        seg = (seg or "").strip()
        if not seg:
            continue
        found = _find_child_folder(service, seg, current_id)
        if found:
            current_id = found["id"]
            web_link = found.get("webViewLink", web_link)
        else:
            current_id, web_link = _create_folder(service, seg, current_id)
    return current_id, web_link

def list_files_in_folder(service, folder_id: str) -> List[dict]:
    """
    Listet Dateien (keine Unterordner) in einem Ordner.
    """
    q = f"trashed=false and '{folder_id}' in parents"
    results: List[dict] = []
    page_token = None
    while True:
        resp = service.files().list(
            q=q,
            spaces="drive",
            fields="nextPageToken, files(id,name,mimeType,webViewLink)",
            pageToken=page_token,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            corpora="allDrives",
        ).execute()
        for f in resp.get("files", []):
            # (wenn du nur Nicht-Ordner willst)
            if f.get("mimeType") != "application/vnd.google-apps.folder":
                results.append(f)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results

def make_file_public(service, file_id: str) -> str:
    """
    Setzt 'anyone: reader' auf eine Datei und gibt eine direkte Download-URL zurück.
    """
    body = {"type": "anyone", "role": "reader"}
    service.permissions().create(
        fileId=file_id,
        body=body,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    # Direkt-URL (für IG-Upload o.ä.)
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def revoke_public(service, file_id: str) -> None:
    """
    Entfernt 'anyone'-Permission auf der Datei.
    """
    perms = service.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role)",
        supportsAllDrives=True,
    ).execute().get("permissions", [])
    for p in perms:
        if p.get("type") == "anyone":
            service.permissions().delete(
                fileId=file_id,
                permissionId=p["id"],
                supportsAllDrives=True,
            ).execute()
