import sqlite3
import uuid

db_id = str(uuid.uuid4())
db_path = f"file:{db_id}?mode=memory&cache=shared"

# Keepalive connection
conn1 = sqlite3.connect(db_path, uri=True)
conn1.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
conn1.commit()

# Route connection
conn2 = sqlite3.connect(db_path, uri=True)
res = conn2.execute("SELECT * FROM users").fetchall()
print("First query:", res)
conn2.close()

# Second route connection
conn3 = sqlite3.connect(db_path, uri=True)
try:
    res = conn3.execute("SELECT * FROM users").fetchall()
    print("Second query:", res)
except Exception as e:
    print("Error:", repr(e))
