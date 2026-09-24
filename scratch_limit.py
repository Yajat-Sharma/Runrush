import re

with open('app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# 1. Modify add_run
add_run_search = """        # Validation: Distance (must be positive)
        try:
            distance = float(distance_str)
            if distance <= 0:
                log_activity(user["id"], "VALIDATION_FAIL", f"Invalid distance: {distance}")
                flash("Distance must be greater than 0 km.", "danger")
                return redirect(url_for("index"))"""

add_run_replace = """        # Validation: Distance (must be positive)
        try:
            distance = float(distance_str)
            if distance <= 0:
                log_activity(user["id"], "VALIDATION_FAIL", f"Invalid distance: {distance}")
                flash("Distance must be greater than 0 km.", "danger")
                return redirect(url_for("index"))
            if distance > 1000:
                log_activity(user["id"], "VALIDATION_FAIL", f"Invalid distance (over limit): {distance}")
                flash("Distance cannot exceed 1000 km per run.", "danger")
                return redirect(url_for("index"))"""

app_code = app_code.replace(add_run_search, add_run_replace)

# 2. Modify parse_strava_csv
csv_search = """        distance_km = parse_distance_str(raw_row.get(dist_col))
        if not distance_km or distance_km <= 0:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid distance: '{raw_row.get(dist_col)}'"
            })
            continue"""

csv_replace = """        distance_km = parse_distance_str(raw_row.get(dist_col))
        if not distance_km or distance_km <= 0:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Invalid distance: '{raw_row.get(dist_col)}'"
            })
            continue
        if distance_km > 1000:
            invalids.append({
                "row": row_index,
                "name": act_name or f"Row {row_index}",
                "reason": f"Distance cannot exceed 1000 km (Found: {distance_km} km)"
            })
            continue"""

app_code = app_code.replace(csv_search, csv_replace)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

print("Updated app.py with 1000 km limit.")
