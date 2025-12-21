from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import subprocess
import sqlite3
import os
import uvicorn

app = FastAPI()

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MPV_PATH = os.path.join(BASE_DIR, "mpv.exe")
DB_NAME = os.path.join(BASE_DIR, "jukebox.db")
STATIC_PATH = os.path.join(BASE_DIR, "static")

# Tentative de détection du Jabra
DEVICE_ID = "wasapi/Speakers (Jabra SPEAK 510 USB)"

# Variable pour mémoriser le volume entre deux morceaux
CURRENT_VOLUME = 70

# --- GESTION DES FICHIERS STATIQUES ---
if not os.path.exists(STATIC_PATH):
    os.makedirs(STATIC_PATH)

app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

def stop_previous_mpv():
    """Arrête proprement les instances de mpv en cours"""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "mpv.exe"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass

# --- ROUTES API ---

@app.get("/")
def read_index():
    """Sert la page d'accueil (index.html dans le dossier static)"""
    return FileResponse(os.path.join(STATIC_PATH, "index.html"))

@app.get("/search")
def search_songs(q: str = ""):
    """Route de recherche filtrée ou intégrale"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # On trie par titre pour que ce soit plus lisible (ORDER BY)
    query = "SELECT id, title, artist FROM tracks WHERE title LIKE ? OR artist LIKE ? ORDER BY title ASC"
    term = f"%{q}%"
    cur.execute(query, (term, term))
    songs = cur.fetchall()
    conn.close()
    return {"songs": [{"id": s[0], "title": s[1], "artist": s[2]} for s in songs]}

@app.get("/volume/{level}")
def set_volume(level: int):
    """Met à jour le volume global pour le prochain lancement"""
    global CURRENT_VOLUME
    # On s'assure que le volume reste entre 0 et 100
    CURRENT_VOLUME = max(0, min(100, level))
    print(f"Volume réglé sur : {CURRENT_VOLUME}%")
    return {"status": "volume_updated", "level": CURRENT_VOLUME}

@app.get("/play/{song_id}")
def play_song(song_id: int):
    stop_previous_mpv()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT path FROM tracks WHERE id = ?", (song_id,))
    result = cur.fetchone()
    conn.close()

    if result:
        file_path = result[0]
        args = [
            MPV_PATH, file_path, 
            "--no-video", 
            "--vo=null",
            f"--audio-device={DEVICE_ID}", 
            f"--volume={CURRENT_VOLUME}",  # Application du volume ici
            "--really-quiet"
        ]
        # Lancement en arrière-plan
        subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"status": "playing", "song": os.path.basename(file_path), "volume": CURRENT_VOLUME}
    
    return {"status": "error", "message": "Chanson non trouvée"}

@app.get("/stop")
def stop():
    stop_previous_mpv()
    return {"status": "stopped"}

@app.get("/list")
def list_songs():
    return search_songs("")

if __name__ == "__main__":
    # Écoute sur toutes les interfaces pour l'accès mobile
    uvicorn.run(app, host="0.0.0.0", port=8000)