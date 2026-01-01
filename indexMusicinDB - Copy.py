import os
import sqlite3
from mutagen.id3 import ID3

# --- CONFIGURATION ---
MUSIC_FOLDER = r"\\192.168.0.3\music\Ben Harper"
DB_NAME = "jukebox.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Table Tracks (avec la nouvelle colonne)
    c.execute('''CREATE TABLE IF NOT EXISTS tracks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT, artist TEXT, album TEXT, path TEXT, cover_path TEXT)''')
    
    # Sécurité : Si la table existait sans cover_path, on l'ajoute
    try:
        c.execute("ALTER TABLE tracks ADD COLUMN cover_path TEXT")
    except sqlite3.OperationalError:
        pass # Déjà là, tout va bien

    # 2. Table Playlist
    c.execute('''CREATE TABLE IF NOT EXISTS playlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    position INTEGER NOT NULL)''')

    # 3. Table Shuffled Playlist
    c.execute('''CREATE TABLE IF NOT EXISTS shuffled_playlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER NOT NULL,
                    position INTEGER NOT NULL)''')

    conn.commit()
    return conn


def add_column():
    conn = sqlite3.connect(DB_NAME)
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN cover_path TEXT")
        print("Colonne 'cover_path' ajoutée avec succès.")
    except sqlite3.OperationalError:
        print("La colonne existe déjà.")
    conn.close()

def scan_music():
    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM tracks")
    
    print(f"Scan en cours de {MUSIC_FOLDER}...")
    
    for root, dirs, files in os.walk(MUSIC_FOLDER):
        # --- DÉTECTION DE LA COUVERTURE ---
        # On cherche un fichier image dans le dossier actuel (root)
        current_cover = None
        for f in files:
            if f.lower() in ['cover.jpg', 'cover.png', 'folder.jpg', 'front.jpg']:
                current_cover = os.path.join(root, f)
                break # On prend la première image trouvée

        for file in files:
            if file.endswith(".mp3"):
                full_path = os.path.join(root, file)
                # Initialisation des variables par défaut
                artist = "Artiste Inconnu"
                album = os.path.basename(root)
                title = file

                try:
                    # On tente de lire les tags ID3
                    try:
                        audio = ID3(full_path)
                        artist = str(audio.get('TPE1', ['Artiste Inconnu'])[0])
                        album = str(audio.get('TALB', ['Album Inconnu'])[0])
                        title = str(audio.get('TIT2', [file])[0])
                    except Exception:
                        # Si ID3 échoue (pas de tags), on garde les valeurs par défaut
                        pass
                    
                    # C'est ici qu'on insère, une fois qu'on a soit les tags, soit le défaut
                    c.execute("""INSERT INTO tracks (title, artist, album, path, cover_path) 
                                 VALUES (?, ?, ?, ?, ?)""",
                              (title, artist, album, full_path, current_cover))

                except Exception as e:
                    # Ce except ferme le premier 'try' (celui du haut)
                    print(f"Erreur d'insertion pour {file}: {e}")
    
    conn.commit()
    count = c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    print(f"Scan terminé ! {count} morceaux indexés avec leurs images.")
    conn.close()

if __name__ == "__main__":
    scan_music()