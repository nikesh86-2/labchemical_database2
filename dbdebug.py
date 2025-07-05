import sqlite3
DB_FILE = "chemical_inventory.db"
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("SELECT id, name, cas_number FROM Chemicals ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
