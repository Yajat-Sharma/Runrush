"""
Tests for RunRush Friendly Challenges Phase 5:
- Challenge finalization across all 4 types (Distance, Consistency, Longest Run, Daily Distance).
- Draw / Tie outcome (0 medals awarded).
- Single winner outcome (winner receives 1 medal, loser 0).
- Repeated finalization idempotency.
- Award accumulation (Friendly Challenges × N).
- Run edit recalibration and winner change / award reversal.
- Run deletion recalibration and award reversal.
- Profile integration via get_badges_status_for_user and /api/badges.
- In-app notification creation on finalization and recalibration.
"""

from datetime import datetime, timedelta, timezone
import json
import pytest
from app import app, get_badges_status_for_user
from db import get_db
from services.friendly_challenge_service import (
    create_friendly_challenge_tables,
    create_challenge,
    finalize_challenge_if_due,
    recalibrate_challenge_if_needed,
    recalibrate_user_challenges_on_run_change,
    get_user_friendly_challenge_stats,
    get_friendly_challenge_medal,
)


@pytest.fixture(autouse=True)
def setup_challenge_db(app):
    """Ensure in-memory SQLite tables exist for friendly challenges."""
    conn = get_db()
    create_friendly_challenge_tables(conn)
    conn.commit()
    conn.close()


def create_user(username, display_name):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO users (username, pin, display_name, profile_emoji, status) "
        "VALUES (?, 'pin', ?, '🏃', 'active')",
        (username, display_name)
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def insert_run(user_id, date_str, distance_km, time_min=30.0, run_type="gps"):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO runs (user_id, date, distance_km, time_min, pace, calories, run_type) "
        "VALUES (?, ?, ?, ?, '5:00', 300, ?)",
        (user_id, date_str, distance_km, time_min, run_type)
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def create_and_accept_test_challenge(challenger_id, opponent_id, c_type, start_date, end_date):
    """Helper to create challenge in ACCEPTED state with custom dates."""
    unit = "days" if c_type == "CONSISTENCY" else "km"
    conn = get_db()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""
        INSERT INTO friendly_challenges (
            challenger_id, opponent_id, challenge_type, title,
            start_date, end_date, challenge_timezone, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'UTC', 'ACCEPTED', ?, ?)
    """, (challenger_id, opponent_id, c_type, f"Duel {c_type}", start_date, end_date, now_str, now_str))
    chal_id = cur.lastrowid

    conn.execute("""
        INSERT INTO challenge_participants (challenge_id, user_id, final_score, score_unit, result, created_at, updated_at)
        VALUES (?, ?, 0.0, ?, 'PENDING', ?, ?)
    """, (chal_id, challenger_id, unit, now_str, now_str))
    conn.execute("""
        INSERT INTO challenge_participants (challenge_id, user_id, final_score, score_unit, result, created_at, updated_at)
        VALUES (?, ?, 0.0, ?, 'PENDING', ?, ?)
    """, (chal_id, opponent_id, unit, now_str, now_str))

    conn.commit()
    conn.close()
    return chal_id


def test_finalization_all_four_challenge_types():
    """Verify finalization and score determination for Distance, Consistency, Longest, and Daily."""
    u1 = create_user("runner_alpha", "Runner Alpha")
    u2 = create_user("runner_beta", "Runner Beta")

    start_date = "2026-01-01"
    end_date = "2026-01-07"

    # 1. DISTANCE: u1 = 12km, u2 = 10km -> u1 wins
    chal_dist = create_and_accept_test_challenge(u1, u2, "DISTANCE", start_date, end_date)
    insert_run(u1, "2026-01-02 08:00:00", 12.0)
    insert_run(u2, "2026-01-03 08:00:00", 10.0)

    res_dist = finalize_challenge_if_due(chal_dist)
    assert res_dist["status"] == "COMPLETED"
    assert res_dist["winner_id"] == u1
    assert res_dist["result_type"] == "WIN"

    # 2. CONSISTENCY: u1 runs on 3 days (1km, 1km, 1km), u2 runs on 4 days (0.5km each) -> u2 wins
    chal_cons = create_and_accept_test_challenge(u1, u2, "CONSISTENCY", start_date, end_date)
    insert_run(u1, "2026-01-01 09:00:00", 5.0)
    insert_run(u1, "2026-01-02 09:00:00", 5.0)
    insert_run(u1, "2026-01-03 09:00:00", 5.0)

    insert_run(u2, "2026-01-01 09:00:00", 2.0)
    insert_run(u2, "2026-01-02 09:00:00", 2.0)
    insert_run(u2, "2026-01-04 09:00:00", 2.0)
    insert_run(u2, "2026-01-05 09:00:00", 2.0)

    res_cons = finalize_challenge_if_due(chal_cons)
    assert res_cons["winner_id"] == u2
    assert res_cons["result_type"] == "WIN"

    # 3. LONGEST: u1 single run 15km, u2 runs 10km + 10km (20km total, but longest is 10km) -> u1 wins
    chal_long = create_and_accept_test_challenge(u1, u2, "LONGEST", start_date, end_date)
    insert_run(u1, "2026-01-06 09:00:00", 15.0)
    insert_run(u2, "2026-01-06 08:00:00", 10.0)
    insert_run(u2, "2026-01-06 18:00:00", 10.0)

    res_long = finalize_challenge_if_due(chal_long)
    assert res_long["winner_id"] == u1
    assert res_long["result_type"] == "WIN"

    # 4. DAILY: single day 2026-01-10. u1 = 7km + 3km = 10km, u2 = 8km -> u1 wins
    chal_daily = create_and_accept_test_challenge(u1, u2, "DAILY", "2026-01-10", "2026-01-10")
    insert_run(u1, "2026-01-10 07:00:00", 7.0)
    insert_run(u1, "2026-01-10 17:00:00", 3.0)
    insert_run(u2, "2026-01-10 10:00:00", 8.0)

    res_daily = finalize_challenge_if_due(chal_daily)
    assert res_daily["winner_id"] == u1
    assert res_daily["result_type"] == "WIN"


def test_draw_finalization_awards_no_medal():
    """When a challenge ends in equal scores, result is DRAW and no medal is awarded."""
    u1 = create_user("draw_runner_1", "Runner 1")
    u2 = create_user("draw_runner_2", "Runner 2")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    insert_run(u1, "2026-01-02 08:00:00", 10.0)
    insert_run(u2, "2026-01-03 08:00:00", 10.0)

    res = finalize_challenge_if_due(chal_id)
    assert res["status"] == "COMPLETED"
    assert res["winner_id"] is None
    assert res["result_type"] == "DRAW"

    # Verify no awards in challenge_awards
    conn = get_db()
    awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
    assert len(awards) == 0

    # Verify participants table
    parts = conn.execute("SELECT user_id, result, final_score FROM challenge_participants WHERE challenge_id = ?", (chal_id,)).fetchall()
    conn.close()
    for p in parts:
        assert p["result"] == "DRAW"
        assert round(float(p["final_score"]), 2) == 10.0

    # Stats: draws count = 1, medal count = 0
    stats1 = get_user_friendly_challenge_stats(u1)
    stats2 = get_user_friendly_challenge_stats(u2)
    assert stats1["draws"] == 1
    assert stats1["wins"] == 0
    assert stats1["medal_count"] == 0
    assert stats2["draws"] == 1
    assert stats2["wins"] == 0
    assert stats2["medal_count"] == 0


def test_winner_finalization_idempotent_awards():
    """Winner gets exactly 1 award, loser 0. Calling finalization repeatedly is idempotent."""
    u1 = create_user("winner_u1", "Winner U1")
    u2 = create_user("loser_u2", "Loser U2")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    insert_run(u1, "2026-01-02 08:00:00", 15.0)
    insert_run(u2, "2026-01-03 08:00:00", 10.0)

    # First finalization
    res1 = finalize_challenge_if_due(chal_id)
    assert res1["winner_id"] == u1
    assert res1["result_type"] == "WIN"

    # Second finalization (repeated attempt)
    res2 = finalize_challenge_if_due(chal_id)
    assert res2["winner_id"] == u1

    # Check database: exactly 1 award row for u1, 0 for u2
    conn = get_db()
    awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
    conn.close()
    assert len(awards) == 1
    assert awards[0]["user_id"] == u1
    assert awards[0]["award_type"] == "FRIENDLY_CHALLENGE_WIN"


def test_medal_count_accumulates_cumulative_wins():
    """Winner receives one increment per win. First win = 1, Second win = 2."""
    u1 = create_user("champion_runner", "Champion")
    u2 = create_user("rival_1", "Rival 1")
    u3 = create_user("rival_2", "Rival 2")

    # Win 1
    c1 = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-03")
    insert_run(u1, "2026-01-02 08:00:00", 5.0)
    finalize_challenge_if_due(c1)

    medal1 = get_friendly_challenge_medal(u1)
    assert medal1["earned"] is True
    assert medal1["count"] == 1
    assert medal1["name"] == "Friendly Challenges × 1"

    # Win 2
    c2 = create_and_accept_test_challenge(u1, u3, "DISTANCE", "2026-01-04", "2026-01-06")
    insert_run(u1, "2026-01-05 08:00:00", 7.0)
    finalize_challenge_if_due(c2)

    medal2 = get_friendly_challenge_medal(u1)
    assert medal2["earned"] is True
    assert medal2["count"] == 2
    assert medal2["name"] == "Friendly Challenges × 2"

    # Lose 1 (against rival_1)
    c3 = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-07", "2026-01-09")
    insert_run(u2, "2026-01-08 08:00:00", 12.0)
    finalize_challenge_if_due(c3)

    # Medal count for u1 should remain 2 (losses don't decrement or increment)
    medal3 = get_friendly_challenge_medal(u1)
    assert medal3["count"] == 2
    assert medal3["name"] == "Friendly Challenges × 2"


def test_run_edit_recalibration_and_winner_reversal():
    """Editing a run recalculates scores and safely reverses the award if winner flips."""
    u1 = create_user("init_winner", "Initial Winner")
    u2 = create_user("init_loser", "Initial Loser")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    insert_run(u1, "2026-01-02 08:00:00", 10.0)
    run_id_u2 = insert_run(u2, "2026-01-02 09:00:00", 8.0)

    # Finalize: u1 wins (10km vs 8km)
    finalize_challenge_if_due(chal_id)
    assert get_friendly_challenge_medal(u1)["count"] == 1
    assert get_friendly_challenge_medal(u2)["count"] == 0

    # Edit u2's run to 14.0 km
    conn = get_db()
    conn.execute("UPDATE runs SET distance_km = 14.0 WHERE id = ?", (run_id_u2,))
    conn.commit()
    conn.close()

    # Recalibrate via service
    recalibrate_user_challenges_on_run_change(u2, "2026-01-02")

    # Now u2 has 14km > u1's 10km: Winner flips to u2!
    conn = get_db()
    chal = conn.execute("SELECT winner_id, result_type FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    assert chal["winner_id"] == u2
    assert chal["result_type"] == "WIN"

    # Verify awards: u1 award reversed, u2 granted award
    awards = conn.execute("SELECT user_id FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
    assert len(awards) == 1
    assert awards[0]["user_id"] == u2

    # Verify audit trail
    activity = conn.execute("SELECT * FROM challenge_activity WHERE challenge_id = ? AND activity_type = 'RECALIBRATED'", (chal_id,)).fetchall()
    assert len(activity) == 1
    meta = json.loads(activity[0]["metadata"])
    assert meta["old_winner_id"] == u1
    assert meta["new_winner_id"] == u2
    conn.close()

    assert get_friendly_challenge_medal(u1)["count"] == 0
    assert get_friendly_challenge_medal(u2)["count"] == 1


def test_run_deletion_recalibration_to_draw():
    """Deleting a qualifying run recalculates scores and safely reverses awards if outcome becomes DRAW."""
    u1 = create_user("del_runner_1", "Runner 1")
    u2 = create_user("del_runner_2", "Runner 2")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    insert_run(u1, "2026-01-02 08:00:00", 5.0)
    run_extra = insert_run(u1, "2026-01-03 08:00:00", 5.0) # total 10.0 km
    insert_run(u2, "2026-01-02 09:00:00", 5.0) # total 5.0 km

    finalize_challenge_if_due(chal_id)
    assert get_friendly_challenge_medal(u1)["count"] == 1

    # Delete u1's second run
    conn = get_db()
    conn.execute("DELETE FROM runs WHERE id = ?", (run_extra,))
    conn.commit()
    conn.close()

    # Recalibrate
    recalibrate_user_challenges_on_run_change(u1, "2026-01-03")

    # Now both have 5.0km: Result is DRAW, u1's award is removed!
    conn = get_db()
    chal = conn.execute("SELECT winner_id, result_type FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    assert chal["winner_id"] is None
    assert chal["result_type"] == "DRAW"

    awards = conn.execute("SELECT * FROM challenge_awards WHERE challenge_id = ?", (chal_id,)).fetchall()
    assert len(awards) == 0
    conn.close()

    assert get_friendly_challenge_medal(u1)["count"] == 0
    assert get_friendly_challenge_medal(u2)["count"] == 0


def test_public_profile_and_badges_api_render_medal(client):
    """Badge system integrates Friendly Challenges medal across public profiles and /api/badges."""
    u1 = create_user("profile_champ", "Profile Champion")
    u2 = create_user("profile_challenger", "Challenger")

    # Initially 0 wins -> locked medal
    medals_init = get_badges_status_for_user(u1)
    fc_badge = next((b for b in medals_init if b["key"] == "FRIENDLY_CHALLENGES"), None)
    assert fc_badge is not None
    assert fc_badge["earned"] is False
    assert fc_badge["name"] == "Friendly Challenges"

    # Win 2 challenges
    c1 = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-03")
    insert_run(u1, "2026-01-02 08:00:00", 10.0)
    finalize_challenge_if_due(c1)

    c2 = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-04", "2026-01-06")
    insert_run(u1, "2026-01-05 08:00:00", 12.0)
    finalize_challenge_if_due(c2)

    # Inspect get_badges_status_for_user
    medals_after = get_badges_status_for_user(u1)
    fc_badge_after = next((b for b in medals_after if b["key"] == "FRIENDLY_CHALLENGES"), None)
    assert fc_badge_after is not None
    assert fc_badge_after["earned"] is True
    assert fc_badge_after["name"] == "Friendly Challenges × 2"
    assert fc_badge_after["icon"] == "⚔️"

    # Inspect public profile endpoint
    with client.session_transaction() as sess:
        sess["user_id"] = u1
    res = client.get("/api/user/profile_champ/public-profile")
    assert res.status_code == 200
    pdata = res.get_json()
    p_fc = next((b for b in pdata["badges"] if b["key"] == "FRIENDLY_CHALLENGES"), None)
    assert p_fc is not None
    assert p_fc["earned"] is True
    assert p_fc["name"] == "Friendly Challenges × 2"

    # Inspect /api/badges endpoint
    res_b = client.get("/api/badges")
    assert res_b.status_code == 200
    bdata = res_b.get_json()
    b_fc = next((b for b in bdata["badges"] if b["key"] == "FRIENDLY_CHALLENGES"), None)
    assert b_fc is not None
    assert b_fc["earned"] is True
    assert b_fc["name"] == "Friendly Challenges × 2"


def test_finalization_notification_dispatched():
    """Finalization creates appropriate notifications for participants."""
    u1 = create_user("notif_winner", "Notif Winner")
    u2 = create_user("notif_loser", "Notif Loser")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    insert_run(u1, "2026-01-02 08:00:00", 10.0)
    finalize_challenge_if_due(chal_id)

    conn = get_db()
    notifs = conn.execute("SELECT * FROM notifications WHERE type = 'CHALLENGE_RESULT'").fetchall()
    conn.close()

    assert len(notifs) >= 2
    titles = [n["title"] for n in notifs]
    assert any("Victory" in t for t in titles)
    assert any("Completed" in t for t in titles)


def test_delete_run_endpoint_triggers_recalibration(client):
    """The /delete/<id> route executes recalibration and adjusts challenge awards."""
    u1 = create_user("route_del_winner", "Winner")
    u2 = create_user("route_del_loser", "Loser")

    chal_id = create_and_accept_test_challenge(u1, u2, "DISTANCE", "2026-01-01", "2026-01-05")
    run1 = insert_run(u1, "2026-01-02 08:00:00", 12.0)
    insert_run(u2, "2026-01-02 09:00:00", 8.0)

    # Finalize: u1 has 1 award
    finalize_challenge_if_due(chal_id)
    assert get_friendly_challenge_medal(u1)["count"] == 1

    # Now u1 deletes their winning run via the web route
    with client.session_transaction() as sess:
        sess["user_id"] = u1

    res = client.post(f"/delete/{run1}", follow_redirects=False)
    assert res.status_code == 302 # Redirect to index

    # Winner should now have flipped to u2 (8km vs 0km)!
    conn = get_db()
    chal = conn.execute("SELECT winner_id, result_type FROM friendly_challenges WHERE id = ?", (chal_id,)).fetchone()
    conn.close()

    assert chal["winner_id"] == u2
    assert chal["result_type"] == "WIN"
    assert get_friendly_challenge_medal(u1)["count"] == 0
    assert get_friendly_challenge_medal(u2)["count"] == 1

