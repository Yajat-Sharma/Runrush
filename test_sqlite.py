import sqlite3
conn = sqlite3.connect(':memory:')
conn.row_factory = sqlite3.Row
conn.execute('CREATE TABLE t (id INT, name TEXT)')
conn.execute('INSERT INTO t VALUES (1, ''foo'')')
rows = conn.execute('SELECT * FROM t').fetchall()
conn.close()
print(rows[0]['name'])
