from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import date, datetime, timedelta

app = Flask(__name__)
app.secret_key = "super-secret-key-change-this"  # needed for sessions

DEFAULT_WEIGHT = 0.0   # used if user hasn't set weight yet


# ----------------- DB HELPERS -----------------

def get_db():
    conn = sqlite3.connect("runs.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    # users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL
        )
    """)

    # add new columns if they don't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN weight REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN weekly_goal_km REAL")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN theme TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN height REAL")
    except sqlite3.OperationalError:
        pass

    # runs table, linked to user
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            distance_km REAL NOT NULL,
            time_min REAL NOT NULL,
            pace REAL NOT NULL,
            calories REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
# Make sure DB/tables exist when app starts (for Render / gunicorn)
with app.app_context():
    init_db()



def calc_stats(distance_km, time_min, weight_kg):
    pace = time_min / distance_km
    calories = weight_kg * distance_km
    return round(pace, 2), round(calories, 0)


def format_time_min(minutes):
    total_seconds = int(round(minutes * 60))
    m = total_seconds // 60
    s = total_seconds % 60
    return f"{m}m {s:02d}s"


def require_login():
    return "user_id" in session


def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


# ----------------- ROUTES -----------------


@app.route("/")
def home_redirect():
    if not require_login():
        return redirect(url_for("login"))
    return redirect(url_for("index"))


@app.route("/dashboard", methods=["GET"])
def index():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    username = user["username"]
    display_name = user["display_name"] or username
    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT

        # ---- BMI CALCULATION (uses actual stored weight + height) ----
    raw_weight = user["weight"]
    raw_height = user["height"] if "height" in user.keys() else None

    bmi_value = None
    bmi_status = None

    try:
        if raw_weight is not None and raw_height is not None:
            w = float(raw_weight)
            h_cm = float(raw_height)
            if h_cm > 0:
                h_m = h_cm / 100.0
                bmi_value = round(w / (h_m * h_m), 1)

                if bmi_value < 18.5:
                    bmi_status = "Underweight"
                elif bmi_value < 25:
                    bmi_status = "Normal"
                elif bmi_value < 30:
                    bmi_status = "Overweight"
                else:
                    bmi_status = "Obese"
    except (TypeError, ValueError):
        bmi_value = None
        bmi_status = None

    # theme from DB (fallback dark)
    theme = user["theme"] or "dark"

    # --- read sort + filter from query params ---
    sort_by = request.args.get("sort", "date")      # date | distance | time
    filter_opt = request.args.get("filter", "all")  # all | last7 | month | 5k10k

    conn = get_db()

    # --- base query with sorting ---
    base_query = "SELECT * FROM runs WHERE user_id = ?"
    if sort_by == "distance":
        order_clause = " ORDER BY distance_km DESC, date DESC"
    elif sort_by == "time":
        order_clause = " ORDER BY time_min DESC, date DESC"
    else:  # default = date
        order_clause = " ORDER BY date DESC, id DESC"

    runs = conn.execute(base_query + order_clause, (user["id"],)).fetchall()

    # ---- All-time stats (use ALL runs) ----
    total_km = sum(r["distance_km"] for r in runs) if runs else 0
    total_cal = sum(r["calories"] for r in runs) if runs else 0
    avg_pace = (sum(r["pace"] for r in runs) / len(runs)) if runs else 0

    # ---- This month stats (use ALL runs) ----
    today = date.today()
    current_year = today.year
    current_month = today.month

    month_runs = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if d.year == current_year and d.month == current_month:
                month_runs.append(r)
        except Exception:
            continue

    month_km = sum(r["distance_km"] for r in month_runs) if month_runs else 0
    month_cal = sum(r["calories"] for r in month_runs) if month_runs else 0
    month_avg_pace = (sum(r["pace"] for r in month_runs) / len(month_runs)) if month_runs else 0

    # ---- WEEKLY DISTANCE + GOAL PROGRESS ----
    week_start = today - timedelta(days=today.weekday())   # Monday
    week_end = week_start + timedelta(days=6)

    week_runs = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            if week_start <= d <= week_end:
                week_runs.append(r)
        except Exception:
            continue

    weekly_km = sum(r["distance_km"] for r in week_runs) if week_runs else 0.0

    weekly_goal = (
        user["weekly_goal_km"]
        if "weekly_goal_km" in user.keys() and user["weekly_goal_km"] is not None
        else None
    )

    if weekly_goal and weekly_goal > 0:
        weekly_remaining = max(weekly_goal - weekly_km, 0)
        weekly_progress_percent = min(100.0 * weekly_km / weekly_goal, 100.0)
    else:
        weekly_remaining = None
        weekly_progress_percent = 0.0

    # ---- Personal bests (use ALL runs) ----
    pb_5k_time = None
    pb_5k_pace = None
    pb_10k_time = None
    pb_10k_pace = None

    for r in runs:
        dist = r["distance_km"]
        t = r["time_min"]
        pace = r["pace"]

        # treat 4.5–5.5 km as 5K
        if 4.5 <= dist <= 5.5:
            if pb_5k_time is None or t < pb_5k_time:
                pb_5k_time = t
                pb_5k_pace = pace

        # treat 9–11 km as 10K
        if 9.0 <= dist <= 11.0:
            if pb_10k_time is None or t < pb_10k_time:
                pb_10k_time = t
                pb_10k_pace = pace

    pb_5k_time_str = format_time_min(pb_5k_time) if pb_5k_time is not None else None
    pb_10k_time_str = format_time_min(pb_10k_time) if pb_10k_time is not None else None

    # ---- FILTER for history table (not stats) ----
    filtered_runs = list(runs)

    if filter_opt == "last7":
        cutoff = today - timedelta(days=7)
        temp = []
        for r in runs:
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                if d >= cutoff:
                    temp.append(r)
            except Exception:
                continue
        filtered_runs = temp

    elif filter_opt == "month":
        filtered_runs = month_runs

    elif filter_opt == "5k10k":
        temp = []
        for r in runs:
            dist = r["distance_km"]
            if (4.5 <= dist <= 5.5) or (9.0 <= dist <= 11.0):
                temp.append(r)
        filtered_runs = temp

    # ---------- STREAK CALCULATION ----------
    all_dates = []
    for r in runs:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            all_dates.append(d)
        except Exception:
            pass

    if all_dates:
        all_dates = sorted(list(set(all_dates)))  # unique + sorted ASC

        # ---- CURRENT STREAK ----
        current_streak = 0
        day_pointer = today

        while day_pointer in all_dates:
            current_streak += 1
            day_pointer = day_pointer - timedelta(days=1)

        # ---- BEST STREAK ----
        best_streak = 0
        streak = 1
        for i in range(1, len(all_dates)):
            if all_dates[i] == all_dates[i-1] + timedelta(days=1):
                streak += 1
            else:
                best_streak = max(best_streak, streak)
                streak = 1
        best_streak = max(best_streak, streak)

        # ---- WEEKLY STREAK BAR (Mon–Sun) ----
        week_start = today - timedelta(days=today.weekday())   # Monday
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        streak_bar = []
        for d in week_days:
            if d in all_dates:
                streak_bar.append("🔥")
            else:
                streak_bar.append("—")
    else:
        current_streak = 0
        best_streak = 0
        streak_bar = ["—"] * 7

    conn.close()

    return render_template(
        "index.html",
        theme=theme,
        runs=filtered_runs,              # history table uses filtered list
        total_km=round(total_km, 2),
        total_cal=round(total_cal, 0),
        avg_pace=round(avg_pace, 2),
        month_km=round(month_km, 2),
        month_cal=round(month_cal, 0),
        month_avg_pace=round(month_avg_pace, 2),
        pb_5k_time=pb_5k_time_str,
        pb_5k_pace=round(pb_5k_pace, 2) if pb_5k_pace is not None else None,
        pb_10k_time=pb_10k_time_str,
        pb_10k_pace=round(pb_10k_pace, 2) if pb_10k_pace is not None else None,
        weight=user_weight,
        username=username,
        display_name=display_name,
        active_sort=sort_by,
        active_filter=filter_opt,
        current_streak=current_streak,
        best_streak=best_streak,
        streak_bar=streak_bar,
        weekly_km=round(weekly_km, 1),
        weekly_goal=weekly_goal,
        weekly_remaining=round(weekly_remaining, 1) if weekly_remaining is not None else None,
        weekly_progress_percent=round(weekly_progress_percent, 1),
        bmi_value=bmi_value,
        bmi_status=bmi_status,
        height=raw_height,

    )


# ---------- ADD RUN ----------

@app.route("/add", methods=["POST"])
def add_run():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    run_date = request.form.get("date")
    if not run_date:
        run_date = date.today().strftime("%Y-%m-%d")

    try:
        distance = float(request.form.get("distance", "0"))
        time_min = float(request.form.get("time", "0"))
    except (TypeError, ValueError):
        return redirect(url_for("index"))

    if distance <= 0 or time_min <= 0:
        return redirect(url_for("index"))

    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT
    pace, calories = calc_stats(distance, time_min, user_weight)

    conn = get_db()
    conn.execute(
        """
        INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user["id"], run_date, distance, time_min, pace, calories),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------- WEEKLY GOAL ----------

@app.route("/weekly-goal", methods=["POST"])
def weekly_goal():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    goal_str = request.form.get("weekly_goal", "").strip()
    try:
        goal_val = float(goal_str) if goal_str else None
    except ValueError:
        goal_val = None

    conn = get_db()
    conn.execute(
        "UPDATE users SET weekly_goal_km = ? WHERE id = ?",
        (goal_val, user["id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------- DELETE RUN ----------

@app.route("/delete/<int:run_id>", methods=["POST"])
def delete_run(run_id):
    if not require_login():
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "DELETE FROM runs WHERE id = ? AND user_id = ?",
        (run_id, session["user_id"]),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------- SETTINGS ----------

@app.route("/settings", methods=["GET"])
def settings():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()

    return render_template(
        "settings.html",
        display_name=user["display_name"] or user["username"],
        username=user["username"],
        weight=user["weight"],
        height=user["height"],
        theme=user["theme"] or "dark"
    )

@app.route("/profile", methods=["POST"])
def update_profile():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    display_name = request.form.get("display_name")
    weight = request.form.get("weight")

    conn = get_db()
    conn.execute("""
        UPDATE users SET display_name = ?, weight = ?
        WHERE id = ?
    """, (display_name, weight, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))

@app.route("/settings/update", methods=["POST"])
def update_settings():
    if not require_login():
        return redirect(url_for("login"))

    theme = request.form.get("theme")
    display_name = request.form.get("display_name")
    weight = request.form.get("weight")
    height = request.form.get("height")   # ⭐ NEW

    user = get_current_user()

    conn = get_db()
    conn.execute("""
        UPDATE users
        SET theme = ?, display_name = ?, weight = ?, height = ?
        WHERE id = ?
    """, (theme, display_name, weight, height, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("settings"))

#-------Delete acc-----#
@app.route("/delete-account", methods=["POST"])
def delete_account():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()

    # 1) Delete all runs for this user
    conn.execute("DELETE FROM runs WHERE user_id = ?", (user["id"],))

    # 2) Delete the user record
    conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))

    conn.commit()
    conn.close()

    # 3) Clear session and send back to login
    session.clear()
    return redirect(url_for("login"))

# ---------- EDIT RUN ---------

@app.route("/edit/<int:run_id>", methods=["GET"])
def edit_run(run_id):
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    run = conn.execute(
        "SELECT * FROM runs WHERE id = ? AND user_id = ?",
        (run_id, session["user_id"])
    ).fetchone()
    conn.close()

    if not run:
        return redirect(url_for("index"))

    display_name = user["display_name"] or user["username"]
    user_weight = user["weight"] if user["weight"] is not None else DEFAULT_WEIGHT

    return render_template(
        "edit.html",
        run=run,
        weight=user_weight,
        username=user["username"],
        display_name=display_name,
        theme=user["theme"] or "dark"
    )


@app.route("/edit/<int:run_id>", methods=["POST"])
def update_run(run_id):
    if not require_login():
        return redirect(url_for("login"))

    distance = float(request.form["distance"])
    time_min = float(request.form["time"])
    run_date = request.form.get("date")

    if distance <= 0 or time_min <= 0:
        return redirect(url_for("index"))

    user = get_current_user()
    user_weight = user["weight"] if user and user["weight"] is not None else DEFAULT_WEIGHT

    pace, calories = calc_stats(distance, time_min, user_weight)

    conn = get_db()
    conn.execute("""
        UPDATE runs
        SET date = ?, distance_km = ?, time_min = ?, pace = ?, calories = ?
        WHERE id = ? AND user_id = ?
    """, (run_date, distance, time_min, pace, calories, run_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


# ---------- AUTH ROUTES ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        if not username or not pin:
            return render_template("register.html", error="Username and PIN are required.")

        if len(pin) < 4 or not pin.isdigit():
            return render_template("register.html", error="Use a 4+ digit numeric PIN.")

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, pin) VALUES (?, ?)",
                (username, pin)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already taken.")
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        session["user_id"] = user["id"]
        session["username"] = username
        return redirect(url_for("onboarding"))

    return render_template("register.html")

#Onboarding program 

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if not require_login():
        return redirect(url_for("login"))

    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    # If user already has basic data, don't keep showing onboarding
    if request.method == "GET":
        if (user["display_name"] is not None or user["weight"] is not None
                or user["weekly_goal_km"] is not None):
            return redirect(url_for("index"))

        return render_template(
            "onboarding.html",
            username=user["username"]
        )

    # POST: save onboarding data
    display_name = request.form.get("display_name", "").strip() or user["username"]
    weight_raw = request.form.get("weight", "").strip()
    weekly_goal_raw = request.form.get("weekly_goal", "").strip()

    try:
        weight = float(weight_raw) if weight_raw else None
    except ValueError:
        weight = None

    try:
        weekly_goal = float(weekly_goal_raw) if weekly_goal_raw else None
    except ValueError:
        weekly_goal = None

    conn = get_db()
    conn.execute("""
        UPDATE users
        SET display_name = ?, weight = ?, weekly_goal_km = ?
        WHERE id = ?
    """, (display_name, weight, weekly_goal, user["id"]))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        pin = request.form["pin"].strip()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND pin = ?",
            (username, pin)
        ).fetchone()
        conn.close()

        if not user:
            return render_template("login.html", error="Invalid username or PIN.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- RUN APP ----------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

