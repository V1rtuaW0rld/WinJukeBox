import os
import sqlite3
import logging
from mutagen.id3 import ID3
from tqdm import tqdm

# --- CONFIGURATION ---
MUSIC_FOLDER = r"\\192.168.0.3\music"
DB_NAME = "jukeboxnew.db"

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Table Tracks
    c.execute('''CREATE TABLE IF NOT EXISTS tracks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT, artist TEXT, album TEXT, path TEXT, cover_path TEXT)''')
    
    # Ajout colonne cover_path si manquante
    try:
        c.execute("ALTER TABLE tracks ADD COLUMN cover_path TEXT")
    except sqlite3.OperationalError:
        pass

    # Table Playlist
    c.execute('''CREATE TABLE IF NOT EXISTS playlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    position INTEGER NOT NULL)''')

    # Table Shuffled Playlist
    c.execute('''CREATE TABLE IF NOT EXISTS shuffled_playlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    position INTEGER NOT NULL)''')

    conn.commit()
    return conn


def scan_music():
    logging.info(f"Scan en cours de {MUSIC_FOLDER}...")

    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM tracks")

    # --- Étape 1 : Pré-scan pour compter les MP3 ---
    logging.info("Pré-scan des fichiers...")
    all_mp3 = []

    for root, dirs, files in os.walk(MUSIC_FOLDER):
        for file in files:
            if file.lower().endswith(".mp3"):
                all_mp3.append((root, file))

    total = len(all_mp3)
    logging.info(f"{total} fichiers MP3 détectés.")

    # --- Étape 2 : Scan réel avec barre de progression ---
    for root, file in tqdm(all_mp3, desc="Indexation des MP3"):
        full_path = os.path.join(root, file)

        # Détection de la couverture
        current_cover = None
        try:
            for f in os.listdir(root):
                if f.lower() in ['cover.jpg', 'cover.png', 'folder.jpg', 'front.jpg']:
                    current_cover = os.path.join(root, f)
                    break
        except Exception as e:
            logging.warning(f"Impossible de lire le dossier {root}: {e}")

        # Valeurs par défaut
        artist = "Artiste Inconnu"
        album = os.path.basename(root)
        title = file

        # Lecture des tags ID3
        try:
            try:
                audio = ID3(full_path)
                artist = str(audio.get('TPE1', ['Artiste Inconnu'])[0])
                album = str(audio.get('TALB', ['Album Inconnu'])[0])
                title = str(audio.get('TIT2', [file])[0])
            except Exception:
                pass  # Tags manquants ou illisibles

            # Insertion en base
            c.execute("""INSERT INTO tracks (title, artist, album, path, cover_path) 
                         VALUES (?, ?, ?, ?, ?)""",
                      (title, artist, album, full_path, current_cover))

        except Exception as e:
            logging.error(f"Erreur d'insertion pour {file}: {e}")

    conn.commit()
    count = c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    conn.close()

    logging.info(f"Scan terminé ! {count} morceaux indexés.")


if __name__ == "__main__":
    scan_music()
