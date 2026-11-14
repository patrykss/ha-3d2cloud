import os
import json
import queue
import threading
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()
upload_queue = queue.Queue()

TEMP_DIR = "/data/queue_videos"
os.makedirs(TEMP_DIR, exist_ok=True)

def load_options():
    try:
        with open("/data/options.json", "r") as f:
            return json.load(f)
    except Exception:
        return {
            "youtube_enabled": False,
            "title_template": "{printer} - {filename} {date}",
            "printer_name": "Ender 3 V3 KE"
        }

def process_queue_worker():
    while True:
        task = upload_queue.get()
        if task is None:
            break

        file_path = task["file_path"]
        filename = task["filename"]
        options = load_options()
        
        printer = options.get("printer_name", "Ender 3 V3 KE")
        template = options.get("title_template", "{printer} - {filename} {date}")
        
        date_str = datetime.now().strftime("%d.%m.%Y")
        title = template.replace("{printer}", printer).replace("{filename}", filename).replace("{date}", date_str)
        
        print(f"Processing video: {filename} with title: '{title}'")
        
        if options.get("youtube_enabled"):
            print("YouTube upload enabled (placeholder for API v3 call)...")
        else:
            print("YouTube upload disabled in config, skipping cloud upload.")
            
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Freed space: deleted local file {file_path}")
            
        upload_queue.task_done()

threading.Thread(target=process_queue_worker, daemon=True).start()

@app.post("/api/upload")
async def receive_video(file: UploadFile = File(...), filename: str = Form(...)):
    file_path = os.path.join(TEMP_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    upload_queue.put({"file_path": file_path, "filename": filename})
    return {"status": "success", "queued_filename": filename}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    options = load_options()
    q_size = upload_queue.qsize()
    printer = options.get("printer_name", "Ender 3 V3 KE")
    template = options.get("title_template", "")
    yt_status = "Enabled" if options.get("youtube_enabled") else "Disabled"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>HA 3d2cloud Dashboard</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f4f6f9; color: #333; margin: 0; padding: 20px; }}
            .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
            h1 {{ color: #03a9f4; margin-top: 0; }}
            .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; background: #e0f7fa; color: #006064; font-weight: bold; }}
            code {{ background: #eee; padding: 2px 6px; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 HA 3d2cloud Bridge</h1>
            <p>Your reliable middleware connecting 3D printer timelapses directly to cloud storage and YouTube while protecting local storage.</p>
        </div>
        <div class="card">
            <h3>Status & Queue</h3>
            <p>Printer Name: <b>{printer}</b></p>
            <p>YouTube Sync: <span class="badge">{yt_status}</span></p>
            <p>Files currently in queue: <b>{{q_size}}</b></p>
            <p>Title Template: <code>{template}</code></p>
        </div>
    </body>
    </html>
    """
