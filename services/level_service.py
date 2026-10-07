"""
Level service - distance-only rank ladder (Nike Run Club style).

A runner's level is derived purely from their lifetime kilometres, summed from
the runs table. Nothing is stored, so edits, deletes and bulk imports can never
leave a level out of sync.
"""

from db import get_db

# (level, title, Font Awesome icon, colour, minimum lifetime km)
LEVELS = [
    (1,  "Couch Starter",   "fa-shoe-prints",        "#94A3B8", 0),
    (2,  "Jogger",          "fa-person-walking",     "#F5C242", 25),
    (3,  "Strider",         "fa-person-running",     "#84CC16", 75),
    (4,  "Pacer",           "fa-gauge-high",         "#22C55E", 150),
    (5,  "Road Warrior",    "fa-road",               "#14B8A6", 300),
    (6,  "Tempo Titan",     "fa-bolt",               "#F97316", 500),
    (7,  "Marathoner",      "fa-medal",              "#1683F7", 800),
    (8,  "Ultra Runner",    "fa-mountain",           "#8B5CF6", 1200),
    (9,  "Elite",           "fa-gem",                "#EC4899", 2000),
    (10, "RunRush Legend",  "fa-crown",              "#EAB308", 3500),
]


def _entry(index):
    level, title, icon, color, min_km = LEVELS[index]
    return {"level": level, "title": title, "icon": icon, "color": color, "min_km": min_km}


def level_for_km(total_km):
    """Return the ladder entry for a lifetime distance (negative/None -> level 1)."""
    total = float(total_km or 0)
    index = 0
    for i, (_, _, _, _, min_km) in enumerate(LEVELS):
        if total >= min_km:
            index = i
    return _entry(index)


def level_info(total_km):
    """Full level snapshot: current level, progress to the next, and the next level."""
    total = max(0.0, float(total_km or 0))
    current = level_for_km(total)
    index = current["level"] - 1
    nxt = _entry(index + 1) if index + 1 < len(LEVELS) else None

    if nxt:
        span = nxt["min_km"] - current["min_km"]
        progress = (total - current["min_km"]) / span if span else 1.0
        km_to_next = round(nxt["min_km"] - total, 1)
    else:
        progress, km_to_next = 1.0, 0.0

    info = dict(current)
    info.update({
        "total_km": round(total, 1),
        "progress": round(min(1.0, max(0.0, progress)), 4),
        "km_to_next": km_to_next,
        "next": nxt,
        "is_max": nxt is None,
    })
    return info


def get_total_km(user_id):
    """Lifetime kilometres for a user, summed from their runs."""
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(distance_km), 0) AS total FROM runs WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return float(row["total"] or 0)


def detect_level_up(km_before, km_after):
    """
    Return the new level entry if the runner crossed into a higher level
    (the highest one reached when several are skipped at once), else None.
    """
    before = level_for_km(km_before)
    after = level_for_km(km_after)
    return after if after["level"] > before["level"] else None


def ladder():
    """The full ladder for the 'all ranks' sheet."""
    return [_entry(i) for i in range(len(LEVELS))]
