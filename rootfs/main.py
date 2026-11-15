from __future__ import annotations

import hmac
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

DATA_DIR = Path("/data")
OPTIONS_FILE = DATA_DIR / "options.json"
QUEUE_DIR = DATA_DIR / "queue_videos"
PROCESSING_DIR = DATA_DIR / "processing"
FAILED_DIR = DATA_DIR / "failed"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
CHUNK_SIZE = 1024 * 1024

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
)
log = logging.getLogger("ha-3d2cloud")

for directory in (QUEUE_DIR, PROCESSING_DIR, FAILED_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def load_options() -> dict[str, Any]:
    try:
        with OPTIONS_FILE.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        log.warning("%s nie istnieje; używam wartości domyślnych", OPTIONS_FILE)
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Nie można odczytać konfiguracji: %s", exc)
    return {}


def option(name: str, default: Any = None) -> Any:
    return load_options().get(name, default)


def safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return (cleaned or "video")[:100]


def queue_snapshot() -> dict[str, Any]:
    return {
        "queued": len(list(QUEUE_DIR.iterdir())),
        "processing": len(list(PROCESSING_DIR.iterdir())),
        "failed": len(list(FAILED_DIR.iterdir())),
        "youtube_enabled": bool(option("youtube_enabled", False)),
        "printer_name": option("printer_name", "3D Printer"),
    }


def make_title(filename: str) -> str:
    printer = str(option("printer_name", "3D Printer"))
    template = str(option("title_template", "{printer} - {filename} {date}"))
    values = {
        "printer": printer,
        "filename": Path(filename).stem,
        "date": datetime.now().astimezone().strftime("%Y-%m-%d"),
    }
    try:
        title = template.format_map(values)
    except (KeyError, ValueError) as exc:
        log.warning("Błędny title_template (%s); używam domyślnego", exc)
        title = "{printer} - {filename} {date}".format_map(values)
    return title[:100]


def youtube_access_token() -> str:
    token = str(option("youtube_access_token", "")).strip()
    refresh = str(option("youtube_refresh_token", "")).strip()
    client_id = str(option("youtube_client_id", "")).strip()
    client_secret = str(option("youtube_client_secret", "")).strip()

    if refresh and client_id and client_secret:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
    if not token:
        raise RuntimeError("Brak youtube_access_token lub danych do odświeżenia OAuth")
    return token


def upload_to_youtube(video_path: Path, title: str) -> str:
    token = youtube_access_token()
    privacy = str(option("youtube_privacy_status", "unlisted"))
    if privacy not in {"private", "unlisted", "public"}:
        privacy = "unlisted"
    metadata = {
        "snippet": {
            "title": title,
            "description": "Timelapse wydrukowany i przesłany przez HA 3d2cloud.",
            "categoryId": str(option("youtube_category_id", "22")),
        },
        "status": {"privacyStatus": privacy},
    }
    size = video_path.stat().st_size
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/*",
        "X-Upload-Content-Length": str(size),
    }
    start = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers=headers,
        json=metadata,
        timeout=60,
    )
    start.raise_for_status()
    upload_url = start.headers.get("Location")
    if not upload_url:
        raise RuntimeError("YouTube nie zwrócił adresu sesji resumable upload")

    with video_path.open("rb") as stream:
        result = requests.put(
            upload_url,
            data=stream,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/*",
                "Content-Length": str(size),
            },
            timeout=(60, 3600),
        )
    result.raise_for_status()
    video_id = result.json().get("id")
    if not video_id:
        raise RuntimeError("YouTube nie zwrócił identyfikatora filmu")
    return f"https://www.youtube.com/watch?v={video_id}"


def process_file(source: Path) -> None:
    target = PROCESSING_DIR / source.name
    try:
        source.replace(target)
    except FileNotFoundError:
        return

    try:
        if bool(option("youtube_enabled", False)):
            title = make_title(target.name)
            url = upload_to_youtube(target, title)
            log.info("Wysłano %s jako '%s': %s", target.name, title, url)
        else:
            log.info("YouTube wyłączony; pomijam wysyłkę pliku %s", target.name)
        # Po poprawnym przetworzeniu plik jest usuwany, aby nie zajmował /data.
        target.unlink(missing_ok=True)
    except Exception:
        log.exception("Przetwarzanie %s nie powiodło się; plik zachowano w /data/failed", target.name)
        failed_target = FAILED_DIR / target.name
        try:
            target.replace(failed_target)
        except OSError:
            log.exception("Nie udało się przenieść pliku do katalogu failed")


def worker_loop() -> None:
    log.info("Worker kolejki uruchomiony")
    while True:
        try:
            candidates = sorted(
                p for p in QUEUE_DIR.iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
            )
            if candidates:
                process_file(candidates[0])
            else:
                time.sleep(2)
        except Exception:
            log.exception("Błąd workera")
            time.sleep(5)


worker = threading.Thread(target=worker_loop, name="video-worker", daemon=True)


app = FastAPI(
    title="HA 3d2cloud",
    description="Odbiór timelapsów z drukarek 3D",
    version="1.0.0",
)


@app.on_event("startup")
def start_worker() -> None:
    if not worker.is_alive():
        worker.start()


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """
<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HA 3d2cloud</title>
<style>
body{font:16px system-ui,sans-serif;background:#111827;color:#e5e7eb;margin:0;padding:28px}
main{max-width:760px;margin:auto}h1{font-size:1.7rem}.panel{background:#1f2937;padding:20px;border-radius:12px;margin:16px 0}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stat{background:#374151;padding:16px;border-radius:8px}
small{color:#9ca3af}code{color:#93c5fd}
</style></head>
<body><main>
<h1>HA 3d2cloud</h1>
<p>Odbiór i kolejkowanie timelapsów z drukarki 3D.</p>
<div class="panel"><h2>Status kolejki</h2><div class="stats">
<div class="stat"><small>Oczekujące</small><h2 id="queued">—</h2></div>
<div class="stat"><small>Przetwarzane</small><h2 id="processing">—</h2></div>
<div class="stat"><small>Błędy</small><h2 id="failed">—</h2></div>
</div><p id="youtube"></p><small>Odświeżanie co 5 sekund.</small></div>
<div class="panel"><h2>API drukarki</h2><p><code>POST /api/upload</code></p>
<p>Multipart/form-data, pole pliku: <code>file</code>. Opcjonalnie nagłówek <code>X-API-Token</code>.</p>
</div>
</main><script>
async function refresh(){try{const r=await fetch('api/status');if(!r.ok)return;const s=await r.json();
for(const k of ['queued','processing','failed'])document.getElementById(k).textContent=s[k];
document.getElementById('youtube').textContent='YouTube: '+(s.youtube_enabled?'włączony':'wyłączony')+' | Drukarka: '+s.printer_name;
}catch(e){}}
refresh();setInterval(refresh,5000);
</script></body></html>
"""


@app.get("/api/status")
def status() -> dict[str, Any]:
    return queue_snapshot()


@app.post("/api/upload")
async def upload_video(
    file: UploadFile = File(...),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> JSONResponse:
    configured_token = str(option("api_token", "")).strip()
    if configured_token and not hmac.compare_digest(configured_token, x_api_token or ""):
        raise HTTPException(status_code=401, detail="Nieprawidłowy token API")

    original_name = Path(file.filename or "timelapse.mp4").name
    extension = Path(original_name).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Niedozwolony format. Obsługiwane: mp4, mov, mkv, webm, avi")

    max_bytes = int(option("max_upload_mb", 4096)) * 1024 * 1024
    unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}_{safe_stem(Path(original_name).stem)}{extension}"
    temporary_path = QUEUE_DIR / f".{unique_name}.part"
    final_path = QUEUE_DIR / unique_name
    written = 0

    try:
        with temporary_path.open("xb") as output:
            while chunk := await file.read(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail=f"Plik przekracza limit {max_bytes // (1024 * 1024)} MB")
                output.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="Przesłany plik jest pusty")
        temporary_path.replace(final_path)
    except HTTPException:
        temporary_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temporary_path.unlink(missing_ok=True)
        log.exception("Błąd zapisu przesłanego pliku")
        raise HTTPException(status_code=500, detail="Nie udało się zapisać pliku") from exc
    finally:
        await file.close()

    log.info("Dodano do kolejki: %s (%d bajtów)", final_path.name, written)
    return JSONResponse(
        status_code=202,
        content={"accepted": True, "queued_file": final_path.name, "bytes": written},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
