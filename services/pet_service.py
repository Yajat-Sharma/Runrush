"""
Pet Service - Business logic for the Virtual Pace Pet feature.
Supports multi-pet collection with a single active pet tracked via is_active = TRUE.
"""

from datetime import datetime, date
from db import get_db, IntegrityError

# Level thresholds — (cumulative_km, level)
# Sorted descending so calculate_level can short-circuit
LEVEL_THRESHOLDS = [
    (100, 5),  # Full Grown
    (60, 4),   # Developing
    (30, 3),   # Growing
    (10, 2),   # Baby
    (0, 1)     # Egg
]

# Per-type stage names (index = level - 1)
LEVEL_NAMES = {
    'dog':    ['Egg', 'Puppy', 'Growing', 'Developing', 'Full Grown'],
    'bird':   ['Egg', 'Chick', 'Growing', 'Developing', 'Full Grown'],
    'dragon': ['Egg', 'Hatchling', 'Young Dragon', 'Adult', 'Full Grown'],
}

# Centralized pet catalog
PET_DEFINITIONS = {
    'dog':    {'name': 'Road Runner',   'description': 'Loyal companion for every trail.',  'unlock_distance': 0},
    'bird':   {'name': 'Sky Dasher',    'description': 'Soars higher with every stride.',   'unlock_distance': None},
    'dragon': {'name': 'Blaze Strider', 'description': 'Forged in the fire of your runs.', 'unlock_distance': None},
}


def calculate_level(total_km):
    """Calculate pet level based on total km fed."""
    for threshold_km, level in LEVEL_THRESHOLDS:
        if total_km >= threshold_km:
            return level
    return 1


def get_level_name(pet_type, level):
    """Get the display name for a pet's current level."""
    names = LEVEL_NAMES.get(pet_type, LEVEL_NAMES['dog'])
    idx = max(0, min(level - 1, len(names) - 1))
    return names[idx]


def get_next_threshold(current_level):
    """Get the km threshold for the next level, or None if max."""
    for threshold_km, lvl in reversed(LEVEL_THRESHOLDS):
        if lvl == current_level + 1:
            return threshold_km
    return None


def get_current_threshold(current_level):
    """Get the km threshold for the current level."""
    for threshold_km, lvl in LEVEL_THRESHOLDS:
        if lvl == current_level:
            return threshold_km
    return 0


def get_active_pet(user_id):
    """
    Returns the user's active pet record, or None.
    """
    conn = get_db()
    pet = conn.execute("SELECT * FROM user_pets WHERE user_id = ? AND is_active = TRUE", (user_id,)).fetchone()
    conn.close()
    if pet:
        return dict(pet)
    return None


def get_pet(user_id):
    """Backward compatibility alias for get_active_pet."""
    return get_active_pet(user_id)


def evaluate_pet_health(user_id):
    """
    Checks days since last_fed_date and updates health_status for the active pet.
    > 7 days = waiting for you
    > 3 days = sleepy
    else = happy
    """
    pet = get_active_pet(user_id)
    if not pet or not pet.get('last_fed_date'):
        return

    if isinstance(pet['last_fed_date'], str):
        last_fed_str = pet['last_fed_date'][:10]
        last_fed = datetime.strptime(last_fed_str, "%Y-%m-%d").date()
    else:
        last_fed = pet['last_fed_date'].date()
        
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
            "UPDATE user_pets SET health_status = ? WHERE id = ?",
            (new_status, pet['id'])
        )
        conn.commit()
        conn.close()


def feed_pet(user_id, distance_km, run_date_str=None):
    """
    Feeds the active pet.
    """
    pet = get_active_pet(user_id)
    if not pet:
        return

    new_total = pet['total_km_fed'] + distance_km
    new_level = calculate_level(new_total)

    today_str = date.today().strftime("%Y-%m-%d")
    feed_date = run_date_str if run_date_str else today_str

    if isinstance(pet.get('last_fed_date'), str):
        current_last_fed = pet['last_fed_date'][:10]
    elif pet.get('last_fed_date'):
        current_last_fed = pet['last_fed_date'].strftime("%Y-%m-%d")
    else:
        current_last_fed = None

    if current_last_fed and feed_date < current_last_fed:
        feed_date = current_last_fed

    conn = get_db()
    conn.execute(
        """
        UPDATE user_pets
        SET total_km_fed = ?,
            level = ?,
            last_fed_date = ?,
            health_status = 'happy'
        WHERE id = ?
        """,
        (new_total, new_level, feed_date, pet['id'])
    )
    conn.commit()
    conn.close()


def remove_km(user_id, distance_km):
    """
    Subtracts distance from the active pet.
    """
    pet = get_active_pet(user_id)
    if not pet:
        return

    new_total = max(0.0, pet['total_km_fed'] - distance_km)
    new_level = calculate_level(new_total)

    conn = get_db()
    conn.execute(
        "UPDATE user_pets SET total_km_fed = ?, level = ? WHERE id = ?",
        (new_total, new_level, pet['id'])
    )
    conn.commit()
    conn.close()


def get_user_collection(user_id):
    """
    Returns all pets in the user's collection.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM user_pets WHERE user_id = ? ORDER BY adopted_at",
        (user_id,)
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d['level_name'] = get_level_name(d['pet_type'], d['level'])
        nt = get_next_threshold(d['level'])
        ct = get_current_threshold(d['level'])
        d['next_threshold'] = nt
        d['current_threshold'] = ct
        if nt:
            d['km_until_next'] = round(max(0.0, nt - d['total_km_fed']), 2)
        else:
            d['km_until_next'] = 0
        result.append(d)
    return result


def switch_active_pet(user_id, pet_id):
    """
    Switch the active pet transactionally.
    """
    conn = get_db()
    try:
        # Verify the pet entry belongs to this user
        row = conn.execute(
            "SELECT id FROM user_pets WHERE id = ? AND user_id = ?",
            (pet_id, user_id)
        ).fetchone()
        
        if not row:
            return False

        # Transactionally deactivate all pets then activate the selected one
        conn.execute("UPDATE user_pets SET is_active = FALSE WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE user_pets SET is_active = TRUE WHERE id = ?", (pet_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error switching active pet: {e}")
        return False
    finally:
        conn.close()


def rename_pet(user_id, pet_id, new_name):
    """
    Rename a pet in the collection.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM user_pets WHERE id = ? AND user_id = ?",
        (pet_id, user_id)
    ).fetchone()
    
    if not row:
        conn.close()
        return False

    conn.execute(
        "UPDATE user_pets SET pet_name = ? WHERE id = ?",
        (new_name, pet_id)
    )
    conn.commit()
    conn.close()
    return True


def get_unlocked_types(total_distance_km):
    """
    Given a user's total lifetime distance, return which pet types are unlocked.
    """
    result = {}
    for pet_type, defn in PET_DEFINITIONS.items():
        unlock_dist = defn.get('unlock_distance')
        if unlock_dist is None:
            result[pet_type] = {
                'unlocked': False,
                'definition': defn,
                'unlock_distance': None,
                'reason': 'Coming soon'
            }
        elif total_distance_km >= unlock_dist:
            result[pet_type] = {
                'unlocked': True,
                'definition': defn,
                'unlock_distance': unlock_dist
            }
        else:
            result[pet_type] = {
                'unlocked': False,
                'definition': defn,
                'unlock_distance': unlock_dist,
                'km_remaining': round(unlock_dist - total_distance_km, 2)
            }
    return result


def adopt_pet(user_id, pet_name, pet_type):
    """
    Adopt a pet into the collection.
    If the user has no active pets, this pet becomes active.
    Returns (True, None) on success, (False, error_msg) on failure.
    """
    return adopt_new_pet(user_id, pet_name, pet_type)


def adopt_new_pet(user_id, pet_name, pet_type):
    """
    Adopt a new pet into the collection.
    Sets it as the active pet transactionally.
    Returns (True, None) on success, (False, error_msg) on failure.
    """
    conn = get_db()
    try:
        # Check if user already has this pet type
        existing = conn.execute(
            "SELECT id FROM user_pets WHERE user_id = ? AND pet_type = ?",
            (user_id, pet_type)
        ).fetchone()
        if existing:
            return False, "You already have this pet type"

        today_str = date.today().strftime("%Y-%m-%d")

        conn.execute(
            """
            INSERT INTO user_pets (user_id, pet_name, pet_type, level, health_status, total_km_fed, last_fed_date, is_active)
            VALUES (?, ?, ?, 1, 'happy', 0.0, ?, FALSE)
            """,
            (user_id, pet_name, pet_type, today_str)
        )
        
        # Get the ID of the newly inserted pet
        new_pet = conn.execute(
            "SELECT id FROM user_pets WHERE user_id = ? AND pet_type = ?",
            (user_id, pet_type)
        ).fetchone()

        if new_pet:
            new_pet_id = new_pet['id'] if isinstance(new_pet, dict) else new_pet[0]
            conn.execute("UPDATE user_pets SET is_active = FALSE WHERE user_id = ?", (user_id,))
            conn.execute("UPDATE user_pets SET is_active = TRUE WHERE id = ?", (new_pet_id,))

        conn.commit()
        return True, None
    except IntegrityError:
        conn.rollback()
        return False, "You already have this pet type"
    except Exception as e:
        conn.rollback()
        print(f"Error adopting new pet: {e}")
        return False, str(e)
    finally:
        conn.close()
