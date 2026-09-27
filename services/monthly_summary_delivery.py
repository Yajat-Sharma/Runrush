"""
Monthly summary delivery — sends one user's rendered summary via Resend and
tracks delivery status in monthly_summary_deliveries, so the same
(user_id, year, month) is never sent twice even if the batch job runs
more than once.

Completes the layering: MonthlySummaryService -> MonthlySummary ->
monthly_summary_renderer (subject, html) -> this module (transport +
idempotency). No Flask/HTTP here — the route layer (a later addition)
just calls send_monthly_summaries_for_all_eligible_users() and returns
its result as JSON, mirroring app.py's existing
POST /api/trigger-weekly-emails / send_weekly_summary() split.
"""

import os
from datetime import datetime

from db import get_db
from services.monthly_summary_service import build_monthly_summary
from services.monthly_summary_renderer import render_subject, render_html

DELIVERY_STATUS_PENDING = "PENDING"
DELIVERY_STATUS_SENT = "SENT"
DELIVERY_STATUS_FAILED = "FAILED"


def _get_delivery(conn, user_id, year, month):
    row = conn.execute(
        "SELECT * FROM monthly_summary_deliveries WHERE user_id = ? AND year = ? AND month = ?",
        (user_id, year, month),
    ).fetchone()
    return dict(row) if row else None


def _upsert_delivery(conn, user_id, year, month, status, error=None, sent_at=None):
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    existing = _get_delivery(conn, user_id, year, month)
    if existing:
        conn.execute(
            "UPDATE monthly_summary_deliveries SET status = ?, error = ?, sent_at = ?, updated_at = ? WHERE id = ?",
            (status, error, sent_at, now_str, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO monthly_summary_deliveries "
            "(user_id, year, month, status, error, sent_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, year, month, status, error, sent_at, now_str, now_str),
        )
    conn.commit()


def _post_to_resend(api_key, from_email, to_email, subject, html_body):
    """Same stdlib-urllib POST pattern as app.py's send_weekly_summary() and
    services/pin_recovery_service.py's _send_via_resend(). Kept local to
    this module rather than extracted into a shared helper — the existing
    call sites are out of scope for this feature (see architectural notes
    in the project's Phase 0 audit; not refactoring them here)."""
    import json as _json
    import urllib.request as _url_req
    import urllib.error as _url_err

    payload = _json.dumps({
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }).encode("utf-8")

    req = _url_req.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with _url_req.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, None
            return False, f"Resend returned status {resp.status}"
    except _url_err.HTTPError as e:
        return False, f"HTTPError {e.code}: {e.reason}"
    except _url_err.URLError as e:
        return False, f"URLError: {e.reason}"
    except Exception as e:  # defensive: a send failure must never crash the batch
        return False, str(e)


def send_monthly_summary_email(user_id, year, month, force=False):
    """
    Build, render, and send one user's monthly summary email.

    Idempotent by default: if a SENT delivery already exists for this
    (user_id, year, month), this is a no-op — returns status='skipped'
    without calling Resend again. Pass force=True to resend deliberately
    (e.g. a manual admin resend), which is the only path that bypasses the
    guard.

    Never raises for expected failure modes (no email on file, opted out,
    no API key configured, render error, Resend error) — always returns a
    result dict, so a caller iterating many users can continue past a
    single failure without a try/except at each call site.

    A delivery row is only ever written for an actual send *attempt*
    (SENT or FAILED) — "ineligible" cases (no email, opted out, no API key)
    are not recorded as deliveries, since nothing was attempted to fail or
    succeed at.
    """
    conn = get_db()

    existing = _get_delivery(conn, user_id, year, month)
    if existing and existing["status"] == DELIVERY_STATUS_SENT and not force:
        conn.close()
        return {"status": "skipped", "reason": "already_sent"}

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return {"status": "ineligible", "reason": "no_such_user"}
    user = dict(user)

    email = user.get("email")
    opted_in = user.get("email_monthly_summary")
    opted_in = 1 if opted_in is None else opted_in  # column defaults to 1
    if not email or not opted_in:
        conn.close()
        return {"status": "ineligible", "reason": "no_email_or_opted_out"}

    api_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "RunRush <noreply@runrush.app>")
    if not api_key:
        conn.close()
        return {"status": "ineligible", "reason": "no_api_key_configured"}

    try:
        summary = build_monthly_summary(user_id, year, month)
    except ValueError as e:
        conn.close()
        return {"status": "failed", "reason": str(e)}

    subject = render_subject(summary)
    html_body = render_html(summary)

    ok, error = _post_to_resend(api_key, from_email, email, subject, html_body)

    if ok:
        sent_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _upsert_delivery(conn, user_id, year, month, DELIVERY_STATUS_SENT, error=None, sent_at=sent_at)
        conn.close()
        return {"status": "sent"}

    _upsert_delivery(conn, user_id, year, month, DELIVERY_STATUS_FAILED, error=error, sent_at=None)
    conn.close()
    return {"status": "failed", "reason": error}


def send_monthly_summaries_for_all_eligible_users(year, month):
    """
    Sends the given month's summary to every eligible user (has an email,
    hasn't opted out), continuing past individual failures — one user's
    error never stops the rest of the batch. Returns a tally plus
    per-user detail, mirroring the shape app.py's
    POST /api/trigger-weekly-emails already returns for the weekly job.
    """
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM users WHERE email IS NOT NULL AND email != '' "
        "AND COALESCE(email_monthly_summary, 1) = 1"
    ).fetchall()
    user_ids = [r["id"] for r in rows]
    conn.close()

    tally = {"sent": 0, "failed": 0, "skipped": 0, "ineligible": 0}
    details = []
    for uid in user_ids:
        result = send_monthly_summary_email(uid, year, month)
        status = result["status"]
        tally[status] = tally.get(status, 0) + 1
        details.append({"user_id": uid, **result})

    return {"tally": tally, "details": details}
