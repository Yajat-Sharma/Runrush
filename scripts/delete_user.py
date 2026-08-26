import os
import sqlite3
try:
    import psycopg2
except ImportError:
    psycopg2 = None

def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if not psycopg2:
            print("Error: psycopg2-binary is required to connect to PostgreSQL.")
            exit(1)
        print("Connecting to PostgreSQL (Production)...")
        conn = psycopg2.connect(db_url)
    else:
        print("Connecting to SQLite (Local)...")
        conn = sqlite3.connect("runs.db")
        conn.row_factory = sqlite3.Row
    return conn

def list_users(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, username, display_name FROM users ORDER BY id ASC")
    users = cur.fetchall()
    
    print("\n--- Current Users ---")
    print(f"{'ID':<5} | {'Username':<20} | {'Display Name'}")
    print("-" * 50)
    for u in users:
        # Handle dict-like row access for both psycopg2 and sqlite3
        uid = u[0]
        uname = u[1]
        dname = u[2] or "None"
        print(f"{uid:<5} | {uname:<20} | {dname}")
    print("-" * 50)
    cur.close()

def delete_user(conn, user_id):
    cur = conn.cursor()
    # Delete associated runs first to avoid foreign key constraints (if any)
    cur.execute("DELETE FROM runs WHERE user_id = %s" if os.environ.get("DATABASE_URL") else "DELETE FROM runs WHERE user_id = ?", (user_id,))
    deleted_runs = cur.rowcount
    
    # Delete the user
    cur.execute("DELETE FROM users WHERE id = %s" if os.environ.get("DATABASE_URL") else "DELETE FROM users WHERE id = ?", (user_id,))
    deleted_users = cur.rowcount
    
    conn.commit()
    cur.close()
    
    if deleted_users > 0:
        print(f"✅ Successfully deleted user ID {user_id} and {deleted_runs} associated runs.")
    else:
        print(f"⚠️ User ID {user_id} not found.")

if __name__ == "__main__":
    conn = get_connection()
    try:
        while True:
            list_users(conn)
            choice = input("\nEnter the ID of the user you want to delete (or type 'q' to quit): ").strip()
            
            if choice.lower() == 'q':
                break
                
            if not choice.isdigit():
                print("Please enter a valid numeric ID.")
                continue
                
            user_id = int(choice)
            confirm = input(f"Are you sure you want to permanently delete user ID {user_id}? (y/n): ").strip().lower()
            
            if confirm == 'y':
                delete_user(conn, user_id)
            else:
                print("Deletion cancelled.")
    finally:
        conn.close()
        print("Database connection closed.")
