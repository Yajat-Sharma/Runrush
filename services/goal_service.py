import math
from datetime import datetime, timedelta

from db import get_db

# Hard minimums for Layer 1
LAYER_1_MINIMUMS = {
    3: 2,
    5: 4,
    10: 8,
    21: 10,
    42: 16,
    100: 24
}

def get_user_goals(user_id):
    conn = get_db()
    goals = conn.execute("SELECT * FROM user_goals WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    
    result = []
    for g in goals:
        g_dict = dict(g)
        if g_dict['status'] == 'active':
            g_dict['calendar'] = generate_training_calendar(
                g_dict['target_distance_km'], 
                g_dict['target_date'], 
                g_dict['days_per_week'],
                user_id
            )
        result.append(g_dict)
    return result

def check_goal_feasibility(user_id, target_distance_km, target_date_str, days_per_week):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    weeks_available = (target_date - today).days / 7.0

    # Layer 1: Hard floor minimums
    floor_weeks = 0
    # Find the nearest standard distance for Layer 1 checks
    for dist in sorted(LAYER_1_MINIMUMS.keys(), reverse=True):
        if target_distance_km >= dist:
            floor_weeks = LAYER_1_MINIMUMS[dist]
            break
            
    # Layer 2: Baseline and 10% rule
    conn = get_db()
    cutoff_date = (today - timedelta(weeks=8)).strftime("%Y-%m-%d")
    recent_runs = conn.execute(
        "SELECT distance_km FROM runs WHERE user_id = ? AND date >= ?",
        (user_id, cutoff_date)
    ).fetchall()
    conn.close()

    baseline_km = 0
    if recent_runs:
        max_single = max(r['distance_km'] for r in recent_runs)
        total_dist = sum(r['distance_km'] for r in recent_runs)
        avg_weekly = total_dist / 8.0  # simple avg over 8 weeks
        baseline_km = max(max_single, avg_weekly)

    weeks_needed = 0
    if baseline_km > 0 and target_distance_km > baseline_km:
        weeks_needed = math.log(target_distance_km / baseline_km) / math.log(1.10)

    # Adjust weeks needed based on days_per_week
    if days_per_week <= 2:
        weeks_needed *= 1.5
    elif days_per_week == 3:
        weeks_needed *= 1.15
        
    required_weeks = max(floor_weeks, math.ceil(weeks_needed))

    if weeks_available >= required_weeks:
        return True, None
    else:
        suggested_date = (today + timedelta(weeks=required_weeks)).strftime("%Y-%m-%d")
        message = "Even Olympic athletes need more time than that! Let's aim for something a bit more achievable."
        if required_weeks > 10:
            message = "That's a big jump! To avoid injury, we recommend taking a bit more time to build up."
            
        return False, {
            "message": message,
            "suggested_date": suggested_date
        }

def generate_training_calendar(target_distance_km, target_date_str, days_per_week, user_id):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    
    total_days = (target_date - today).days
    total_weeks = max(1, math.ceil(total_days / 7.0))
    
    conn = get_db()
    cutoff_date = (today - timedelta(weeks=8)).strftime("%Y-%m-%d")
    recent_runs = conn.execute(
        "SELECT distance_km FROM runs WHERE user_id = ? AND date >= ?",
        (user_id, cutoff_date)
    ).fetchall()
    conn.close()

    baseline_km = 0
    if recent_runs:
        baseline_km = max(r['distance_km'] for r in recent_runs)
        
    if baseline_km == 0:
        baseline_km = max(1.0, target_distance_km * 0.1) # Default starting point

    calendar = []
    
    # Linearly interpolate long run distance from baseline to target over the weeks
    for week in range(total_weeks):
        week_num = week + 1
        
        # Calculate progress ratio
        progress = (week + 1) / total_weeks
        
        long_run_dist = baseline_km + (target_distance_km - baseline_km) * progress
        
        # Smooth out the final week to just be the target distance
        if week == total_weeks - 1:
            long_run_dist = target_distance_km
            
        other_run_dist = long_run_dist * 0.5
        
        week_start = today + timedelta(weeks=week)
        week_end = week_start + timedelta(days=6)
        
        calendar.append({
            "week_number": week_num,
            "date_range": f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}",
            "long_run": round(long_run_dist, 1),
            "other_runs": round(other_run_dist, 1),
            "days_per_week": days_per_week
        })
        
    return calendar

def evaluate_goals_for_user(user_id, run_id=None):
    """
    Hook called when a run is logged, edited, or deleted.
    SINGLE RUN COMPLETION: Completes if ANY single run >= target_distance_km.
    """
    conn = get_db()
    
    active_goals = conn.execute(
        "SELECT * FROM user_goals WHERE user_id = ? AND status = 'active'",
        (user_id,)
    ).fetchall()
    
    if not active_goals:
        conn.close()
        return

    # To accurately handle edits/deletes, check if user HAS any single run >= target distance
    # within the goal period (after created_at).
    for goal in active_goals:
        qualifying_run = conn.execute(
            "SELECT id FROM runs WHERE user_id = ? AND distance_km >= ? AND date >= substr(?, 1, 10)",
            (user_id, goal['target_distance_km'], goal['created_at'])
        ).fetchone()
        
        if qualifying_run:
            conn.execute(
                "UPDATE user_goals SET status = 'completed' WHERE id = ?",
                (goal['id'],)
            )
    
    # We must also re-evaluate completed goals in case the run that qualified them was deleted/edited down
    completed_goals = conn.execute(
        "SELECT * FROM user_goals WHERE user_id = ? AND status = 'completed'",
        (user_id,)
    ).fetchall()
    
    for goal in completed_goals:
        qualifying_run = conn.execute(
            "SELECT id FROM runs WHERE user_id = ? AND distance_km >= ? AND date >= substr(?, 1, 10)",
            (user_id, goal['target_distance_km'], goal['created_at'])
        ).fetchone()
        
        if not qualifying_run:
            conn.execute(
                "UPDATE user_goals SET status = 'active' WHERE id = ?",
                (goal['id'],)
            )
            
    conn.commit()
    conn.close()
