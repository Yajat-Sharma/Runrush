"""
PIN Recovery Service.

Handles:
  - Generating & hashing cryptographically-secure 6-digit codes
  - Persisting recovery records to `pin_resets` table
  - Sending recovery / recovery-email-verification emails via Resend
  - Verifying submitted codes
  - Masking email addresses for display (no enumeration)

Security notes:
  - Codes are NEVER stored in plaintext — only bcrypt-hashed.
  - Codes are NEVER logged or returned to the browser.
  - Each new code request invalidates any prior active code for that user.
  - Codes expire after PIN_RESET_EXPIRY_SECONDS (900 = 15 min).
  - After PIN_RESET_MAX_ATTEMPTS wrong guesses the record is marked used.
  - Rate-limiting (3 emails/hr per user) is enforced here via the DB.
"""

import os
import json
import secrets
import urllib.request as _url_req
import urllib.error  as _url_err
from datetime import datetime, timedelta

from db import get_db
from extensions import bcrypt

# ── Configuration ──────────────────────────────────────────────
PIN_RESET_EXPIRY_SECONDS  = 900   # 15 minutes
PIN_RESET_MAX_ATTEMPTS    = 5
PIN_RESET_MAX_EMAILS_PER_HOUR = 3  # per user_id per hour


# ── Internal helpers ────────────────────────────────────────────

def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _send_via_resend(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email through the existing Resend integration (stdlib urllib only)."""
    api_key    = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "RunRush <noreply@runrush.app>")

    if not api_key:
        return False

    payload = json.dumps({
        "from":    from_email,
        "to":      [to_email],
        "subject": subject,
        "html":    html_body,
    }).encode("utf-8")

    req = _url_req.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
    )
    try:
        with _url_req.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (_url_err.URLError, Exception):
        return False


def mask_email(email: str) -> str:
    """Return j***@domain.com for display — never expose the full address."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


# ── Rate-limit check ────────────────────────────────────────────

def _count_recent_emails(conn, user_id: int) -> int:
    """Count recovery emails sent to this user in the last hour."""
    cutoff = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM pin_resets "
        "WHERE user_id = ? AND created_at > ?",
        (user_id, cutoff),
    ).fetchone()
    return row["cnt"] if row else 0


# ── Public API ──────────────────────────────────────────────────

def generate_and_send_recovery_code(user_id: int, to_email: str, username: str) -> tuple[bool, str]:
    """
    Generate a 6-digit code, hash it, store it, send it via Resend.

    Returns (True, "") on success or (False, error_reason) on failure.
    Never returns or logs the plaintext code.
    """
    conn = get_db()
    try:
        # Rate-limit: max 3 requests per hour
        if _count_recent_emails(conn, user_id) >= PIN_RESET_MAX_EMAILS_PER_HOUR:
            return False, "rate_limited"

        # Invalidate any existing active code for this user
        conn.execute(
            "UPDATE pin_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
            (_now_str(), user_id),
        )

        # Generate 6-digit code (cryptographically secure)
        code_int  = secrets.randbelow(900000) + 100000   # 100000–999999
        code_str  = str(code_int)

        # Hash the code — never store plaintext
        code_hash = bcrypt.generate_password_hash(code_str)

        expires_at = (datetime.utcnow() + timedelta(seconds=PIN_RESET_EXPIRY_SECONDS)
                      ).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT INTO pin_resets
               (user_id, code_hash, expires_at, attempts, created_at)
               VALUES (?, ?, ?, 0, ?)""",
            (user_id, code_hash, expires_at, _now_str()),
        )
        conn.commit()

        # Send email
        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;background:#09090f;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:480px;margin:0 auto;background:#0d0d1a;border-radius:20px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#b0ff4f 0%,#00f2ff 100%);
              padding:28px;text-align:center;">
    <div style="font-size:2rem;">🔑</div>
    <h1 style="margin:8px 0 4px;color:#000;font-size:1.4rem;font-weight:800;">RunRush</h1>
    <p style="margin:0;color:rgba(0,0,0,0.65);font-size:0.9rem;">PIN Recovery Code</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#ccc;margin-top:0;">
      Hi <strong style="color:#fff;">{username}</strong>,<br>
      Use the code below to reset your RunRush PIN.
      It expires in <strong style="color:#b0ff4f;">15 minutes</strong>.
    </p>
    <div style="background:#1a1a2e;border-radius:12px;padding:22px;
                text-align:center;margin:20px 0;
                border:1px solid rgba(176,255,79,0.25);">
      <div style="font-size:2.4rem;font-weight:800;letter-spacing:0.3em;color:#b0ff4f;">
        {code_str}
      </div>
      <div style="color:#555;font-size:0.78rem;margin-top:8px;">
        YOUR 6-DIGIT RECOVERY CODE
      </div>
    </div>
    <p style="color:#666;font-size:0.82rem;">
      If you did not request a PIN reset, ignore this email.
      Your PIN remains unchanged.
    </p>
    <p style="color:#444;font-size:0.75rem;text-align:center;margin-top:24px;">
      This code will expire after one use or in 15 minutes.
    </p>
  </div>
</div>
</body></html>"""

        sent = _send_via_resend(to_email, "Your RunRush PIN Recovery Code", html_body)
        if not sent:
            return False, "email_failed"

        return True, ""

    finally:
        conn.close()


def verify_recovery_code(user_id: int, submitted_code: str) -> tuple[bool, str]:
    """
    Verify a submitted 6-digit code against the latest active record.

    Returns (True, "") on success or (False, reason) on failure.
    Increments attempt counter; marks record as used on success or max attempts.
    """
    conn = get_db()
    try:
        now_str = _now_str()

        # Fetch most recent active (unused, unexpired) record
        record = conn.execute(
            """SELECT * FROM pin_resets
               WHERE user_id = ? AND used_at IS NULL AND expires_at > ?
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, now_str),
        ).fetchone()

        if not record:
            return False, "no_active_code"

        if record["attempts"] >= PIN_RESET_MAX_ATTEMPTS:
            # Mark exhausted
            conn.execute(
                "UPDATE pin_resets SET used_at = ? WHERE id = ?",
                (now_str, record["id"]),
            )
            conn.commit()
            return False, "max_attempts"

        # Increment attempts first (before verifying) — prevents timing oracle
        conn.execute(
            "UPDATE pin_resets SET attempts = attempts + 1 WHERE id = ?",
            (record["id"],),
        )
        conn.commit()

        if not bcrypt.check_password_hash(record["code_hash"], submitted_code):
            remaining = PIN_RESET_MAX_ATTEMPTS - (record["attempts"] + 1)
            if remaining <= 0:
                conn.execute(
                    "UPDATE pin_resets SET used_at = ? WHERE id = ?",
                    (now_str, record["id"]),
                )
                conn.commit()
                return False, "max_attempts"
            return False, "wrong_code"

        # Valid — mark as used (single-use enforcement)
        conn.execute(
            "UPDATE pin_resets SET used_at = ? WHERE id = ?",
            (now_str, record["id"]),
        )
        conn.commit()
        return True, ""

    finally:
        conn.close()


def generate_and_send_verification_email(user_id: int, to_email: str, username: str) -> tuple[bool, str]:
    """
    Send a 6-digit code to verify a *recovery email* address.
    Reuses the same pin_resets table (type differentiation by context).
    """
    # Identical flow to recovery code — reuse table, different email body
    conn = get_db()
    try:
        if _count_recent_emails(conn, user_id) >= PIN_RESET_MAX_EMAILS_PER_HOUR:
            return False, "rate_limited"

        conn.execute(
            "UPDATE pin_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
            (_now_str(), user_id),
        )

        code_int  = secrets.randbelow(900000) + 100000
        code_str  = str(code_int)
        code_hash = bcrypt.generate_password_hash(code_str)
        expires_at = (datetime.utcnow() + timedelta(seconds=PIN_RESET_EXPIRY_SECONDS)
                      ).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            """INSERT INTO pin_resets
               (user_id, code_hash, expires_at, attempts, created_at)
               VALUES (?, ?, ?, 0, ?)""",
            (user_id, code_hash, expires_at, _now_str()),
        )
        conn.commit()

        html_body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:20px;background:#09090f;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:480px;margin:0 auto;background:#0d0d1a;border-radius:20px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#4dadff 0%,#b0ff4f 100%);
              padding:28px;text-align:center;">
    <div style="font-size:2rem;">📧</div>
    <h1 style="margin:8px 0 4px;color:#000;font-size:1.4rem;font-weight:800;">RunRush</h1>
    <p style="margin:0;color:rgba(0,0,0,0.65);font-size:0.9rem;">Verify Your Recovery Email</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#ccc;margin-top:0;">
      Hi <strong style="color:#fff;">{username}</strong>,<br>
      Enter the code below in RunRush to verify this email address
      as your account recovery email.
    </p>
    <div style="background:#1a1a2e;border-radius:12px;padding:22px;
                text-align:center;margin:20px 0;
                border:1px solid rgba(77,173,255,0.25);">
      <div style="font-size:2.4rem;font-weight:800;letter-spacing:0.3em;color:#4dadff;">
        {code_str}
      </div>
      <div style="color:#555;font-size:0.78rem;margin-top:8px;">
        YOUR 6-DIGIT VERIFICATION CODE
      </div>
    </div>
    <p style="color:#666;font-size:0.82rem;">
      If you did not make this request, ignore this email.
    </p>
  </div>
</div>
</body></html>"""

        sent = _send_via_resend(to_email, "Verify Your RunRush Recovery Email", html_body)
        if not sent:
            return False, "email_failed"

        return True, ""

    finally:
        conn.close()
