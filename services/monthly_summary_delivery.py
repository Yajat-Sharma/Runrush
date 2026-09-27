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


def _claim_delivery(conn, user_id, year, month, force=False):
    """
    Atomically claims (user_id, year, month) for processing, in a single
    INSERT ... ON CONFLICT ... DO UPDATE ... WHERE ... RETURNING statement.
    This is the fix for the audit's concurrency finding: the previous
    implementation did a SELECT to check "already sent?", then later did a
    separate INSERT/UPDATE after the Resend call completed -- two
    concurrent callers could both pass the SELECT check and both reach
    Resend before either write landed. There is no such window here: the
    claim is a single statement, atomic at the database level (enforced by
    the UNIQUE(user_id, year, month) constraint + the engine's own conflict
    resolution), so it works across separate connections/processes, not
    just within one Python process.

    Returns the claimed delivery row's id on success, or None if it could
    not be claimed (another PENDING or a completed SENT row already exists)
    -- callers MUST NOT call Resend unless this returns a non-None id.

    Claim succeeds when:
      - no row exists yet for this (user_id, year, month), OR
      - the existing row's status is FAILED (a retry is always allowed), OR
      - force=True (explicit manual resend/retry, bypasses the FAILED-only
        restriction so it can also reclaim a SENT or stuck PENDING row)

    Claim fails (returns None, force=False) when the existing row's status
    is PENDING (another request is already handling it right now) or SENT
    (already delivered) -- Resend is never called in either case.

    SQLite note: this relies on SQLite's UPSERT support (3.24+) including
    the conditional "DO UPDATE ... WHERE" filter (3.35+), present in the
    sqlite3 module bundled with the Python versions this project uses.
    Under SQLite's coarser file-level write locking, a genuinely
    concurrent second writer may raise sqlite3.OperationalError("database
    is locked") instead of cleanly returning zero rows from RETURNING --
    that is caught below and treated identically to "could not claim".
    This is a weaker guarantee than Postgres's row-level MVCC locking, but
    SQLite is only used for local dev/tests here; production runs
    Postgres, where the ON CONFLICT statement itself serializes concurrent
    claims via the unique index with no separate locking code needed.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    where_clause = "" if force else "WHERE monthly_summary_deliveries.status = 'FAILED'"
    try:
        cur = conn.execute(
            f"""
            INSERT INTO monthly_summary_deliveries
                (user_id, year, month, status, error, sent_at, created_at, updated_at)
            VALUES (?, ?, ?, 'PENDING', NULL, NULL, ?, ?)
            ON CONFLICT (user_id, year, month) DO UPDATE SET
                status = 'PENDING',
                error = NULL,
                updated_at = excluded.updated_at
            {where_clause}
            RETURNING id
            """,
            (user_id, year, month, now_str, now_str),
        )
        row = cur.fetchone()
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None

    if not row:
        return None
    return row["id"]


def _finalize_delivery(conn, delivery_id, status, error=None, sent_at=None):
    """Transitions a claimed (PENDING) row to its terminal state (SENT or
    FAILED). Always called from a try/except in send_monthly_summary_email
    so a PENDING claim is never left stuck -- see FIX 1/FIX 2 notes there."""
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE monthly_summary_deliveries SET status = ?, error = ?, sent_at = ?, updated_at = ? WHERE id = ?",
        (status, error, sent_at, now_str, delivery_id),
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

    Idempotent via an atomic delivery claim (see _claim_delivery): Resend
    is never called unless this process/request successfully claimed the
    (user_id, year, month) slot first. If a SENT delivery already exists,
    or another request currently holds the PENDING claim, this returns
    status='skipped' without touching Resend. Pass force=True to resend
    deliberately (e.g. a manual admin resend), which bypasses the
    FAILED-only retry restriction.

    Never raises for expected OR unexpected failure modes — no email on
    file, opted out, no API key configured, a render error, a Resend
    error, or any other unexpected exception during build/render/send are
    all caught and turned into a result dict, so a caller iterating many
    users can continue past a single failure without wrapping every call
    in its own try/except. A claimed (PENDING) row is *always* transitioned
    to a terminal SENT or FAILED state in the same try/except that does
    the send — it can never be left stuck at PENDING after a recoverable
    failure.

    A delivery row is only ever written for an actual send *attempt*
    (PENDING -> SENT or PENDING -> FAILED) — "ineligible" cases (no email,
    opted out, no API key) are not recorded as deliveries, since nothing
    was attempted to fail or succeed at.
    """
    conn = get_db()

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

    delivery_id = _claim_delivery(conn, user_id, year, month, force=force)
    if delivery_id is None:
        existing = _get_delivery(conn, user_id, year, month)
        conn.close()
        if existing and existing["status"] == DELIVERY_STATUS_SENT:
            return {"status": "skipped", "reason": "already_sent"}
        return {"status": "skipped", "reason": "claim_in_progress"}

    # Everything from here on happens only because THIS call won the claim.
    # Any failure, expected or not, must transition PENDING -> FAILED so
    # the row is retryable and never left stuck.
    try:
        summary = build_monthly_summary(user_id, year, month)
        subject = render_subject(summary)
        html_body = render_html(summary)
        ok, error = _post_to_resend(api_key, from_email, email, subject, html_body)
    except Exception as e:
        ok, error = False, f"{type(e).__name__}: {e}"

    if ok:
        sent_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        _finalize_delivery(conn, delivery_id, DELIVERY_STATUS_SENT, error=None, sent_at=sent_at)
        conn.close()
        return {"status": "sent"}

    _finalize_delivery(conn, delivery_id, DELIVERY_STATUS_FAILED, error=error, sent_at=None)
    conn.close()
    return {"status": "failed", "reason": error}


def send_monthly_summaries_for_all_eligible_users(year, month):
    """
    Sends the given month's summary to every eligible user (has an email,
    hasn't opted out), continuing past individual failures — one user's
    error never stops the rest of the batch. Returns a tally plus
    per-user detail, mirroring the shape app.py's
    POST /api/trigger-weekly-emails already returns for the weekly job.

    send_monthly_summary_email() already catches every failure mode it
    knows about (see its docstring) and always returns a result dict — but
    this loop wraps each call in its own try/except anyway, as a second
    line of defense: an exception raised *before* reaching that function's
    own try block (e.g. get_db() itself failing for user uid) must still
    not abort processing of the remaining users. Nothing is swallowed
    silently — an unexpected exception here is recorded in `tally` under
    'failed' and in `details` with the exception message, exactly like an
    expected Resend failure would be.
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
        try:
            result = send_monthly_summary_email(uid, year, month)
        except Exception as e:
            result = {"status": "failed", "reason": f"unexpected error: {type(e).__name__}: {e}"}
        status = result["status"]
        tally[status] = tally.get(status, 0) + 1
        details.append({"user_id": uid, **result})

    return {"tally": tally, "details": details}
