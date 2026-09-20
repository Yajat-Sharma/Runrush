import sqlite3
import sys

def apply_sql():
    conn = sqlite3.connect('runs.db')
    with open('migrations/004_add_monthly_goals.sql', 'r') as f:
        sql = f.read()
    conn.executescript(sql)
    conn.commit()
    conn.close()
    print("Migration applied successfully")

if __name__ == '__main__':
    apply_sql()
