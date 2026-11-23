import json
import math
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from db import get_db

def parse_date_safe(val, default=None):
    if val is None:
        return default
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return default
    s = s.split()[0].split('T')[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return default

# Hard minimums for Layer 1
LAYER_1_MINIMUMS = {
    3: 2,
    5: 4,
    10: 8,
    21: 10,
    42: 16,
    100: 24
}

# Inactivity Cancellation Threshold (14 days = 2 weeks of missing all runs)
INACTIVITY_DAYS_THRESHOLD = 14

def check_and_cancel_inactive_goals(
    user_id: Optional[int] = None,
    inactivity_days: int = INACTIVITY_DAYS_THRESHOLD,
    conn = None
) -> List[Dict[str, Any]]:
    """
    Checks active running plans / goals. If a runner has not logged any runs for
    `inactivity_days` (default: 14 days / 2 weeks), the plan is automatically cancelled,
    dashboard pinning is revoked, and an in-app notification is dispatched alerting the user.
    """
    should_close = False
    if conn is None:
        conn = get_db()
        should_close = True

    today = datetime.now().date()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    query = "SELECT * FROM user_goals WHERE status = 'active'"
    params = []
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)

    active_goals = conn.execute(query, tuple(params)).fetchall()
    cancelled_goals = []

    for g_row in active_goals:
        g = dict(g_row)
        g_id = g["id"]
        uid = g["user_id"]
        goal_created_str = g.get("created_at")
        goal_created_date = parse_date_safe(goal_created_str, today)
        race_name = g.get("race_name") or f"{g.get('target_distance_km')} km Race"

        # Find the latest run date for this user on or after the goal creation date
        run_row = conn.execute(
            "SELECT MAX(date) as last_run_date FROM runs WHERE user_id = ? AND date >= ?",
            (uid, goal_created_date.strftime("%Y-%m-%d"))
        ).fetchone()

        last_activity_date = None
        if run_row and run_row["last_run_date"]:
            last_activity_date = parse_date_safe(run_row["last_run_date"])

        # If no runs were logged since goal creation, inactivity counts from goal creation date
        if not last_activity_date:
            last_activity_date = goal_created_date

        days_inactive = (today - last_activity_date).days
        weeks_inactive = max(1, round(days_inactive / 7.0, 1))

        if days_inactive >= inactivity_days:
            # 1. Update user_goals status
            conn.execute(
                "UPDATE user_goals SET status = 'cancelled', dashboard_pinned = 0 WHERE id = ?",
                (g_id,)
            )

            # 2. Update ai_plan_json with cancellation audit
            ai_plan_raw = g.get("ai_plan_json")
            if ai_plan_raw:
                try:
                    plan_obj = json.loads(ai_plan_raw)
                    plan_obj["cancellation_reason"] = f"Cancelled due to {weeks_inactive} weeks ({days_inactive} days) of inactivity."
                    plan_obj["cancelled_at"] = now_str
                    conn.execute(
                        "UPDATE user_goals SET ai_plan_json = ? WHERE id = ?",
                        (json.dumps(plan_obj), g_id)
                    )
                except Exception:
                    pass

            # 3. Create Notification in notifications & user_notifications
            notif_title = "Training Plan Cancelled"
            notif_msg = (
                f"Your {race_name} training plan was cancelled due to {int(weeks_inactive)} weeks of inactivity "
                f"with no logged workouts. Whenever you're ready to start training again, Rumi AI can build you a fresh plan! 👟"
            )
            try:
                from db import USE_PG
                if USE_PG:
                    n_cur = conn.execute(
                        "INSERT INTO notifications (title, message, type, created_by, audience_type, created_at) "
                        "VALUES (?, ?, 'PLAN_CANCELLED', ?, 'SPECIFIC_USER', ?) RETURNING id",
                        (notif_title, notif_msg, uid, now_str)
                    )
                    notif_id = n_cur.fetchone()["id"]
                else:
                    n_cur = conn.execute(
                        "INSERT INTO notifications (title, message, type, created_by, audience_type, created_at) "
                        "VALUES (?, ?, 'PLAN_CANCELLED', ?, 'SPECIFIC_USER', ?)",
                        (notif_title, notif_msg, uid, now_str)
                    )
                    notif_id = n_cur.lastrowid

                conn.execute(
                    "INSERT INTO user_notifications (notification_id, user_id, delivered_at) VALUES (?, ?, ?)",
                    (notif_id, uid, now_str)
                )
            except Exception as n_err:
                print(f"[RunRush] Inactivity cancellation notification warning: {n_err}")

            cancelled_goals.append({
                "goal_id": g_id,
                "user_id": uid,
                "race_name": race_name,
                "days_inactive": days_inactive,
                "weeks_inactive": weeks_inactive,
                "last_activity_date": last_activity_date.strftime("%Y-%m-%d")
            })

    if cancelled_goals:
        conn.commit()

    if should_close:
        conn.close()

    return cancelled_goals

def get_user_goals(user_id):
    # Automatically evaluate active goals for inactivity cancellation
    try:
        check_and_cancel_inactive_goals(user_id=user_id)
    except Exception as exc:
        print(f"[get_user_goals] Inactivity check warning: {exc}")

    # Reconcile any unlinked runs with active plan workouts
    try:
        reconcile_and_match_recent_runs_for_plan(user_id=user_id)
    except Exception as exc:
        print(f"[get_user_goals] Reconcile runs warning: {exc}")

    conn = get_db()
    goals = conn.execute("SELECT * FROM user_goals WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    conn.close()
    
    result = []
    for g in goals:
        g_dict = dict(g)
        g_dict['dashboard_pinned'] = bool(g_dict.get('dashboard_pinned'))
        
        # Ensure target_date is formatted as clean YYYY-MM-DD string for frontend
        if g_dict.get('target_date'):
            td_parsed = parse_date_safe(g_dict['target_date'])
            if td_parsed:
                g_dict['target_date'] = td_parsed.strftime("%Y-%m-%d")

        # Parse AI plan JSON if present
        if g_dict.get('ai_plan_json'):
            try:
                g_dict['ai_plan'] = json.loads(g_dict['ai_plan_json'])
            except Exception:
                g_dict['ai_plan'] = None
        else:
            g_dict['ai_plan'] = None

        if g_dict['status'] == 'active':
            try:
                g_dict['calendar'] = generate_training_calendar(
                    g_dict['target_distance_km'], 
                    g_dict['target_date'], 
                    g_dict['days_per_week'],
                    user_id,
                    g_dict.get('created_at')
                )
            except Exception as e:
                print(f"[get_user_goals] Calendar fallback warning for goal {g_dict.get('id')}: {e}")
                g_dict['calendar'] = None
        result.append(g_dict)
    return result

def check_goal_feasibility(user_id, target_distance_km, target_date_str, days_per_week):
    target_date = parse_date_safe(target_date_str, (datetime.now() + timedelta(weeks=8)).date())
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
    today = datetime.now().date()
    target_date = parse_date_safe(target_date_str, (today + timedelta(weeks=8)))
    created_date = parse_date_safe(created_at, today)

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

def match_run_to_training_plan(user_id: int, run_id: int, distance_km: float, date_str: str = None):
    """
    Correlates a newly logged run to the runner's periodized weekly training plan workouts.
    Finds the best matching scheduled workout in the target week and marks it as completed.
    Returns matching metadata dict or None if no match.
    """
    conn = get_db()
    goal = conn.execute(
        "SELECT id, ai_plan_json, target_date, created_at, race_name FROM user_goals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    
    if not goal:
        conn.close()
        return None
        
    g_dict = dict(goal)
    ai_plan_raw = g_dict.get('ai_plan_json')
    if not ai_plan_raw:
        conn.close()
        return None
        
    try:
        ai_plan = json.loads(ai_plan_raw)
    except Exception:
        conn.close()
        return None
        
    weeks = ai_plan.get('weeks', [])
    if not weeks:
        conn.close()
        return None
        
    run_date = parse_date_safe(date_str, datetime.now().date())
    run_day_name = run_date.strftime("%A")
    created_date = parse_date_safe(g_dict.get('created_at'), datetime.now().date())
    
    # 1. Locate matching week
    target_week = None
    target_week_idx = -1
    for idx, w in enumerate(weeks):
        w_start = created_date + timedelta(weeks=idx)
        w_end = w_start + timedelta(days=6)
        w['start_date'] = w_start.strftime("%Y-%m-%d")
        w['end_date'] = w_end.strftime("%Y-%m-%d")
        if w_start <= run_date <= w_end:
            target_week = w
            target_week_idx = idx
            break
            
    # Fallback to current week if outside bounds or not found
    if target_week is None:
        for idx, w in enumerate(weeks):
            if w.get('is_current'):
                target_week = w
                target_week_idx = idx
                break
        if target_week is None:
            target_week = weeks[0]
            target_week_idx = 0

    workouts = target_week.get('workouts', [])
    if not workouts:
        conn.close()
        return None

    # Check if run_id is already linked to a workout in this plan
    for w in weeks:
        for wo in w.get('workouts', []):
            if wo.get('completed_run_id') == run_id:
                conn.close()
                return None

    # 2. Score candidate workouts (that aren't already completed)
    best_candidate = None
    best_score = -999.0
    
    for wo_idx, wo in enumerate(workouts):
        if wo.get('completed'):
            continue
            
        wo_dist = float(wo.get('distance_km', 0))
        delta = abs(distance_km - wo_dist)
        ratio = distance_km / max(0.1, wo_dist)
        
        score = 0.0
        # Day of week bonus
        if wo.get('day', '').strip().lower() == run_day_name.lower():
            score += 150.0
            
        # Distance proximity score (closer distance = higher score)
        dist_score = max(0.0, 100.0 - (delta * 15.0))
        score += dist_score
        
        # Long run matching bonus
        is_long_run = "long run" in wo.get('type', '').lower() or "race day" in wo.get('type', '').lower()
        if is_long_run and ratio >= 0.70:
            score += 40.0
            
        # Qualification threshold: must be at least 50% of workout distance, within 2.5 km, or >= 3.0 km
        is_qualified = (ratio >= 0.50) or (delta <= 2.5) or (distance_km >= 3.0)
        
        if is_qualified and score > best_score:
            best_score = score
            best_candidate = (wo_idx, wo)

    if best_candidate is None:
        conn.close()
        return None
        
    wo_idx, matched_wo = best_candidate
    matched_wo['completed'] = True
    matched_wo['completed_run_id'] = run_id
    matched_wo['completed_distance_km'] = round(float(distance_km), 2)
    matched_wo['completed_at'] = run_date.strftime("%Y-%m-%d")
    matched_wo['completed_day'] = run_day_name

    # Calculate week stats
    completed_count = sum(1 for w in workouts if w.get('completed'))
    target_week['completed_workouts'] = completed_count
    target_week['total_workouts'] = len(workouts)
    target_week['completion_pct'] = round((completed_count / len(workouts)) * 100) if workouts else 0

    # Save to database
    conn.execute(
        "UPDATE user_goals SET ai_plan_json = ? WHERE id = ?",
        (json.dumps(ai_plan), g_dict['id'])
    )

    # Dispatch in-app notification of workout completion
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notif_title = "⚡ Workout Completed!"
        notif_msg = (
            f"Run matched with {matched_wo.get('day')} {matched_wo.get('type')}! "
            f"Logged {float(distance_km):.1f} km towards your {g_dict.get('race_name') or 'Race'} plan."
        )
        from db import USE_PG
        if USE_PG:
            n_cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type, created_at) "
                "VALUES (?, ?, 'WORKOUT_COMPLETED', ?, 'SPECIFIC_USER', ?) RETURNING id",
                (notif_title, notif_msg, user_id, now_str)
            )
            notif_id = n_cur.fetchone()["id"]
        else:
            n_cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type, created_at) "
                "VALUES (?, ?, 'WORKOUT_COMPLETED', ?, 'SPECIFIC_USER', ?)",
                (notif_title, notif_msg, user_id, now_str)
            )
            notif_id = n_cur.lastrowid

        conn.execute(
            "INSERT INTO user_notifications (notification_id, user_id, delivered_at) VALUES (?, ?, ?)",
            (notif_id, user_id, now_str)
        )
    except Exception as n_err:
        print(f"[RunRush] Workout match notification warning: {n_err}")

    conn.commit()
    conn.close()

    return {
        "matched": True,
        "goal_id": g_dict['id'],
        "week_number": target_week.get('week_number', target_week_idx + 1),
        "workout_index": wo_idx,
        "workout_day": matched_wo.get('day'),
        "workout_type": matched_wo.get('type'),
        "planned_km": matched_wo.get('distance_km'),
        "actual_km": round(float(distance_km), 2),
        "completed_count": completed_count,
        "total_workouts": len(workouts),
        "completion_pct": target_week['completion_pct']
    }

def unmatch_run_from_training_plan(user_id: int, run_id: int):
    """
    Reverts completion of any workout matched with the given run_id (unless manually overridden).
    """
    conn = get_db()
    goal = conn.execute(
        "SELECT id, ai_plan_json FROM user_goals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    
    if not goal:
        conn.close()
        return False
        
    g_dict = dict(goal)
    ai_plan_raw = g_dict.get('ai_plan_json')
    if not ai_plan_raw:
        conn.close()
        return False
        
    try:
        ai_plan = json.loads(ai_plan_raw)
    except Exception:
        conn.close()
        return False
        
    modified = False
    for w in ai_plan.get('weeks', []):
        for wo in w.get('workouts', []):
            if wo.get('completed_run_id') == run_id and not wo.get('manual_override'):
                wo['completed'] = False
                wo.pop('completed_run_id', None)
                wo.pop('completed_distance_km', None)
                wo.pop('completed_at', None)
                wo.pop('completed_day', None)
                modified = True
        if modified:
            completed_count = sum(1 for wo in w.get('workouts', []) if wo.get('completed'))
            w['completed_workouts'] = completed_count
            tot = len(w.get('workouts', []))
            w['completion_pct'] = round((completed_count / tot) * 100) if tot else 0

    if modified:
        conn.execute(
            "UPDATE user_goals SET ai_plan_json = ? WHERE id = ?",
            (json.dumps(ai_plan), g_dict['id'])
        )
        conn.commit()
    conn.close()
    return modified

def reconcile_and_match_recent_runs_for_plan(user_id: int):
    """
    Scans recent runs since the goal was created and matches any unlinked runs
    to uncompleted workouts in the user's active plan.
    """
    conn = get_db()
    goal = conn.execute(
        "SELECT id, created_at, ai_plan_json FROM user_goals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (user_id,)
    ).fetchone()
    
    if not goal or not goal['ai_plan_json']:
        conn.close()
        return []
        
    g_dict = dict(goal)
    created_str = g_dict.get('created_at') or datetime.now().strftime("%Y-%m-%d")
    date_prefix = str(created_str)[:10]

    runs = conn.execute(
        "SELECT id, distance_km, date FROM runs WHERE user_id = ? AND date >= ? ORDER BY date ASC, id ASC",
        (user_id, date_prefix)
    ).fetchall()
    conn.close()

    matches = []
    for r in runs:
        m = match_run_to_training_plan(user_id, r['id'], r['distance_km'], r['date'])
        if m:
            matches.append(m)
    return matches

def toggle_plan_workout_completion(user_id: int, goal_id: int, week_number: int, workout_index: int, completed: bool = None):
    """
    Manually toggles or sets completion of a specific scheduled workout in the user's plan.
    """
    conn = get_db()
    goal = conn.execute(
        "SELECT id, ai_plan_json FROM user_goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id)
    ).fetchone()
    
    if not goal:
        conn.close()
        return None
        
    g_dict = dict(goal)
    ai_plan_raw = g_dict.get('ai_plan_json')
    if not ai_plan_raw:
        conn.close()
        return None
        
    try:
        ai_plan = json.loads(ai_plan_raw)
    except Exception:
        conn.close()
        return None

    weeks = ai_plan.get('weeks', [])
    target_week = None
    for w in weeks:
        if w.get('week_number') == week_number:
            target_week = w
            break
            
    if not target_week or workout_index < 0 or workout_index >= len(target_week.get('workouts', [])):
        conn.close()
        return None

    wo = target_week['workouts'][workout_index]
    if completed is None:
        new_state = not wo.get('completed', False)
    else:
        new_state = bool(completed)

    wo['completed'] = new_state
    if new_state:
        wo['manual_override'] = True
        wo['completed_at'] = datetime.now().strftime("%Y-%m-%d")
        if not wo.get('completed_distance_km'):
            wo['completed_distance_km'] = wo.get('distance_km', 0)
    else:
        wo['manual_override'] = False
        wo.pop('completed_run_id', None)
        wo.pop('completed_distance_km', None)
        wo.pop('completed_at', None)
        wo.pop('completed_day', None)

    completed_count = sum(1 for w_item in target_week['workouts'] if w_item.get('completed'))
    target_week['completed_workouts'] = completed_count
    tot = len(target_week['workouts'])
    target_week['completion_pct'] = round((completed_count / tot) * 100) if tot else 0

    conn.execute(
        "UPDATE user_goals SET ai_plan_json = ? WHERE id = ?",
        (json.dumps(ai_plan), goal_id)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "workout": wo,
        "week_number": week_number,
        "workout_index": workout_index,
        "completed_count": completed_count,
        "total_workouts": tot,
        "completion_pct": target_week['completion_pct']
    }

def evaluate_goals_for_user(user_id, run_id=None):
    """
    Hook called when a run is logged, edited, or deleted.
    1. Evaluates overall goal completion (if any single run >= target_distance_km).
    2. Dynamic Workout Auto-Matcher: Correlates run to active plan workouts.
    """
    conn = get_db()
    
    active_goals = conn.execute(
        "SELECT * FROM user_goals WHERE user_id = ? AND status = 'active'",
        (user_id,)
    ).fetchall()
    
    if not active_goals:
        conn.close()
        return None

    matched_workout_info = None

    # Auto-match workout to plan if run_id provided
    if run_id:
        try:
            run_row = conn.execute(
                "SELECT id, distance_km, date FROM runs WHERE id = ? AND user_id = ?",
                (run_id, user_id)
            ).fetchone()
            if run_row:
                matched_workout_info = match_run_to_training_plan(
                    user_id=user_id,
                    run_id=run_row['id'],
                    distance_km=run_row['distance_km'],
                    date_str=run_row['date']
                )
        except Exception as match_err:
            print(f"[evaluate_goals_for_user] Workout match warning: {match_err}")
    else:
        # Reconcile if a run was deleted
        try:
            goal = conn.execute(
                "SELECT id, ai_plan_json FROM user_goals WHERE user_id = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
                (user_id,)
            ).fetchone()
            if goal and goal['ai_plan_json']:
                ai_plan = json.loads(goal['ai_plan_json'])
                modified = False
                for w in ai_plan.get('weeks', []):
                    for wo in w.get('workouts', []):
                        r_id = wo.get('completed_run_id')
                        if r_id and not wo.get('manual_override'):
                            exists = conn.execute("SELECT id FROM runs WHERE id = ? AND user_id = ?", (r_id, user_id)).fetchone()
                            if not exists:
                                wo['completed'] = False
                                wo.pop('completed_run_id', None)
                                wo.pop('completed_distance_km', None)
                                wo.pop('completed_at', None)
                                modified = True
                    if modified:
                        cc = sum(1 for wo in w.get('workouts', []) if wo.get('completed'))
                        w['completed_workouts'] = cc
                        tot = len(w.get('workouts', []))
                        w['completion_pct'] = round((cc / tot) * 100) if tot else 0
                if modified:
                    conn.execute("UPDATE user_goals SET ai_plan_json = ? WHERE id = ?", (json.dumps(ai_plan), goal['id']))
                    conn.commit()
        except Exception as rec_err:
            print(f"[evaluate_goals_for_user] Reconcile warning: {rec_err}")

    # Check if user has any single run >= target distance within the goal period
    goal_completed = False
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
            goal_completed = True
    
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

    return {
        "goal_completed": goal_completed,
        "matched_workout": matched_workout_info
    }

def generate_ai_training_plan(
    user_id: int,
    target_distance_km: float,
    target_date_str: str,
    days_per_week: int,
    fitness_level: str = "intermediate",
    long_run_day: str = "Sunday",
    race_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build an AI-guided progressive running training plan leading to a race day.
    Includes feasibility check, periodized phases (base, build, peak, taper, race week),
    weekly workout distributions, long run milestones, and coaching tips.
    """
    target_date = parse_date_safe(target_date_str, (datetime.now() + timedelta(weeks=8)).date())
    target_date_str = target_date.strftime("%Y-%m-%d")

    today = datetime.now().date()
    total_days = max(1, (target_date - today).days)
    total_weeks = max(1, math.ceil(total_days / 7.0))
    days_per_week = max(2, min(6, int(days_per_week)))
    target_distance_km = float(target_distance_km)

    # 1. Check Feasibility
    is_feasible, reject_data = check_goal_feasibility(
        user_id, target_distance_km, target_date_str, days_per_week
    )

    # 2. Establish Baseline Distance
    conn = get_db()
    cutoff_date = (today - timedelta(weeks=8)).strftime("%Y-%m-%d")
    recent_runs = conn.execute(
        "SELECT distance_km FROM runs WHERE user_id = ? AND date >= ?",
        (user_id, cutoff_date)
    ).fetchall()
    conn.close()

    max_recent = max([r['distance_km'] for r in recent_runs]) if recent_runs else 0.0
    
    if max_recent > 0:
        baseline_km = max_recent
    else:
        # Default starting point based on fitness level and distance
        if fitness_level == "beginner":
            baseline_km = max(1.5, target_distance_km * 0.20)
        elif fitness_level == "experienced":
            baseline_km = max(5.0, target_distance_km * 0.45)
        else: # intermediate
            baseline_km = max(3.0, target_distance_km * 0.30)

    # Peak target long run
    if target_distance_km >= 40.0:
        peak_long_run = min(34.0, target_distance_km * 0.80)
    elif target_distance_km >= 20.0:
        peak_long_run = min(18.5, target_distance_km * 0.88)
    elif target_distance_km >= 10.0:
        peak_long_run = min(10.0, target_distance_km * 0.95)
    else:
        peak_long_run = target_distance_km

    # 3. Taper Structure
    if total_weeks >= 10:
        taper_weeks = 2
    elif total_weeks >= 4:
        taper_weeks = 1
    else:
        taper_weeks = 0

    progression_weeks = max(1, total_weeks - taper_weeks)

    # 4. Generate Weekly Targets
    weekly_long_runs = []
    for w in range(progression_weeks):
        if progression_weeks == 1:
            dist = peak_long_run
        else:
            prog = (w + 1) / progression_weeks
            dist = baseline_km + (peak_long_run - baseline_km) * prog

        # Cutback recovery week every 4th week (if plan is >= 6 weeks long)
        if total_weeks >= 6 and (w + 1) % 4 == 0 and w < progression_weeks - 1:
            dist = dist * 0.78 # 22% cutback for active physiological adaptation

        weekly_long_runs.append(round(dist, 1))

    # Add taper weeks
    if taper_weeks == 2:
        weekly_long_runs.append(round(peak_long_run * 0.72, 1))
        weekly_long_runs.append(round(target_distance_km, 1))
    elif taper_weeks == 1:
        weekly_long_runs.append(round(target_distance_km, 1))

    # Pad or trim to exactly total_weeks
    while len(weekly_long_runs) < total_weeks:
        weekly_long_runs.append(round(target_distance_km, 1))
    weekly_long_runs = weekly_long_runs[:total_weeks]
    weekly_long_runs[-1] = round(target_distance_km, 1)

    # 5. Build detailed schedule
    long_day = long_run_day if long_run_day in ["Saturday", "Sunday"] else "Sunday"
    
    weeks_schedule = []
    for w_idx in range(total_weeks):
        w_num = w_idx + 1
        w_start = today + timedelta(weeks=w_idx)
        w_end = w_start + timedelta(days=6)
        long_km = weekly_long_runs[w_idx]

        is_race_week = (w_num == total_weeks)
        is_taper = (w_idx >= progression_weeks and not is_race_week)
        
        if is_race_week:
            phase = "Race Week"
        elif is_taper:
            phase = "Taper & Sharpen"
        elif w_num <= math.ceil(progression_weeks * 0.35):
            phase = "Base Aerobic Build"
        elif w_num == progression_weeks:
            phase = "Peak Volume Load"
        else:
            phase = "Progressive Endurance"

        easy_run_dist = max(2.0, round(long_km * 0.45, 1))
        tempo_run_dist = max(2.5, round(long_km * 0.55, 1))
        recovery_dist = max(1.5, round(long_km * 0.35, 1))

        workouts = []
        if is_race_week:
            shakeout = max(2.0, round(target_distance_km * 0.25, 1))
            workouts.append({
                "day": "Tuesday",
                "type": "Easy Shakeout",
                "distance_km": shakeout,
                "description": "Very relaxed easy jog to stay loose."
            })
            if days_per_week >= 3:
                workouts.append({
                    "day": "Thursday",
                    "type": "Activation Run",
                    "distance_km": max(1.5, round(shakeout * 0.7, 1)),
                    "description": "Short activation jog with 3x 20s strides at race pace."
                })
            workouts.append({
                "day": long_day,
                "type": "RACE DAY // TARGET",
                "distance_km": round(target_distance_km, 1),
                "description": "The target race! Execute your controlled pacing strategy and finish strong."
            })
        else:
            if days_per_week == 2:
                workouts.append({
                    "day": "Wednesday",
                    "type": "Midweek Aerobic Run",
                    "distance_km": easy_run_dist,
                    "description": "Maintain steady conversational aerobic pace (Zone 2)."
                })
                workouts.append({
                    "day": long_day,
                    "type": "Weekly Long Run",
                    "distance_km": long_km,
                    "description": "Build aerobic endurance. Run comfortably throughout."
                })
            elif days_per_week == 3:
                workouts.append({
                    "day": "Tuesday",
                    "type": "Easy Aerobic Run",
                    "distance_km": easy_run_dist,
                    "description": "Smooth conversational pace. Focus on good running posture."
                })
                workouts.append({
                    "day": "Thursday",
                    "type": "Pace Workout / Tempo",
                    "distance_km": tempo_run_dist,
                    "description": "Warmup, then race-pace intervals to build lactate threshold."
                })
                workouts.append({
                    "day": long_day,
                    "type": "Weekly Long Run",
                    "distance_km": long_km,
                    "description": "Your cornerstone endurance run. Keep the first half disciplined."
                })
            elif days_per_week == 4:
                workouts.append({
                    "day": "Tuesday",
                    "type": "Easy Aerobic Run",
                    "distance_km": easy_run_dist,
                    "description": "Comfortable conversational pace."
                })
                workouts.append({
                    "day": "Wednesday",
                    "type": "Tempo / Threshold Run",
                    "distance_km": tempo_run_dist,
                    "description": "Comfortably hard threshold intervals to build stamina."
                })
                workouts.append({
                    "day": "Friday",
                    "type": "Recovery Shakeout",
                    "distance_km": recovery_dist,
                    "description": "Very gentle recovery jog or cross-training."
                })
                workouts.append({
                    "day": long_day,
                    "type": "Weekly Long Run",
                    "distance_km": long_km,
                    "description": "Key weekly endurance workout. Practice your race hydration."
                })
            else: # 5+ days
                workouts.append({
                    "day": "Monday",
                    "type": "Easy Recovery",
                    "distance_km": recovery_dist,
                    "description": "Light shakeout run."
                })
                workouts.append({
                    "day": "Tuesday",
                    "type": "Interval Speed Session",
                    "distance_km": tempo_run_dist,
                    "description": "Intervals with recovery jogs to sharpen VO2 max."
                })
                workouts.append({
                    "day": "Thursday",
                    "type": "Tempo Progression",
                    "distance_km": easy_run_dist,
                    "description": "Controlled aerobic run finishing at target race pace."
                })
                workouts.append({
                    "day": "Friday",
                    "type": "Easy Base Run",
                    "distance_km": recovery_dist,
                    "description": "Light easy mileage."
                })
                workouts.append({
                    "day": long_day,
                    "type": "Weekly Long Run",
                    "distance_km": long_km,
                    "description": "Key weekly endurance anchor."
                })

        weekly_total = round(sum(w_item["distance_km"] for w_item in workouts), 1)

        weeks_schedule.append({
            "week_number": w_num,
            "phase": phase,
            "date_range": f"{w_start.strftime('%b %d')} - {w_end.strftime('%b %d')}",
            "long_run_km": long_km,
            "weekly_total_km": weekly_total,
            "workouts": workouts,
            "is_current": (w_num == 1),
            "is_past": False
        })

    # 6. Coach Strategy Tips (Professional, telemetry-driven)
    coach_notes = [
        f"**Pacing Discipline**: For your {target_distance_km:g} km goal, start the first 30% of the race conservatively. Running the second half strong is the proven secret to a personal best.",
        f"**Hydration & Fuel**: On runs longer than 60 minutes, practice drinking water or electrolyte fluids every 20-30 minutes so your stomach is well-adapted for race day.",
        f"**Recovery Architecture**: Muscles adapt and get stronger during rest and sleep. Aim for 7-8 hours of sleep and honor your recovery days.",
        f"**Gear & Protocol Validation**: Nothing new on race day. Wear the shoes, socks, and gear you've thoroughly tested during your long runs."
    ]

    # Optional AI commentary enhancement with Gemini
    ai_commentary = None
    try:
        from services.rumi_service import is_rumi_configured
        if is_rumi_configured():
            import os
            from google import genai
            from google.genai import types

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            client = genai.Client(api_key=api_key)
            model_name = os.environ.get("RUMI_GEMINI_MODEL", "gemini-2.5-flash-lite")
            
            prompt = (
                f"You are Rumi, an expert and encouraging running coach in RunRush. "
                f"A runner is training for a {target_distance_km:g} km race on {target_date_str} ({total_weeks} weeks plan, "
                f"{days_per_week} days/week, level: {fitness_level}). "
                f"Provide exactly 2 sentences of high-energy, personalized coaching strategy and motivation for their plan."
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=150)
            )
            if response and response.text:
                ai_commentary = response.text.strip()
    except Exception:
        pass

    if ai_commentary:
        coach_notes.insert(0, f"**Coach Intelligence**: {ai_commentary}")

    race_display_name = race_name.strip() if race_name and race_name.strip() else f"{target_distance_km:g} km Race Target"

    return {
        "status": "success",
        "is_feasible": is_feasible,
        "feasibility_info": reject_data,
        "race_name": race_display_name,
        "target_distance_km": round(target_distance_km, 1),
        "target_date": target_date_str,
        "days_per_week": days_per_week,
        "fitness_level": fitness_level,
        "long_run_day": long_day,
        "total_weeks": total_weeks,
        "taper_weeks": taper_weeks,
        "weeks": weeks_schedule,
        "coach_notes": coach_notes,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

