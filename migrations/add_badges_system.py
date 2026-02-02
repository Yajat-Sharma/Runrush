"""
Database migration to add Achievement Badge System.

This script creates:
1. badges table - Badge definitions (static configuration)
2. user_badges table - User's earned badges with unique constraint
3. user_stats table - Denormalized stats for performance optimization

Run this script after deploying to production:
    python migrations/add_badges_system.py
"""

import sqlite3
from datetime import datetime, timedelta, date

DB_PATH = "runs.db"

# Badge definitions
INITIAL_BADGES = [
    {
        'key': 'FIRST_5K',
        'name': 'First 5K',
        'description': 'Completed your first 5km run!',
        'criteria_type': 'SINGLE_DISTANCE',
        'criteria_value': 5.0,
        'icon_url': '/static/badges/5k.png'
    },
    {
        'key': 'TOTAL_50KM',
        'name': '50 KM Warrior',
        'description': 'Ran a total of 50 kilometers!',
        'criteria_type': 'ACCUMULATIVE_DISTANCE',
        'criteria_value': 50.0,
        'icon_url': '/static/badges/50km.png'
    },
    {
        'key': 'TOTAL_100KM',
        'name': '100 KM Champion',
        'description': 'Conquered 100 kilometers total!',
        'criteria_type': 'ACCUMULATIVE_DISTANCE',
        'criteria_value': 100.0,
        'icon_url': '/static/badges/100km.png'
    },
    {
        'key': 'STREAK_7DAY',
        'name': '7-Day Streak',
        'description': 'Ran for 7 consecutive days!',
        'criteria_type': 'STREAK',
        'criteria_value': 7,
        'icon_url': '/static/badges/streak7.png'
    },
    {
        'key': 'STREAK_30DAY',
        'name': '30-Day Streak',
        'description': 'Incredible! 30 days in a row!',
        'criteria_type': 'STREAK',
        'criteria_value': 30,
        'icon_url': '/static/badges/streak30.png'
    },
    {
        'key': 'FIRST_10K',
        'name': 'First 10K',
        'description': 'Completed your first 10km run!',
        'criteria_type': 'SINGLE_DISTANCE',
        'criteria_value': 10.0,
        'icon_url': '/static/badges/10k.png'
    }
]


def migrate():
    """Run the migration."""
    print("🚀 Starting Achievement Badge System migration...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 1. Create badges table
        print("\n📋 Creating 'badges' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                criteria_type TEXT NOT NULL,
                criteria_value REAL NOT NULL,
                icon_url TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on criteria_type for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_badges_criteria 
            ON badges(criteria_type)
        """)
        
        # 2. Create user_badges table
        print("🏆 Creating 'user_badges' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                unlocked_at TEXT NOT NULL,
                activity_id INTEGER,
                UNIQUE(user_id, badge_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (activity_id) REFERENCES runs(id) ON DELETE SET NULL
            )
        """)
        
        # Create index on user_id for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_badges_user 
            ON user_badges(user_id)
        """)
        
        # 3. Create user_stats table
        print("📊 Creating 'user_stats' table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                total_distance_km REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_activity_date TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 4. Insert initial badge definitions
        print("\n🎖️  Inserting badge definitions...")
        for badge in INITIAL_BADGES:
            try:
                cursor.execute("""
                    INSERT INTO badges (key, name, description, criteria_type, criteria_value, icon_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    badge['key'],
                    badge['name'],
                    badge['description'],
                    badge['criteria_type'],
                    badge['criteria_value'],
                    badge['icon_url']
                ))
                print(f"  ✓ {badge['name']}")
            except sqlite3.IntegrityError:
                print(f"  ⚠ {badge['name']} already exists, skipping...")
        
        # 5. Initialize user_stats for existing users
        print("\n👥 Initializing stats for existing users...")
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()
        
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        for user_row in users:
            user_id = user_row[0]
            
            # Check if stats already exist
            existing = cursor.execute(
                "SELECT user_id FROM user_stats WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            
            if existing:
                print(f"  ⚠ Stats for user {user_id} already exist, skipping...")
                continue
            
            # Calculate initial stats from existing runs
            runs = cursor.execute(
                "SELECT date, distance_km FROM runs WHERE user_id = ? ORDER BY date ASC",
                (user_id,)
            ).fetchall()
            
            if not runs:
                # User has no runs yet
                cursor.execute("""
                    INSERT INTO user_stats (user_id, total_distance_km, current_streak, best_streak, updated_at)
                    VALUES (?, 0.0, 0, 0, ?)
                """, (user_id, now_str))
                print(f"  ✓ User {user_id}: No runs yet")
                continue
            
            # Calculate total distance
            total_distance = sum(run[1] for run in runs)
            
            # Calculate streaks
            all_dates = []
            for run in runs:
                try:
                    d = datetime.strptime(run[0], "%Y-%m-%d").date()
                    all_dates.append(d)
                except:
                    continue
            
            all_dates = sorted(list(set(all_dates)))  # unique + sorted
            
            # Current streak
            current_streak = 0
            today = date.today()
            day_pointer = today
            
            while day_pointer in all_dates:
                current_streak += 1
                day_pointer = day_pointer - timedelta(days=1)
            
            # Best streak
            best_streak = 0
            streak = 1
            for i in range(1, len(all_dates)):
                if all_dates[i] == all_dates[i-1] + timedelta(days=1):
                    streak += 1
                else:
                    best_streak = max(best_streak, streak)
                    streak = 1
            best_streak = max(best_streak, streak)
            
            last_activity_date = all_dates[-1].strftime("%Y-%m-%d") if all_dates else None
            
            # Insert stats
            cursor.execute("""
                INSERT INTO user_stats (
                    user_id, total_distance_km, current_streak, best_streak, 
                    last_activity_date, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, total_distance, current_streak, best_streak, last_activity_date, now_str))
            
            print(f"  ✓ User {user_id}: {total_distance:.1f}km total, {current_streak} day streak")
        
        conn.commit()
        
        print("\n✅ Migration completed successfully!")
        print("\n📈 Summary:")
        
        badge_count = cursor.execute("SELECT COUNT(*) FROM badges").fetchone()[0]
        user_count = cursor.execute("SELECT COUNT(*) FROM user_stats").fetchone()[0]
        
        print(f"  • {badge_count} badges defined")
        print(f"  • {user_count} users initialized")
        print("\n🎉 Achievement system is ready!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
