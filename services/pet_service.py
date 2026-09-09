"""
Pet Service - Business logic for the Virtual Pace Pet feature.
"""

from datetime import datetime, date
from db import get_db

# Level thresholds
LEVEL_THRESHOLDS = [
    (100, 5),
    (50, 4),
    (25, 3),
    (10, 2),
    (0, 1)
]

def calculate_level(total_km):
    """Calculate pet level based on total km fed."""
    for threshold_km, level in LEVEL_THRESHOLDS:
        if total_km >= threshold_km:
            return level
    return 1

def get_pet(user_id):
    """
    Returns the user's pet record, or None if they haven't adopted one.
    """
    conn = get_db()
    pet = conn.execute("SELECT * FROM user_pets WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    if pet:
        # Convert to dict to allow mutation
        return dict(pet)
    return None

def evaluate_pet_health(user_id):
    """
    Checks days since last_fed_date and updates health_status.
    > 7 days = waiting for you
    > 3 days = sleepy
    else = happy
    """
    pet = get_pet(user_id)
    if not pet or not pet.get('last_fed_date'):
        return

    last_fed_str = pet['last_fed_date'][:10] # YYYY-MM-DD
    last_fed = datetime.strptime(last_fed_str, "%Y-%m-%d").date()
    today = date.today()
    
    days_since = (today - last_fed).days
    
    if days_since > 7:
        new_status = "waiting for you"
    elif days_since > 3:
        new_status = "sleepy"
    else:
        new_status = "happy"
        
    if new_status != pet['health_status']:
        conn = get_db()
        conn.execute(
            "UPDATE user_pets SET health_status = ? WHERE user_id = ?",
            (new_status, user_id)
        )
        conn.commit()
        conn.close()

def feed_pet(user_id, distance_km, run_date_str=None):
    """
    Adds distance to total_km_fed and updates last_fed_date.
    Checks and updates level.
    """
    pet = get_pet(user_id)
    if not pet:
        return
    
    new_total = pet['total_km_fed'] + distance_km
    new_level = calculate_level(new_total)
    
    # We use today as last_fed_date unless the run is in the past,
    # but generally just updating it to today is good. We can use run_date_str if provided.
    today_str = date.today().strftime("%Y-%m-%d")
    feed_date = run_date_str if run_date_str else today_str
    
    # Only update last_fed_date if the run date is newer than existing
    current_last_fed = pet.get('last_fed_date')
    if current_last_fed and feed_date < current_last_fed:
        feed_date = current_last_fed # Don't regress the fed date

    conn = get_db()
    conn.execute(
        """
        UPDATE user_pets
        SET total_km_fed = ?,
            level = ?,
            last_fed_date = ?,
            health_status = 'happy'
        WHERE user_id = ?
        """,
        (new_total, new_level, feed_date, user_id)
    )
    conn.commit()
    conn.close()

def remove_km(user_id, distance_km):
    """
    Subtracts distance from total_km_fed (used when a run is edited or deleted).
    """
    pet = get_pet(user_id)
    if not pet:
        return
        
    new_total = max(0.0, pet['total_km_fed'] - distance_km)
    new_level = calculate_level(new_total)
    
    conn = get_db()
    conn.execute(
        """
        UPDATE user_pets
        SET total_km_fed = ?,
            level = ?
        WHERE user_id = ?
        """,
        (new_total, new_level, user_id)
    )
    conn.commit()
    conn.close()

def adopt_pet(user_id, pet_name, pet_type):
    """
    Creates a new pet for the user.
    """
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO user_pets (user_id, pet_name, pet_type, level, health_status, total_km_fed, last_fed_date)
            VALUES (?, ?, ?, 1, 'happy', 0.0, ?)
            """,
            (user_id, pet_name, pet_type, date.today().strftime("%Y-%m-%d"))
        )
        conn.commit()
    except Exception as e:
        print(f"Error adopting pet: {e}")
    finally:
        conn.close()
