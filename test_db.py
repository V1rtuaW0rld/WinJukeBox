import sqlite3
conn = sqlite3.connect("jukebox.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables trouvées :", cur.fetchall())
conn.close()