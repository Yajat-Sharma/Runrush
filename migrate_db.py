"""
Database migration script to ensure all columns exist in the runs table.
"""
import sqlite3

def migrate_database():
    conn = sqlite3.connect('runs.db')
    cursor = conn.cursor()
    
    # Get current columns
    cursor.execute('PRAGMA table_info(runs)')
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    print(f"Existing columns: {existing_columns}")
    
    # Add created_at if missing
    if 'created_at' not in existing_columns:
        print("Adding created_at column...")
        try:
            cursor.execute('ALTER TABLE runs ADD COLUMN created_at TEXT')
            conn.commit()
            print("✓ created_at column added")
        except sqlite3.OperationalError as e:
            print(f"✗ Error adding created_at: {e}")
    else:
        print("✓ created_at column already exists")
    
    # Add insight if missing
    if 'insight' not in existing_columns:
        print("Adding insight column...")
        try:
            cursor.execute('ALTER TABLE runs ADD COLUMN insight TEXT')
            conn.commit()
            print("✓ insight column added")
        except sqlite3.OperationalError as e:
            print(f"✗ Error adding insight: {e}")
    else:
        print("✓ insight column already exists")
    
    # Verify final schema
    cursor.execute('PRAGMA table_info(runs)')
    print("\nFinal schema:")
    for row in cursor.fetchall():
        print(f"  {row[1]:15} {row[2]:10} (nullable: {not row[3]}, default: {row[4]})")
    
    conn.close()
    print("\n✓ Database migration complete!")

if __name__ == '__main__':
    migrate_database()
