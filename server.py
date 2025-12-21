import subprocess
import os
import sqlite3
import uvicorn
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MPV_PATH = os.path.join(BASE_DIR, "mpv.exe")
DB_NAME = os.path.join(BASE_DIR, "jukebox.db")
STATIC_PATH = os.path.join(BASE_DIR, "static")
DEVICE_ID = "wasapi/Speakers (Jabra SPEAK 510 USB)"
IPC_PIPE = r"\\.\pipe\mpv-juke"

def run_mpv_command(command_list):
    """Envoie une commande JSON à MPV via le Pipe Windows"""
    payload = json.dumps({"command": command_list})
    # Commande simplifiée pour Windows
    cmd = f'echo {payload} > {IPC_PIPE}'
    try:
        subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception as e:
        print(f"Erreur IPC: {e}")

# --- ROUTES ---

@app.get("/")
def read_index():
    return FileResponse(os.path.join(STATIC_PATH, "index.html"))

@app.get("/search")
def search_songs(q: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # On remet bien la requête SQL
    query = "SELECT id, title, artist FROM tracks WHERE title LIKE ? OR artist LIKE ? ORDER BY title ASC"
    term = f"%{q}%"
    cur.execute(query, (term, term))
    songs = cur.fetchall()
    conn.close()
    return {"songs": [{"id": s[0], "title": s[1], "artist": s[2]} for s in songs]}

@app.get("/play/{song_id}")
def play_song(song_id: int):
    # Tue l'instance précédente
    subprocess.run(["taskkill", "/F", "/IM", "mpv.exe"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT path FROM tracks WHERE id = ?", (song_id,))
    res = cur.fetchone()
    conn.close()

    if res:
        file_path = res[0]
        # Lancement avec le pipe IPC
        args = [
            MPV_PATH, file_path,
            "--no-video",
            f"--audio-device={DEVICE_ID}",
            f"--input-ipc-server={IPC_PIPE}",
            "--really-quiet"
        ]
        subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"status": "playing"}
    return {"status": "error"}

@app.get("/volume/{level}")
def set_volume(level: int):
    print(f"Réglage volume IPC: {level}")
    run_mpv_command(["set_property", "volume", int(level)])
    return {"volume": level}

@app.get("/stop")
def stop():
    subprocess.run(["taskkill", "/F", "/IM", "mpv.exe"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return {"status": "stopped"}

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)