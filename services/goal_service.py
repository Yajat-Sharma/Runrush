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
                user_id,
                g_dict.get('created_at')
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

def generate_training_calendar(target_distance_km, target_date_str, days_per_week, user_id, created_at=None):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    
    if created_at:
        try:
            created_date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            created_date = datetime.strptime(created_at, "%Y-%m-%d").date()
    else:
        created_date = today

    total_days = (target_date - created_date).days
    total_weeks = max(1, math.ceil(total_days / 7.0))
    
    conn = get_db()
    cutoff_date = (created_date - timedelta(weeks=8)).strftime("%Y-%m-%d")
    recent_runs = conn.execute(
        "SELECT distance_km FROM runs WHERE user_id = ? AND date >= ? AND date <= ?",
        (user_id, cutoff_date, created_date.strftime("%Y-%m-%d"))
    ).fetchall()
    
    baseline_km = 0
    if recent_runs:
        baseline_km = max(r['distance_km'] for r in recent_runs)
        
    if baseline_km == 0:
        baseline_km = max(1.0, target_distance_km * 0.1) # Default starting point

    max_training_dist = target_distance_km
    if target_distance_km >= 10.0:
        max_training_dist = target_distance_km * 0.90

    # Generate original linear plan
    planned_targets = []
    for week in range(total_weeks):
        progress = (week + 1) / total_weeks
        long_run_dist = baseline_km + (max_training_dist - baseline_km) * progress
        if week == total_weeks - 1:
            long_run_dist = max_training_dist
        planned_targets.append(long_run_dist)

    # Calculate shortfalls based on elapsed weeks
    total_shortfall = 0.0
    current_week_idx = -1
    actual_max_per_week = []
    
    for week in range(total_weeks):
        week_start = created_date + timedelta(weeks=week)
        week_end = week_start + timedelta(days=6)
        
        if today > week_end:
            # Fully elapsed week
            runs_in_week = conn.execute(
                "SELECT distance_km FROM runs WHERE user_id = ? AND date >= ? AND date <= ?",
                (user_id, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"))
            ).fetchall()
            max_actual = max([r['distance_km'] for r in runs_in_week]) if runs_in_week else 0.0
            actual_max_per_week.append(max_actual)
            
            planned_target = planned_targets[week]
            if max_actual < planned_target:
                total_shortfall += (planned_target - max_actual)
        else:
            # Current or future week
            if current_week_idx == -1:
                current_week_idx = week
            break
            
    conn.close()
    
    remaining_weeks = total_weeks - current_week_idx if current_week_idx != -1 else 0
    is_at_risk = False
    suggested_date_str = None
    
    # Redistribute shortfalls
    final_targets = list(planned_targets)
    undistributed = 0.0
    if total_shortfall > 0 and remaining_weeks > 0:
        shortfall_per_week = total_shortfall / remaining_weeks
        
        # Apply redistribution with 10% safety cap compared to original plan
        for week in range(current_week_idx, total_weeks):
            orig_target = planned_targets[week]
            safe_max = orig_target * 1.10
            
            desired_target = final_targets[week] + shortfall_per_week
            capped_target = min(desired_target, safe_max, max_training_dist)
            
            if desired_target > capped_target:
                undistributed += (desired_target - capped_target)
                
            final_targets[week] = capped_target
            
        # Check if we can still reach the final target or if volume was lost
        if final_targets[-1] < max_training_dist * 0.99 or undistributed > 0:
            is_at_risk = True
            
            # Calculate how many extra weeks we need
            extra_weeks = 0
            if final_targets[-1] < max_training_dist * 0.99:
                current_max = final_targets[-1]
                while current_max < max_training_dist:
                    current_max *= 1.10
                    extra_weeks += 1
            if undistributed > 0:
                # Add weeks based on lost volume (assume we can safely absorb max_training_dist/2 per extra week)
                extra_weeks += max(1, math.ceil(undistributed / (max_training_dist * 0.5)))
            
            new_target_date = target_date + timedelta(weeks=extra_weeks)
            suggested_date_str = new_target_date.strftime("%Y-%m-%d")

    # Build return calendar
    calendar_data = []
    for week in range(total_weeks):
        week_num = week + 1
        week_start = created_date + timedelta(weeks=week)
        week_end = week_start + timedelta(days=6)
        long_run_dist = final_targets[week]
        other_run_dist = long_run_dist * 0.5
        
        is_past = today > week_end
        is_current = week_start <= today <= week_end
        
        actual_val = actual_max_per_week[week] if is_past else None
        
        calendar_data.append({
            "week_number": week_num,
            "date_range": f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}",
            "long_run": round(long_run_dist, 1),
            "other_runs": round(other_run_dist, 1),
            "days_per_week": days_per_week,
            "is_past": is_past,
            "is_current": is_current,
            "actual_long_run": round(actual_val, 1) if actual_val is not None else None
        })
        
    return {
        "weeks": calendar_data,
        "is_at_risk": is_at_risk,
        "suggested_date": suggested_date_str,
        "is_missed": remaining_weeks == 0 and not (today <= target_date),
        "total_shortfall": round(total_shortfall, 1)
    }

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
