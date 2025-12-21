import os
import sqlite3
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

# --- CONFIGURATION ---
#MUSIC_FOLDER = r"\\192.168.0.3\music\"
MUSIC_FOLDER = r"\\192.168.0.3\music\Ben Harper"
DB_NAME = "jukebox.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # On crée une table simple pour stocker nos morceaux
    c.execute('''CREATE TABLE IF NOT EXISTS tracks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT, artist TEXT, album TEXT, path TEXT)''')
    conn.commit()
    return conn

def scan_music():
    conn = init_db()
    c = conn.cursor()
    # On vide la table pour un scan tout neuf
    c.execute("DELETE FROM tracks")
    
    print(f"Scan en cours de {MUSIC_FOLDER}...")
    
    for root, dirs, files in os.walk(MUSIC_FOLDER):
        for file in files:
            if file.endswith(".mp3"):
                full_path = os.path.join(root, file)
                try:
                    audio = ID3(full_path)
                    # Extraction des tags (on met 'Inconnu' si vide)
                    artist = audio.get('TPE1', ['Artiste Inconnu'])[0]
                    album = audio.get('TALB', ['Album Inconnu'])[0]
                    title = audio.get('TIT2', [file])[0]
                    
                    c.execute("INSERT INTO tracks (title, artist, album, path) VALUES (?, ?, ?, ?)",
                              (str(title), str(artist), str(album), full_path))
                except Exception as e:
                    print(f"Erreur sur {file}: {e}")
    
    conn.commit()
    count = c.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
    print(f"Scan terminé ! {count} morceaux indexés dans {DB_NAME}")
    conn.close()

if __name__ == "__main__":
    scan_music()