import subprocess
import os
import sqlite3
import uvicorn
import json
import time
import random
import ctypes
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# --- AJOUT: GESTION MISE EN VEILLE ---
# Constantes Windows
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

def set_keep_awake(enable=True):
    """Active ou désactive le mode 'pas de veille'."""
    try:
        if enable:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED
            )
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS
            )
    except Exception as e:
        print(f"Erreur gestion veille: {e}")

# Variables pour le timer de veille
last_music_time = time.time()
TIMEOUT_DELAY = 5 * 60  # 5 minutes


# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MPV_PATH = os.path.join(BASE_DIR, "mpv.exe")
DB_NAME = os.path.join(BASE_DIR, "jukebox.db")
STATIC_PATH = os.path.join(BASE_DIR, "static")
IPC_PIPE = r"\\.\pipe\mpv-juke"
shuffle_mode = False 
current_playing_id = None
DEVICE_ID = "auto"
current_volume = 70

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

# --- AJOUT: TÂCHE DE FOND (BACKGROUND TASK) ---
from contextlib import asynccontextmanager # <--- Ajoute cet import en haut du fichier

# --- GESTION DU CYCLE DE VIE (LIFESPAN) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ce code s'exécute au DÉMARRAGE
    monitor_task = asyncio.create_task(monitor_sleep_loop())
    yield
    # Ce code s'exécute à la FERMETURE
    monitor_task.cancel() # Arrête la tâche de fond
    set_keep_awake(False) # Rend la main à Windows
    print("--- Surveillance de la veille désactivée ---")

# --- MODIFICATION DE LA CRÉATION DE L'APP ---
app = FastAPI(lifespan=lifespan)


# 2. Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def monitor_sleep_loop():
    """Surveille la veille et enchaîne les chansons automatiquement"""
    global last_music_time, current_playing_id
    print("--- Surveillance Veille & Auto-Next activée ---")
    
    while True:
        # 1. On récupère l'état de MPV
        # pos sera un nombre si ça joue, ou None si MPV est fermé
        pos = read_mpv_property("time-pos")
        is_paused = read_mpv_property("pause")
        current_time = time.time()

        # --- PARTIE 1 : GESTION DE LA VEILLE ---
        # On considère que la musique joue si MPV est ouvert ET pas en pause
        is_playing = (pos is not None and is_paused is False)

        if is_playing:
            last_music_time = current_time
            set_keep_awake(True) # Interdire la veille
        else:
            # Si musique arrêtée, on attend le délai de 5 min (TIMEOUT_DELAY)
            if (current_time - last_music_time) < TIMEOUT_DELAY:
                set_keep_awake(True)
            else:
                set_keep_awake(False) # Autoriser la veille

        # --- PARTIE 2 : ENCHAÎNEMENT AUTOMATIQUE (AUTO-NEXT) ---
        # Si pos est None, cela veut dire que MPV s'est arrêté (chanson finie)
        # Mais current_playing_id nous dit qu'une chanson était censée jouer
        if pos is None and current_playing_id is not None:
            print(f"Chanson finie. Recherche de la suivante après l'ID {current_playing_id}...")
            
            # On appelle la logique de ta route /next pour trouver l'ID suivant
            next_song = get_next(current_playing_id)
            next_id = next_song.get("id")

            if next_id:
                print(f"Enchaînement auto vers ID: {next_id}")
                play_song(next_id) # On lance la lecture de la suivante
            else:
                print("Fin de la playlist ou aucune chanson suivante trouvée.")
                current_playing_id = None # On remet à zéro pour ne pas boucler dans le vide

        # On vérifie toutes les 5 secondes (plus réactif pour l'enchaînement)
        await asyncio.sleep(5)

# --- ROUTES ---

@app.get("/")
def read_index():
    return FileResponse(os.path.join(STATIC_PATH, "index.html"))
    
# Moteur de recherche principal
@app.get("/search")
def search_songs(q: str = "", mode: str = "title"):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    term = f"%{q}%"
    
    if mode == "artist":
        # On groupe par album pour n'avoir qu'une ligne par disque
        # On utilise MIN(id) pour avoir un ID de référence pour la carte
        query = """SELECT MIN(id), album, artist, album 
                   FROM tracks 
                   WHERE artist LIKE ? 
                   GROUP BY album 
                   ORDER BY album ASC"""
        cur.execute(query, (term,))
        
    elif mode == "album":
        # Même logique : on veut voir les albums qui correspondent à la recherche
        query = """SELECT MIN(id), album, artist, album 
                   FROM tracks 
                   WHERE album LIKE ? 
                   GROUP BY album, artist 
                   ORDER BY album ASC"""
        cur.execute(query, (term,))
        
    else:
        # Mode titre : on garde l'affichage individuel de chaque chanson
        query = """SELECT id, title, artist, album 
                   FROM tracks 
                   WHERE title LIKE ? OR artist LIKE ? 
                   ORDER BY title ASC"""
        cur.execute(query, (term, term))

    songs = cur.fetchall()
    conn.close()
    
    return {"songs": [{"id": s[0], "title": s[1], "artist": s[2], "album": s[3]} for s in songs]}

# Route pour le déploiement (le contenu de l'album)
@app.get("/album_tracks")
def get_album_tracks(album: str, artist: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # On utilise exactement le nom de l'album et de l'artiste
    query = "SELECT id, title, artist, album FROM tracks WHERE album = ? AND artist = ? ORDER BY id ASC"
    cur.execute(query, (album, artist))
    tracks = cur.fetchall()
    conn.close()
    return {"tracks": [{"id": t[0], "title": t[1], "artist": t[2], "album": t[3]} for t in tracks]}


@app.get("/audio-devices")
def get_audio_devices():
    """Récupère la liste des noms 'FriendlyName' des sorties audio actives via PowerShell."""
    cmd = 'powershell "Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object FriendlyName | ConvertTo-Json"'
    try:
        result = subprocess.check_output(cmd, shell=True).decode('utf-8')
        if not result.strip():
            return {"devices": []}
            
        data = json.loads(result)
        # Gestion du cas où il n'y a qu'un seul périphérique (objet vs liste)
        devices = [d['FriendlyName'] for d in (data if isinstance(data, list) else [data])]
        return {"devices": devices}
    except Exception as e:
        print(f"Erreur audio-devices: {e}")
        return {"error": str(e), "devices": []}

@app.get("/play/{song_id}")
def play_song(song_id: int, device: str = None):
    """Lance la lecture d'un morceau sur un périphérique spécifique."""
    global current_playing_id, DEVICE_ID
    
    # 1. Mise à jour de l'état global
    current_playing_id = song_id
    
    # 2. Détermination du périphérique (Priorité au paramètre URL, sinon global)
    # On utilise 'device' s'il est fourni, sinon la variable DEVICE_ID
    target_device = device if device else DEVICE_ID

    # 3. Arrêt propre des instances précédentes
    subprocess.run("taskkill /F /IM mpv.exe /T >nul 2>&1 || exit 0", shell=True)
    time.sleep(0.4) # Temps de latence pour libérer le fichier et le driver audio

    # 4. Recherche du fichier en BDD
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
            f"--audio-device={target_device}",
            f"--input-ipc-server={IPC_PIPE}",
            f"--volume={current_volume}" # On utilise la variable mémorisée ici !
        ]

        # 5. Lancement de MPV (sans fenêtre terminale)
        subprocess.Popen(args, creationflags=0x08000000)
        return {"status": "playing", "device_used": target_device}
    
    return {"status": "error", "message": "Song not found"}


@app.get("/volume/{level}")
def set_volume(level: int):
    global current_volume
    current_volume = int(level) # On mémorise le nouveau volume
    run_mpv_command(["set_property", "volume", current_volume])
    return {"volume": current_volume}

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
        # On s'assure de bien récupérer l'ID pour construire l'URL de la cover
        cur.execute("SELECT id, title, artist, album FROM tracks WHERE id = ?", (current_playing_id,))
        res = cur.fetchone()
        conn.close()
        
        if res:
            track_info = {
                "id": int(res[0]),  # On force en INT pour le JS
                "title": res[1], 
                "artist": res[2], 
                "album": res[3],
                "cover_url": f"/cover/{res[0]}" 
            }

    return {
        "pos": pos, 
        "duration": duration, 
        "paused": paused, 
        "track": track_info 
    }
# --- LIRE un ALBUM en entier ---
# Version FastAPI (à utiliser si tu as "from fastapi import ...")
@app.post("/api/play_album_now")
async def play_album_now(data: dict): # data: dict est nécessaire pour FastAPI
    album = data.get('album')
    artist = data.get('artist')

    conn = sqlite3.connect(DB_NAME) 
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        c.execute("DELETE FROM playlist_album")
        
        # On récupère les morceaux depuis la table 'tracks'
        tracks = c.execute(
            "SELECT id FROM tracks WHERE album = ? AND artist = ? ORDER BY id", 
            (album, artist)
        ).fetchall()

        if not tracks:
            return {"error": "Album non trouvé"}

        for index, track in enumerate(tracks):
            c.execute("INSERT INTO playlist_album (track_id, position) VALUES (?, ?)", 
                      (track['id'], index))

        conn.commit()
        return {
            "status": "success", 
            "first_id": tracks[0]['id'],
            "count": len(tracks)
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

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
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    global shuffle_mode

    # --- ÉTAPE A : PRIORITÉ ALBUM ---
    # On vérifie si la chanson actuelle appartient à l'album flash
    cur.execute("SELECT position FROM playlist_album WHERE track_id = ?", (current_id,))
    res_album = cur.fetchone()

    if res_album:
        current_pos = res_album[0]
        # On cherche la suivante dans l'album
        cur.execute("""
            SELECT track_id FROM playlist_album 
            WHERE position > ? ORDER BY position ASC LIMIT 1
        """, (current_pos,))
        next_row = cur.fetchone()
        
        if next_row:
            conn.close()
            return {"id": next_row[0]}
        else:
            # Fin de l'album : on nettoie la table et on s'arrête (ou on bascule)
            cur.execute("DELETE FROM playlist_album")
            conn.commit()
            conn.close()
            return {"id": None}

    # --- ÉTAPE B : LOGIQUE PLAYLIST NORMALE (ton code existant) ---
    table = "shuffled_playlist" if shuffle_mode else "playlist"
    
    if current_id == 0:
        cur.execute(f"SELECT track_id FROM {table} ORDER BY position ASC LIMIT 1")
    else:
        cur.execute(f"SELECT position FROM {table} WHERE track_id = ?", (current_id,))
        res = cur.fetchone()
        if not res:
            conn.close()
            return {"id": None}
        
        cur.execute(f"SELECT track_id FROM {table} WHERE position > ? ORDER BY position ASC LIMIT 1", (res[0],))
    
    row = cur.fetchone()
    conn.close()
    return {"id": row[0] if row else None}

# --- PREVIOUS ---
@app.get("/previous")
def get_previous(current_id: int = Query(0)):
    """
    Renvoie la chanson précédente :
    1. Regarde d'abord dans playlist_album (prioritaire)
    2. Sinon utilise la logique classique (shuffle ou normale)
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    global shuffle_mode

    # --- 1. TEST PRIORITÉ ALBUM ---
    # On vérifie si l'ID actuel appartient à l'album en cours
    cur.execute("SELECT position FROM playlist_album WHERE track_id = ?", (current_id,))
    res_album = cur.fetchone()

    if res_album:
        current_pos_album = res_album[0]
        # On cherche le morceau précédent dans l'album
        cur.execute("""
            SELECT track_id FROM playlist_album 
            WHERE position < ? 
            ORDER BY position DESC LIMIT 1
        """, (current_pos_album,))
        prev_album_row = cur.fetchone()
        
        if prev_album_row:
            conn.close()
            return {"id": prev_album_row[0]}
        # Si c'est le premier morceau de l'album, on ne renvoie rien (on reste sur place)
        # ou on laisse couler vers la playlist selon ton choix. Ici on s'arrête.
        conn.close()
        return {"id": None}


    # --- 2. TA LOGIQUE CLASSIQUE (Inchangée) ---
    table = "shuffled_playlist" if shuffle_mode else "playlist"

    # Si aucune chanson en cours → renvoyer la dernière
    if current_id == 0:
        cur.execute(f"SELECT track_id FROM {table} ORDER BY position DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return {"id": row[0] if row else None}

    # Trouver la position actuelle dans la playlist
    cur.execute(f"SELECT position FROM {table} WHERE track_id = ?", (current_id,))
    res = cur.fetchone()

    if not res:
        conn.close()
        return {"id": None}

    current_pos = res[0]

    # Trouver la précédente dans la playlist
    cur.execute(f"""
        SELECT track_id FROM {table}
        WHERE position < ?
        ORDER BY position DESC
        LIMIT 1
    """, (current_pos,))
    prev_row = cur.fetchone()
    conn.close()

    return {"id": prev_row[0] if prev_row else None}



#récupérer les covers
@app.get("/cover/{track_id}")
async def get_cover(track_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # On récupère le chemin de la pochette pour ce morceau
    cursor.execute("SELECT cover_path FROM tracks WHERE id = ?", (track_id,))
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        cover_path = row[0]
        if os.path.exists(cover_path):
            return FileResponse(cover_path)
    
    # Si pas d'image, on envoie une image par défaut
    return FileResponse("static/default_cover.png")

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
