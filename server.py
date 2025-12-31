import subprocess
import os
import sqlite3
import uvicorn
import json
import time
import random
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
shuffle_mode = False  # True = on lit shuffled_playlist, False = playlist normale
current_playing_id = None

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
    global current_playing_id
    current_playing_id = song_id 
    
    # 1. Tuer toutes les instances MPV
    subprocess.run("taskkill /F /IM mpv.exe /T >nul 2>&1 || exit 0", shell=True)

    # 2. Laisser le temps au système de terminer le kill
    time.sleep(0.4)  # ← essentiel pour éviter les MPV fantômes

    # 3. Récupérer le chemin du fichier
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

        # 4. Lancer MPV proprement
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
    global current_playing_id
    pos = read_mpv_property("time-pos") or 0
    duration = read_mpv_property("duration") or 0
    paused = read_mpv_property("pause") or False
    
    track_info = None
    if current_playing_id:
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        # On récupère les colonnes 1, 2 et 3 de votre table tracks
        cur.execute("SELECT id, title, artist, album FROM tracks WHERE id = ?", (current_playing_id,))
        res = cur.fetchone()
        conn.close()
        
        if res:
            track_info = {
                "id": res[0], 
                "title": res[1], 
                "artist": res[2], 
                "album": res[3]
            }

    # On renvoie l'objet 'track' dont le JavaScript a besoin
    return {
        "pos": pos, 
        "duration": duration, 
        "paused": paused, 
        "track": track_info 
    }

# --- PLAYLIST ---
@app.post("/playlist/add/{track_id}")
def add_to_playlist(track_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # Trouver la prochaine position
    cur.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM playlist")
    pos = cur.fetchone()[0]

    # Insérer seulement track_id + position
    cur.execute("INSERT INTO playlist (track_id, position) VALUES (?, ?)", (track_id, pos))
    conn.commit()

    conn.close()
    return {"status": "added"}


@app.get("/playlist")
def get_playlist():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT playlist.track_id, tracks.title, tracks.artist
        FROM playlist
        JOIN tracks ON playlist.track_id = tracks.id
        ORDER BY playlist.position ASC
    """)

    songs = cur.fetchall()
    conn.close()

    return {"songs": [{"id": s[0], "title": s[1], "artist": s[2]} for s in songs]}


@app.delete("/playlist/remove/{track_id}")
def remove_from_playlist(track_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("DELETE FROM playlist WHERE track_id = ?", (track_id,))
    conn.commit()
    conn.close()

    return {"status": "removed"}

# --- VIDER la PLAYLIST ---
@app.delete("/playlist/clear")
def clear_playlist():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM playlist")
    conn.commit()
    conn.close()
    return {"status": "cleared"}

# --- SHUFFLE ---
# ACTIVER
@app.post("/shuffle/enable")
def enable_shuffle():
    global shuffle_mode
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # On récupère la playlist actuelle dans l'ordre
    cur.execute("SELECT track_id FROM playlist ORDER BY position ASC")
    rows = cur.fetchall()
    track_ids = [r[0] for r in rows]

    # On vide la shuffled_playlist
    cur.execute("DELETE FROM shuffled_playlist")

    if track_ids:
        # Mélange sans remise
        random.shuffle(track_ids)
        # On réinsère avec une position 1..N
        for idx, tid in enumerate(track_ids, start=1):
            cur.execute(
                "INSERT INTO shuffled_playlist (track_id, position) VALUES (?, ?)",
                (tid, idx),
            )

    conn.commit()
    conn.close()

    shuffle_mode = True
    return {"status": "enabled", "count": len(track_ids)}

# DESACTIVER
@app.post("/shuffle/disable")
def disable_shuffle():
    global shuffle_mode
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM shuffled_playlist")
    conn.commit()
    conn.close()

    shuffle_mode = False
    return {"status": "disabled"}

#SHUFFLE Status
@app.get("/shuffle/status")
def shuffle_status():
    return {"shuffle": shuffle_mode}


# Route pour obtenir la prochaine chanson
from fastapi import Query
# --- NEXT ---
@app.get("/next")
def get_next(current_id: int = Query(0)):
    """
    Renvoie la prochaine chanson à jouer.
    - Si shuffle_mode = True : lit dans shuffled_playlist
    - Sinon : lit dans playlist
    current_id = id de la chanson en cours (0 si aucune)
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    global shuffle_mode

    if shuffle_mode:
        table = "shuffled_playlist"
    else:
        table = "playlist"

    # Si aucune chanson en cours, on renvoie la première
    if current_id == 0:
        cur.execute(f"""
            SELECT {table}.track_id
            FROM {table}
            ORDER BY {table}.position ASC
            LIMIT 1
        """)
        row = cur.fetchone()
        conn.close()
        if row:
            return {"id": row[0]}
        return {"id": None}

    # On cherche la position de la chanson actuelle
    cur.execute(f"""
        SELECT position FROM {table}
        WHERE track_id = ?
    """, (current_id,))
    res = cur.fetchone()

    if not res:
        conn.close()
        return {"id": None}

    current_pos = res[0]

    # On cherche la suivante
    cur.execute(f"""
        SELECT track_id
        FROM {table}
        WHERE position > ?
        ORDER BY position ASC
        LIMIT 1
    """, (current_pos,))
    next_row = cur.fetchone()
    conn.close()

    if next_row:
        return {"id": next_row[0]}
    else:
        return {"id": None}

# --- PREVIOUS ---
@app.get("/previous")
def get_previous(current_id: int = Query(0)):
    """
    Renvoie la chanson précédente selon le mode :
    - shuffle_mode = True → shuffled_playlist
    - sinon → playlist
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    global shuffle_mode

    table = "shuffled_playlist" if shuffle_mode else "playlist"

    # Si aucune chanson en cours → renvoyer la dernière
    if current_id == 0:
        cur.execute(f"""
            SELECT track_id
            FROM {table}
            ORDER BY position DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        conn.close()
        return {"id": row[0] if row else None}

    # Trouver la position actuelle
    cur.execute(f"""
        SELECT position FROM {table}
        WHERE track_id = ?
    """, (current_id,))
    res = cur.fetchone()

    if not res:
        conn.close()
        return {"id": None}

    current_pos = res[0]

    # Trouver la précédente
    cur.execute(f"""
        SELECT track_id
        FROM {table}
        WHERE position < ?
        ORDER BY position DESC
        LIMIT 1
    """, (current_pos,))
    prev_row = cur.fetchone()
    conn.close()

    return {"id": prev_row[0] if prev_row else None}


# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
