import subprocess
import os
import sqlite3
import uvicorn
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 1. Création de l'application
app = FastAPI()

# 2. Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MPV_PATH = os.path.join(BASE_DIR, "mpv.exe")
DB_NAME = os.path.join(BASE_DIR, "jukebox.db")
STATIC_PATH = os.path.join(BASE_DIR, "static")
DEVICE_ID = "wasapi/Headphones (AUKEY BR-C16)"
IPC_PIPE = r"\\.\pipe\mpv-juke"

def run_mpv_command(command_list):
    """Envoie une commande JSON à MPV via le Pipe Windows"""
    payload = json.dumps({"command": command_list})
    cmd = f'echo {payload} > {IPC_PIPE}'
    subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def read_mpv_property(prop):
    """Lit une propriété MPV via IPC JSON"""
    try:
        with open(IPC_PIPE, "r+b", buffering=0) as pipe:
            cmd = json.dumps({"command": ["get_property", prop]}) + "\n"
            pipe.write(cmd.encode("utf-8"))
            response = pipe.readline().decode("utf-8").strip()
            data = json.loads(response)
            return data.get("data", None)
    except:
        return None

# --- ROUTES ---

@app.get("/")
def read_index():
    return FileResponse(os.path.join(STATIC_PATH, "index.html"))

@app.get("/search")
def search_songs(q: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    query = "SELECT id, title, artist FROM tracks WHERE title LIKE ? OR artist LIKE ? ORDER BY title ASC"
    term = f"%{q}%"
    cur.execute(query, (term, term))
    songs = cur.fetchall()
    conn.close()
    return {"songs": [{"id": s[0], "title": s[1], "artist": s[2]} for s in songs]}

@app.get("/play/{song_id}")
def play_song(song_id: int):
    subprocess.run("taskkill /F /IM mpv.exe /T >nul 2>&1 || exit 0", shell=True)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT path FROM tracks WHERE id = ?", (song_id,))
    res = cur.fetchone()
    conn.close()

    if res:
        file_path = res[0]
        args = [
            MPV_PATH, 
            file_path,
            "--no-video",
            "--force-window=no",
            "--no-terminal",
            f"--audio-device={DEVICE_ID}",
            f"--input-ipc-server={IPC_PIPE}",
            "--volume=70"
        ]
        subprocess.Popen(args, creationflags=0x08000000)
        return {"status": "playing"}
    return {"status": "error"}

@app.get("/volume/{level}")
def set_volume(level: int):
    run_mpv_command(["set_property", "volume", int(level)])
    return {"volume": level}

@app.get("/stop")
def stop():
    subprocess.run(["taskkill", "/F", "/IM", "mpv.exe"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return {"status": "stopped"}

@app.get("/pause")
def toggle_pause():
    run_mpv_command(["cycle", "pause"])
    return {"status": "toggled"}

@app.get("/seek/{seconds}")
def seek_time(seconds: int):
    run_mpv_command(["seek", seconds])
    return {"status": "moved"}

@app.get("/setpos/{position}")
def set_position(position: int):
    run_mpv_command(["set_property", "time-pos", int(position)])
    return {"status": "set"}

@app.get("/status")
def get_status():
    pos = read_mpv_property("time-pos") or 0
    duration = read_mpv_property("duration") or 0
    paused = read_mpv_property("pause") or False
    return {"pos": pos, "duration": duration, "paused": paused}

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
