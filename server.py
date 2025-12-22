import subprocess
import os
import sqlite3
import uvicorn
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # <--- IL MANQUAIT CETTE LIGNE
from fastapi.responses import FileResponse

# 1. Création de l'application
app = FastAPI()

# 2. Configuration CORS (Indispensable pour l'accès réseau)
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
    # 1. On tue proprement toute instance précédente
    # On ajoute || exit 0 pour éviter que l'erreur "processus non trouvé" ne bloque tout
    subprocess.run("taskkill /F /IM mpv.exe /T >nul 2>&1 || exit 0", shell=True)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT path FROM tracks WHERE id = ?", (song_id,))
    res = cur.fetchone()
    conn.close()

    if res:
        file_path = res[0]
        # 2. Arguments optimisés pour le mode "Invisible"
        args = [
            MPV_PATH, 
            file_path,
            "--no-video",            # Pas de fenêtre vidéo
            "--force-window=no",     # Pas de fenêtre du tout
            "--no-terminal",         # Pas de sortie console
            f"--audio-device={DEVICE_ID}",
            f"--input-ipc-server={IPC_PIPE}",
            "--volume=70"            # Volume initial par sécurité
        ]
        
        # 3. Le code magique 0x08000000 (CREATE_NO_WINDOW)
        # On utilise Popen pour ne pas attendre que la musique finisse pour répondre au navigateur
        subprocess.Popen(args, creationflags=0x08000000)
        
        print(f"Lecture lancée : {file_path}")
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

@app.get("/pause")
def toggle_pause():
    # 'cycle pause' bascule entre lecture et pause
    run_mpv_command(["cycle", "pause"])
    return {"status": "toggled"}

@app.get("/seek/{seconds}")
def seek_time(seconds: int):
    # Avance ou recule de X secondes
    run_mpv_command(["seek", seconds])
    return {"status": "moved"}

@app.get("/status")
def get_status():
    # Pour l'instant on renvoie des valeurs fictives pour ne pas faire d'erreur
    # On connectera la lecture réelle du temps juste après
    return {"pos": 0, "duration": 0, "paused": False}


# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" permet d'écouter sur TOUTES les interfaces (WiFi, Ethernet, Localhost)
    uvicorn.run(app, host="0.0.0.0", port=8000)