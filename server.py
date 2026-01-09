#lancer le fichier actuel avec cette commande ci-dessous pour avoir un reload auto à chaque ctrl+s
# uvicorn server:app --reload --host 0.0.0.0 --port 8000
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
from fastapi import Request

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
current_playlist_name = "Playlist"

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

#Gestion des previous
def handle_previous(current_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    global shuffle_mode

    try:
        # --- 1. TEST PRIORITÉ ALBUM ---
        cur.execute("SELECT position FROM playlist_album WHERE track_id = ?", (current_id,))
        res_album = cur.fetchone()

        if res_album:
            cur.execute("""
                SELECT track_id FROM playlist_album 
                WHERE position < ? 
                ORDER BY position DESC LIMIT 1
            """, (res_album[0],))
            prev_album_row = cur.fetchone()
            return {"id": prev_album_row[0] if prev_album_row else None}

        # --- 2. LOGIQUE PLAYLIST ---
        table = "shuffled_playlist" if shuffle_mode else "playlist"

        # Sécurité : Si ID inconnu ou nul
        if current_id == 0:
            cur.execute(f"SELECT track_id FROM {table} ORDER BY position DESC LIMIT 1")
            row = cur.fetchone()
            return {"id": row[0] if row else None}

        # Trouver la position actuelle
        cur.execute(f"SELECT position FROM {table} WHERE track_id = ?", (current_id,))
        res = cur.fetchone()

        # Si l'ID n'est pas dans la table (changement de playlist)
        if not res:
            cur.execute(f"SELECT track_id FROM {table} ORDER BY position DESC LIMIT 1")
            row = cur.fetchone()
            return {"id": row[0] if row else None}

        # Trouver la précédente
        cur.execute(f"SELECT track_id FROM {table} WHERE position < ? ORDER BY position DESC LIMIT 1", (res[0],))
        prev_row = cur.fetchone()
        
        return {"id": prev_row[0] if prev_row else None}

    finally:
        conn.close()


#Gestion des NEXT pour assurer les enchainements automatiques
def handle_next(current_id):
    """
    Logique unique pour trouver le morceau suivant, 
    utilisée par le bouton 'Next' ET par l'enchaînement automatique.
    """
    global shuffle_mode
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    try:
        # --- 1. PRIORITÉ ALBUM (Si on est en train d'écouter un album précis) ---
        cur.execute("SELECT position FROM playlist_album WHERE track_id = ?", (current_id,))
        res_album = cur.fetchone()
        if res_album:
            cur.execute("SELECT track_id FROM playlist_album WHERE position > ? ORDER BY position ASC LIMIT 1", (res_album[0],))
            row = cur.fetchone()
            if row:
                return {"id": row[0]}
            else:
                cur.execute("DELETE FROM playlist_album")
                conn.commit()
                return {"id": None}

        # --- 2. GESTION DU SHUFFLE (Auto-réparation) ---
        if shuffle_mode:
            cur.execute("SELECT COUNT(*) FROM shuffled_playlist")
            if cur.fetchone()[0] == 0:
                cur.execute("SELECT track_id FROM playlist")
                ids = [r[0] for r in cur.fetchall()]
                if ids:
                    import random
                    random.shuffle(ids)
                    for i, tid in enumerate(ids):
                        cur.execute("INSERT INTO shuffled_playlist (track_id, position) VALUES (?, ?)", (tid, i))
                    conn.commit()

        # --- 3. CHOIX DE LA TABLE (Normal ou Shuffle) ---
        table = "shuffled_playlist" if shuffle_mode else "playlist"

        cur.execute(f"SELECT position FROM {table} WHERE track_id = ?", (current_id,))
        res = cur.fetchone()

        if res:
            # On cherche le suivant
            cur.execute(f"SELECT track_id FROM {table} WHERE position > ? ORDER BY position ASC LIMIT 1", (res[0],))
        else:
            # Si non trouvé (ex: changement de playlist en cours), on prend le premier
            cur.execute(f"SELECT track_id FROM {table} ORDER BY position ASC LIMIT 1")
        
        row = cur.fetchone()
        return {"id": row[0] if row else None}

    except Exception as e:
        print(f"Erreur handle_next: {e}")
        return {"id": None}
    finally:
        conn.close()


async def monitor_sleep_loop():
    global last_music_time, current_playing_id
    print("--- Surveillance Veille & Auto-Next Active ---")
    
    while True:
        # 1. Capture d'état unique
        pos = read_mpv_property("time-pos")
        is_paused = read_mpv_property("pause")
        current_time = time.time()

        # 2. Gestion de la veille (Keep Awake) - Condensée
        is_playing = (pos is not None and not is_paused)
        if is_playing:
            last_music_time = current_time
            set_keep_awake(True)
        else:
            # Reste éveillé si on est encore dans le délai de grâce
            set_keep_awake((current_time - last_music_time) < TIMEOUT_DELAY)

        # 3. Enchaînement Automatique (Auto-Next)
        if pos is None and current_playing_id is not None:
            await asyncio.sleep(2) # Sécurité NAS plus courte
            
            if read_mpv_property("time-pos") is None:
                print(f"Fin de piste ID: {current_playing_id}")
                
                # C'est ici que la magie opère via la fonction qu'on a créée
                next_data = handle_next(current_playing_id)
                
                if next_data and next_data.get("id"):
                    print(f"Enchaînement -> {next_data['id']}")
                    play_song(next_data["id"]) 
                else:
                    print("Fin de playlist.")
                    current_playing_id = None

        # 4. Fréquence de rafraîchissement (2s = plus réactif que 5s)
        await asyncio.sleep(2)

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

def force_kill_mpv():
    """S'assure que mpv est mort et enterré avant de continuer."""
    # On lance le kill
    subprocess.run("taskkill /F /IM mpv.exe /T >nul 2>&1 || exit 0", shell=True)
    
    # On vérifie activement la liste des processus (max 1 seconde d'attente)
    max_attempts = 10
    while max_attempts > 0:
        check = subprocess.run('tasklist /FI "IMAGENAME eq mpv.exe"', capture_output=True, text=True, shell=True)
        if "mpv.exe" not in check.stdout:
            break
        time.sleep(0.1)
        max_attempts -= 1
    
    # Petit délai de grâce final pour que le driver audio se libère
    time.sleep(0.4)


@app.get("/play/{song_id}")
def play_song(song_id: int, device: str = None):
    """Lance la lecture d'un morceau sur un périphérique spécifique."""
    global current_playing_id, DEVICE_ID, current_volume
    
    # 1. ARRÊT PROPRE ET RADICAL (Sécurité anti-chevauchement)
    # On utilise la fonction qui attend que MPV soit vraiment fermé
    force_kill_mpv() 

    # 2. Mise à jour de l'état global
    current_playing_id = song_id
    
    # 3. Détermination du périphérique
    target_device = device if device else DEVICE_ID

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
            f"--volume={current_volume}"
        ]

        # 5. Lancement de MPV (sans fenêtre terminale)
        # On utilise 0x08000000 pour éviter l'ouverture d'une console CMD
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
    global current_playing_id, current_volume, current_playlist_name
    pos = read_mpv_property("time-pos") or 0
    duration = read_mpv_property("duration") or 0
    paused = read_mpv_property("pause") or False
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # 1. Infos du morceau actuel
    track_info = None
    if current_playing_id:
        cur.execute("SELECT id, title, artist, album FROM tracks WHERE id = ?", (current_playing_id,))
        res = cur.fetchone()
        if res:
            track_info = {
                "id": int(res[0]), "title": res[1], "artist": res[2], 
                "album": res[3], "cover_url": f"/cover/{res[0]}" 
            }

    # 2. RÉCUPÉRATION DE LA BIBLIOTHÈQUE (Synchronisation)
    cur.execute("""
        SELECT info.id, info.name, COUNT(content.id)
        FROM saved_playlists_info info
        LEFT JOIN saved_playlists_content content ON info.id = content.playlist_id
        GROUP BY info.id
        ORDER BY info.created_at DESC
    """)
    playlists_data = [
        {"id": r[0], "name": r[1], "count": r[2]} for r in cur.fetchall()
    ]
    
    conn.close()

    return {
        "pos": pos, 
        "duration": duration, 
        "paused": paused, 
        "track": track_info,
        "volume": current_volume,
        "playlist_name": current_playlist_name,
        "library": playlists_data  # La liste envoyée à tous les clients
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



# --- GESTION DES PLAYLISTS SAUVEGARDÉES ---
@app.post("/api/playlists/create")
async def create_new_playlist_db(request: Request):
    global current_playlist_name
    data = await request.json()
    name = data.get('name')
    
    if not name:
        return {"error": "Nom manquant"}

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 1. On crée l'entrée dans la bibliothèque immédiatement
        # Si elle existe déjà, on récupère juste l'ID, sinon on l'insère
        c.execute("INSERT OR IGNORE INTO saved_playlists_info (name) VALUES (?)", (name,))
        c.execute("SELECT id FROM saved_playlists_info WHERE name = ?", (name,))
        playlist_id = c.fetchone()[0]

        # 2. On vide la file d'attente actuelle (la table 'playlist') 
        # car on "switche" sur une nouvelle playlist vide
        c.execute("DELETE FROM playlist")
        
        # 3. Mise à jour de la variable globale
        current_playlist_name = name
        
        conn.commit()
        return {"status": "success", "id": playlist_id, "name": name}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.post('/api/playlists/save')
async def save_playlist(request: Request): # On ajoute 'request' ici
    data = await request.json() # Avec FastAPI, on utilise 'await request.json()'
    name = data.get('name')
    
    if not name:
        return {"error": "Nom manquant"}

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 1. Vérifier si la playlist existe
        c.execute("SELECT id FROM saved_playlists_info WHERE name = ?", (name,))
        row = c.fetchone()

        if row:
            playlist_id = row[0]
            # Supprimer l'ancien contenu pour cette playlist (Enrichissement)
            c.execute("DELETE FROM saved_playlists_content WHERE playlist_id = ?", (playlist_id,))
        else:
            # Créer une nouvelle entrée
            c.execute("INSERT INTO saved_playlists_info (name) VALUES (?)", (name,))
            playlist_id = c.lastrowid

        # 2. Récupérer les morceaux de la file d'attente actuelle (table 'playlist')
        c.execute("SELECT track_id, position FROM playlist ORDER BY position")
        current_tracks = c.fetchall()

        # 3. Sauvegarder les morceaux
        for track in current_tracks:
            c.execute("""
                INSERT INTO saved_playlists_content (playlist_id, track_id, position)
                VALUES (?, ?, ?)
            """, (playlist_id, track[0], track[1]))

        conn.commit()
        return {"status": "success", "message": "Playlist enregistrée"}

    except Exception as e:
        print(f"Erreur SQL: {e}")
        return {"error": str(e)}
    finally:
        conn.close()

@app.get("/api/playlists")
def list_saved_playlists():
    """Renvoie la liste de toutes les playlists enregistrées."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # On récupère le nom, la date, et on compte le nombre de morceaux au passage !
    c.execute("""
        SELECT info.id, info.name, info.created_at, COUNT(content.id)
        FROM saved_playlists_info info
        LEFT JOIN saved_playlists_content content ON info.id = content.playlist_id
        GROUP BY info.id
        ORDER BY info.created_at DESC
    """)
    rows = cur = c.fetchall()
    conn.close()
    return {
        "playlists": [
            {"id": r[0], "name": r[1], "date": r[2], "count": r[3]} 
            for r in rows
        ]
    }

@app.post("/api/playlists/load")
async def load_saved_playlist(data: dict):
    global shuffle_mode, current_playlist_name  # Mise à jour des deux globales
    playlist_id = data.get("id")
    if not playlist_id:
        return {"error": "ID de playlist manquant"}

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 0. Récupérer le nom de la playlist pour la synchro
        c.execute("SELECT name FROM saved_playlists_info WHERE id = ?", (playlist_id,))
        res_name = c.fetchone()
        if res_name:
            current_playlist_name = res_name[0]

        # 1. On vide TOUT pour repartir à neuf
        c.execute("DELETE FROM playlist")
        c.execute("DELETE FROM shuffled_playlist")
        c.execute("DELETE FROM playlist_album")
        
        # 2. On désactive le mode shuffle côté serveur
        shuffle_mode = False 

        # 3. On injecte les morceaux de la sauvegarde
        c.execute("""
            INSERT INTO playlist (track_id, position)
            SELECT track_id, position 
            FROM saved_playlists_content 
            WHERE playlist_id = ?
            ORDER BY position ASC
        """, (playlist_id,))

        conn.commit()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

@app.delete("/api/playlists/{playlist_id}")
def delete_saved_playlist(playlist_id: int):
    """Supprime définitivement une playlist du catalogue."""
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        c = conn.cursor()
        c.execute("DELETE FROM saved_playlists_info WHERE id = ?", (playlist_id,))
        conn.commit()
        return {"status": "deleted"}
    finally:
        conn.close()

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
    # On utilise la fonction centralisée
    return handle_next(current_id)

# --- PREVIOUS ---
@app.get("/previous")
def get_previous(current_id: int = Query(0)):
    return handle_previous(current_id)

@app.post("/api/clear_album_table")
def clear_album_table():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM playlist_album")
    conn.commit()
    conn.close()
    return {"status": "cleared"}

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
