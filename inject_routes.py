with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

new_routes = """
# ---------- NOTIFICATIONS (PHASE 2) ----------

@app.route("/admin/notifications")
@login_required
@admin_required
def admin_notifications_page():
    user = get_current_user()
    return render_template("admin_notifications.html", user=user, theme=user["theme"] or "dark")

@app.route("/api/admin/notifications", methods=["GET"])
@login_required
@admin_required
def get_admin_notifications():
    conn = get_db()
    rows = conn.execute(
        "SELECT n.*, u.username as creator_username FROM notifications n "
        "LEFT JOIN users u ON n.created_by = u.id ORDER BY n.created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return jsonify({"notifications": [dict(r) for r in rows]})

@app.route("/api/admin/notifications", methods=["POST"])
@login_required
@admin_required
def create_admin_notification():
    user = get_current_user()
    data = request.json
    title = data.get("title", "").strip()
    message = data.get("message", "").strip()
    notif_type = data.get("type", "SYSTEM")
    audience_type = data.get("audience_type", "EVERYONE")
    target_user_id = data.get("target_user_id")

    if not title or not message:
        return jsonify({"error": "Title and message are required"}), 400

    conn = get_db()
    from db import USE_PG
    try:
        if USE_PG:
            cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type) "
                "VALUES (?, ?, ?, ?, ?) RETURNING id",
                (title, message, notif_type, user["id"], audience_type)
            )
            notif_id = cur.fetchone()["id"]
        else:
            cur = conn.execute(
                "INSERT INTO notifications (title, message, type, created_by, audience_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, message, notif_type, user["id"], audience_type)
            )
            notif_id = cur._cursor.lastrowid if hasattr(cur, '_cursor') else cur.lastrowid
            
        if audience_type == "SPECIFIC_USER" and target_user_id:
            conn.execute(
                "INSERT INTO user_notifications (notification_id, user_id) VALUES (?, ?)",
                (notif_id, target_user_id)
            )
        else:
            conn.execute(
                "INSERT INTO user_notifications (notification_id, user_id) "
                "SELECT ?, id FROM users WHERE COALESCE(status, 'active') = 'active'",
                (notif_id,)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        
    return jsonify({"success": True, "message": "Notification sent successfully"})

@app.route("/api/notifications", methods=["GET"])
def get_user_notifications():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    
    user = get_current_user()
    limit = int(request.args.get("limit", 20))
    
    conn = get_db()
    rows = conn.execute(
        "SELECT n.id, n.title, n.message, n.type, n.created_at, un.read_at "
        "FROM user_notifications un "
        "JOIN notifications n ON un.notification_id = n.id "
        "WHERE un.user_id = ? "
        "ORDER BY n.created_at DESC LIMIT ?",
        (user["id"], limit)
    ).fetchall()
    conn.close()
    
    return jsonify({"notifications": [dict(r) for r in rows]})

@app.route("/api/notifications/unread-count", methods=["GET"])
def get_unread_count():
    if not require_login():
        return jsonify({"count": 0})
        
    user = get_current_user()
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as count FROM user_notifications "
        "WHERE user_id = ? AND read_at IS NULL",
        (user["id"],)
    ).fetchone()
    conn.close()
    
    return jsonify({"count": row["count"] if row else 0})

@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
def mark_notification_read(notif_id):
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
        
    user = get_current_user()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    conn.execute(
        "UPDATE user_notifications SET read_at = ? "
        "WHERE notification_id = ? AND user_id = ? AND read_at IS NULL",
        (now_str, notif_id, user["id"])
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
        
    user = get_current_user()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    conn.execute(
        "UPDATE user_notifications SET read_at = ? "
        "WHERE user_id = ? AND read_at IS NULL",
        (now_str, user["id"])
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

"""

content = content.replace("# ---------- RUN APP ----------", new_routes + "\n# ---------- RUN APP ----------")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Routes injected successfully.")
