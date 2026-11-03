"""Patch app.py: add run_routes to startup schema + add API endpoints."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app.py')

with open(APP_PY, 'r', encoding='utf-8', newline='') as f:
    src = f.read()

# ── 1. Startup schema: add run_routes ─────────────────────────────────────────
old_startup = (
    "        conn.close()\n"
    "    except Exception as e:\n"
    "        print(f\"[RunRush DB] Startup schema check warning: {e}\", flush=True)"
)

new_startup = (
    "        # 5. run_routes — GPS route storage for Live Run Tracker\n"
    "        if USE_PG:\n"
    "            conn.execute(\"\"\"\n"
    "                CREATE TABLE IF NOT EXISTS run_routes (\n"
    "                    id SERIAL PRIMARY KEY,\n"
    "                    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,\n"
    "                    route_json TEXT NOT NULL,\n"
    "                    total_distance_km REAL,\n"
    "                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
    "                )\n"
    "            \"\"\")\n"
    "        else:\n"
    "            conn.execute(\"\"\"\n"
    "                CREATE TABLE IF NOT EXISTS run_routes (\n"
    "                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "                    run_id INTEGER NOT NULL,\n"
    "                    route_json TEXT NOT NULL,\n"
    "                    total_distance_km REAL,\n"
    "                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,\n"
    "                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE\n"
    "                )\n"
    "            \"\"\")\n"
    "        try:\n"
    "            conn.execute(\"CREATE INDEX IF NOT EXISTS idx_run_routes_run_id ON run_routes(run_id)\")\n"
    "        except Exception:\n"
    "            pass\n"
    "        conn.close()\n"
    "    except Exception as e:\n"
    "        print(f\"[RunRush DB] Startup schema check warning: {e}\", flush=True)"
)

if old_startup in src:
    src = src.replace(old_startup, new_startup, 1)
    print("OK: startup schema patched")
else:
    print("WARN: startup schema target not found — check manually")

# ── 2. API endpoints after /add ────────────────────────────────────────────────
api_endpoints = '''

@app.route("/api/run/<int:run_id>/route", methods=["POST"])
def save_run_route(run_id):
    """Save GPS route coordinates for a live-tracked run."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json(silent=True) or {}
        route = data.get("route", [])
        total_distance_km = data.get("total_distance_km")
        if not route or not isinstance(route, list):
            return jsonify({"error": "No route data"}), 400
        # Verify run belongs to this user
        conn = get_db()
        run = conn.execute(
            "SELECT id FROM runs WHERE id = ? AND user_id = ?", (run_id, user["id"])
        ).fetchone()
        if not run:
            conn.close()
            return jsonify({"error": "Run not found"}), 404
        import json as _json
        conn.execute("DELETE FROM run_routes WHERE run_id = ?", (run_id,))
        conn.execute(
            "INSERT INTO run_routes (run_id, route_json, total_distance_km) VALUES (?, ?, ?)",
            (run_id, _json.dumps(route), total_distance_km)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True})
    except Exception:
        import traceback
        print("[route save error]", traceback.format_exc())
        return jsonify({"error": "Server error"}), 500


@app.route("/api/run/<int:run_id>/route", methods=["GET"])
def get_run_route(run_id):
    """Return stored GPS route for a run."""
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    user = get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        import json as _json
        conn = get_db()
        row = conn.execute(
            """SELECT rr.route_json, rr.total_distance_km
               FROM run_routes rr
               JOIN runs r ON r.id = rr.run_id
               WHERE rr.run_id = ? AND r.user_id = ?""",
            (run_id, user["id"])
        ).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "No route found"}), 404
        route = _json.loads(row["route_json"]) if isinstance(row["route_json"], str) else row["route_json"]
        return jsonify({"route": route, "total_distance_km": row["total_distance_km"]})
    except Exception:
        import traceback
        print("[route get error]", traceback.format_exc())
        return jsonify({"error": "Server error"}), 500

'''

target_after_add = (
    "return redirect(url_for(\"index\", open=run_id)) if 'run_id' in locals() and run_id else redirect(url_for(\"index\"))\n"
    "\n"
)

if target_after_add in src:
    src = src.replace(target_after_add, target_after_add + api_endpoints, 1)
    print("OK: API endpoints inserted")
else:
    print("WARN: /add end marker not found")

with open(APP_PY, 'w', encoding='utf-8', newline='') as f:
    f.write(src)
print("app.py saved.")
