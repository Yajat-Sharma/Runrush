"""
Pet Service - Business logic for the Virtual Pace Pet feature.
Supports multi-pet collection with single active_pet_id tracking.
"""

from datetime import datetime, date
from db import get_db

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
# unlock_distance = None means TBD / not yet unlockable
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


# ─── Legacy single-pet functions (backward compat) ───

def get_pet(user_id):
    """
    Returns the user's pet record from user_pets, or None.
    Legacy function — kept for backward compatibility.
    """
    conn = get_db()
    pet = conn.execute("SELECT * FROM user_pets WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if pet:
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

    last_fed_str = pet['last_fed_date'][:10]
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
    Feeds ALL pets in the user's collection (since progression is lifetime-distance based).
    Also updates the legacy user_pets row.
    """
    pet = get_pet(user_id)
    if not pet:
        return

    # Update legacy user_pets row
    new_total = pet['total_km_fed'] + distance_km
    new_level = calculate_level(new_total)

    today_str = date.today().strftime("%Y-%m-%d")
    feed_date = run_date_str if run_date_str else today_str

    current_last_fed = pet.get('last_fed_date')
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
        WHERE user_id = ?
        """,
        (new_total, new_level, feed_date, user_id)
    )

    # Also feed active collection pet
    if pet.get('active_pet_id'):
        cp = conn.execute("SELECT id, total_km_fed FROM user_pet_collection WHERE id = ?", (pet['active_pet_id'],)).fetchone()
        if cp:
            cp_new_total = cp['total_km_fed'] + distance_km
            cp_new_level = calculate_level(cp_new_total)
            conn.execute(
                "UPDATE user_pet_collection SET total_km_fed = ?, level = ? WHERE id = ?",
                (cp_new_total, cp_new_level, cp['id'])
            )

    conn.commit()
    conn.close()


def remove_km(user_id, distance_km):
    """
    Subtracts distance from all pets (used when a run is edited or deleted).
    """
    pet = get_pet(user_id)
    if not pet:
        return

    new_total = max(0.0, pet['total_km_fed'] - distance_km)
    new_level = calculate_level(new_total)

    conn = get_db()
    conn.execute(
        "UPDATE user_pets SET total_km_fed = ?, level = ? WHERE user_id = ?",
        (new_total, new_level, user_id)
    )

    # Also remove from active collection pet
    if pet.get('active_pet_id'):
        cp = conn.execute("SELECT id, total_km_fed FROM user_pet_collection WHERE id = ?", (pet['active_pet_id'],)).fetchone()
        if cp:
            cp_new_total = max(0.0, cp['total_km_fed'] - distance_km)
            cp_new_level = calculate_level(cp_new_total)
            conn.execute(
                "UPDATE user_pet_collection SET total_km_fed = ?, level = ? WHERE id = ?",
                (cp_new_total, cp_new_level, cp['id'])
            )

    conn.commit()
    conn.close()


def adopt_pet(user_id, pet_name, pet_type):
    """
    Creates a new pet for the user (legacy user_pets row).
    Also creates the collection entry and sets it as active.
    """
    conn = get_db()
    try:
        today_str = date.today().strftime("%Y-%m-%d")

        # Insert legacy row if not exists
        existing = conn.execute("SELECT user_id FROM user_pets WHERE user_id = ?", (user_id,)).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO user_pets (user_id, pet_name, pet_type, level, health_status, total_km_fed, last_fed_date)
                VALUES (?, ?, ?, 1, 'happy', 0.0, ?)
                """,
                (user_id, pet_name, pet_type, today_str)
            )

        # Insert collection entry
        conn.execute(
            """
            INSERT INTO user_pet_collection (user_id, pet_name, pet_type, total_km_fed, level, adopted_at)
            VALUES (?, ?, ?, 0.0, 1, ?)
            """,
            (user_id, pet_name, pet_type, today_str)
        )

        # Get the new collection row id
        new_pet = conn.execute(
            "SELECT id FROM user_pet_collection WHERE user_id = ? AND pet_type = ?",
            (user_id, pet_type)
        ).fetchone()

        if new_pet:
            conn.execute(
                "UPDATE user_pets SET active_pet_id = ? WHERE user_id = ?",
                (new_pet['id'], user_id)
            )

        conn.commit()
    except Exception as e:
        print(f"Error adopting pet: {e}")
    finally:
        conn.close()


# ─── Collection-aware functions ───

def get_active_pet(user_id):
    """
    Returns the active pet from the collection, determined by
    user_pets.active_pet_id -> user_pet_collection.id.
    Returns dict or None.
    """
    conn = get_db()
    row = conn.execute(
        """
        SELECT c.*, up.health_status, up.last_fed_date
        FROM user_pets up
        JOIN user_pet_collection c ON c.id = up.active_pet_id
        WHERE up.user_id = ?
        """,
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_collection(user_id):
    """
    Returns all pets in the user's collection.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM user_pet_collection WHERE user_id = ? ORDER BY adopted_at",
        (user_id,)
    ).fetchall()

    # Also get active_pet_id
    up = conn.execute(
        "SELECT active_pet_id FROM user_pets WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    active_id = up['active_pet_id'] if up else None
    result = []
    for r in rows:
        d = dict(r)
        d['is_active'] = (d['id'] == active_id)
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


def switch_active_pet(user_id, collection_id):
    """
    Switch the active pet by updating user_pets.active_pet_id.
    Single source of truth — one field, one query.
    Returns True on success, False if collection_id doesn't belong to user.
    """
    conn = get_db()
    # Verify the collection entry belongs to this user
    row = conn.execute(
        "SELECT id FROM user_pet_collection WHERE id = ? AND user_id = ?",
        (collection_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return False

    # Also update legacy user_pets name/type to match the new active pet
    pet_row = conn.execute(
        "SELECT pet_name, pet_type, total_km_fed, level FROM user_pet_collection WHERE id = ?",
        (collection_id,)
    ).fetchone()

    conn.execute(
        """
        UPDATE user_pets
        SET active_pet_id = ?, pet_name = ?, pet_type = ?, total_km_fed = ?, level = ?
        WHERE user_id = ?
        """,
        (collection_id, pet_row['pet_name'], pet_row['pet_type'],
         pet_row['total_km_fed'], pet_row['level'], user_id)
    )
    conn.commit()
    conn.close()
    return True


def rename_pet(user_id, collection_id, new_name):
    """
    Rename a pet in the collection.
    If it's the active pet, also update legacy user_pets.pet_name.
    """
    conn = get_db()
    # Verify ownership
    row = conn.execute(
        "SELECT id FROM user_pet_collection WHERE id = ? AND user_id = ?",
        (collection_id, user_id)
    ).fetchone()
    if not row:
        conn.close()
        return False

    conn.execute(
        "UPDATE user_pet_collection SET pet_name = ? WHERE id = ?",
        (new_name, collection_id)
    )

    # If this is the active pet, also update legacy row
    up = conn.execute(
        "SELECT active_pet_id FROM user_pets WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    if up and up['active_pet_id'] == collection_id:
        conn.execute(
            "UPDATE user_pets SET pet_name = ? WHERE user_id = ?",
            (new_name, user_id)
        )

    conn.commit()
    conn.close()
    return True


def get_unlocked_types(total_distance_km):
    """
    Given a user's total lifetime distance, return which pet types are unlocked.
    Returns dict: {pet_type: {'unlocked': bool, 'definition': {...}, 'unlock_distance': ...}}
    """
    result = {}
    for pet_type, defn in PET_DEFINITIONS.items():
        unlock_dist = defn.get('unlock_distance')
        if unlock_dist is None:
            # TBD — treat as locked
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


def adopt_new_pet(user_id, pet_name, pet_type):
    """
    Adopt a new pet into the collection (for users who already have a pet).
    Sets it as the active pet.
    Returns (True, None) on success, (False, error_msg) on failure.
    """
    conn = get_db()
    try:
        # Check if user already has this pet type
        existing = conn.execute(
            "SELECT id FROM user_pet_collection WHERE user_id = ? AND pet_type = ?",
            (user_id, pet_type)
        ).fetchone()
        if existing:
            conn.close()
            return False, "You already have this pet type"

        today_str = date.today().strftime("%Y-%m-%d")

        # A new pet always starts at 0.0 KM
        current_km = 0.0
        current_level = 1

        conn.execute(
            """
            INSERT INTO user_pet_collection (user_id, pet_name, pet_type, total_km_fed, level, adopted_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, pet_name, pet_type, current_km, current_level, today_str)
        )

        # Get the new row id and set as active
        new_pet = conn.execute(
            "SELECT id FROM user_pet_collection WHERE user_id = ? AND pet_type = ?",
            (user_id, pet_type)
        ).fetchone()

        if new_pet:
            existing_up = conn.execute("SELECT user_id FROM user_pets WHERE user_id = ?", (user_id,)).fetchone()
            if not existing_up:
                conn.execute(
                    """
                    INSERT INTO user_pets (user_id, pet_name, pet_type, level, health_status, total_km_fed, last_fed_date, active_pet_id)
                    VALUES (?, ?, ?, ?, 'happy', ?, ?, ?)
                    """,
                    (user_id, pet_name, pet_type, current_level, current_km, today_str, new_pet['id'])
                )
            else:
                conn.execute(
                    """
                    UPDATE user_pets
                    SET active_pet_id = ?, pet_name = ?, pet_type = ?,
                        total_km_fed = ?, level = ?
                    WHERE user_id = ?
                    """,
                    (new_pet['id'], pet_name, pet_type, current_km, current_level, user_id)
                )

        conn.commit()
        conn.close()
        return True, None
    except Exception as e:
        print(f"Error adopting new pet: {e}")
        conn.close()
        return False, str(e)
