# RunRush — Full Codebase Engineering Audit

**Date:** 2026-09-22 (UTC)
**Scope:** `D:\Programming codes\Running-py` — full tree, `main` @ `a72c8c4`
**Mode:** REVIEW ONLY — no app logic, schema, migration, dependency, env, or history changes made.
**Verification:** `python -m pytest tests/ -q` → **195 passed, 2 failed** (see Testing). `git status --short` clean before and after.

---

## Executive Summary

RunRush is a Flask monolith (∼6000-line `app.py`) with a Vanilla JS + Bootstrap PWA frontend, dual SQLite (dev) / PostgreSQL (prod) storage via a custom `db.py` wrapper, `yoyo-migrations` SQL migrations, and a `tests/` pytest suite.

FACT: the system works as an MVP and has real hardening — SECRET_KEY startup guard (`app.py:36-46`), unified `?`→`%s` SQL wrapper, per-request `close_db(force=True)` teardown (`db.py:225-229`), `bleach` notes sanitization (`utils/validators.py`), PIN hashing, CSRF + rate limiting, pool health-check (`db.py:170-177`), prod-migration policy docs (`migrations/README.md`).

INFERENCE: the dominant risks are structural, not missing features: (1) an unauthenticated debug login, (2) startup auto-DDL that diverges from migrations/`schema.sql`, (3) a 334 KB / 7394-line `templates/index.html` monolith, (4) dead `blueprints/` duplication, (5) PG/SQLite semantic drift hidden by string-casting timestamps, (6) unpinned heavy deps, (7) minimal prod server config, (8) test-suite drift (2 failing layout tests).

No simplistic score is given. See Risk Register for what blocks expansion.

---

## System Architecture

FACT (traced):

```
Browser/PWA (templates/*.html + static/js/*.js + sw.js + IndexedDB)
  → Flask app.py (~5998 lines, ~80 routes) + blueprints/* (unregistered, dead)
  → services/* (auth, run, streak, badge, challenge, goal, pet, weather, pin_recovery)
  → utils/* (validators, decorators, dates, rate_limiter)
  → db.py (SQLite sqlite3 / PG psycopg2 SimpleConnectionPool 1-20 + ?→%s wrapper)
  → SQLite runs.db (dev) / PostgreSQL (prod via DATABASE_URL)
  → migrations/*.sql via yoyo (MIGRATION_DATABASE_URL, never auto-run per README)
  → gunicorn bind only (gunicorn.conf.py) + Render + CI (.github/workflows/python-app.yml)
```

- Entry: `app.py:25 Flask(__name__)`, `teardown_appcontext(close_db)`, `if __name__ == "__main__": app.run(debug=True...)` (`app.py:5996-5997`).
- Routes: all live routes are `@app.route` in `app.py` (e.g. `/dashboard:1138`, `/add:1571`, `/api/sync-run:1741`, `/api/dashboard-layout:5704/5750`, `/admin:4363`). `blueprints/*` + `blueprints/api/v1/*` define parallel routes but **no `register_blueprint` call exists in `app.py`** (grep: zero hits) — dead code.
- Auth: `require_login()` (`app.py:697-698`) is `return "user_id" in session` — inline `if not require_login()` per route, not a decorator. `utils/decorators.py` provides `login_required/admin_required` but `app.py` does not use them.
- `before_request check_pin_setup` (`app.py:767-784`) queries `SELECT pin` on every authenticated request.
- PWA: `static/sw.js` (cache-first static/CDN, network-first pages, network-only `/api/`, IndexedDB via `offline-storage.js` + `sync-engine.js` + `/api/sync-run`).
- Config: `config.py` classes exist but `app.py` does **not** load them via `from_object`; it sets `secret_key`, `csrf`, `limiter`, `bcrypt` directly. `config.py` is effectively reference-only.

Where ownership is clear: `services/` (domain logic), `utils/validators.py` (validation), `db.py` (dialect shim), `sw.js` (caching policy).
Where mixed: `app.py` owns routing + validation + SQL + HTML context building + ML + email + OAuth (~6000 lines); `init_db()` owns DDL that should belong to migrations; `config.py` vs inline config; live `app.py` routes vs dead `blueprints/`.

---

## Repository Inventory

FACT — counts from `glob` + `Get-ChildItem`:

**Production code (KEEP):**
- `app.py` (5998 lines), `db.py` (229), `config.py` (103), `extensions.py` (49), `ml_predictor.py` (227), `models/user.py`, `services/*.py` (9 files: auth, badge, challenge, goal, pet, pin_recovery, run, streak, weather), `utils/*.py` (validators, decorators, dates, rate_limiter), `templates/*.html` (18 files), `static/js/*.js` (7), `static/css/*.css` (2), `static/sw.js`, `static/manifest.json`, `static/icons/*`, `migrations/*.sql` (001-005 + README), `schema.sql`, `requirements.txt`, `gunicorn.conf.py`, `.github/workflows/python-app.yml`, `.env.example`, `README.md`, `PROJECT_SUMMARY.md`, `LICENSE`, `docs/*.md` (16 files).

**Permanent tests (KEEP):**
- `tests/*.py` (21 files + `conftest.py` + `__init__.py`): auth, goals, weekly_goal, monthly_goals, challenges, badges via insights, pets, pet_backend, leaderboard_qualification, public_profile, dashboard_layout, screenshot_import, ml_predictor, validators, date_utils, rate_limiter, google_auth, db_guardrail, smoke_guardrail.

**Reusable dev tools (KEEP, move out of root if desired):**
- `scripts/*` (migrate_to_pg, migrate_db, view_users, view_schema, test_db_layer, screenshot_*, move_progress, simulate_shortfall, legacy_add_badges_system), `audit_db.py`, `check_db.py`, `check_schema.py`, `check_render_db.py`, `apply_migration.py`, `validate.py`, `smoke_test.py`, `verify_prod.py`, `scratch/*` (debug_login, check_tables, check_db, check_badges, apply_sql).

**Temporary / debug artifacts (MOVE or DELETE after reference trace — see Test/Debug Artifact Audit):**
- Root `test_*.py` (13 files: `test_api`, `test_db`, `test_jsonify`, `test_local`, `test_mock`, `test_monthly_progress`, `test_pg`, `test_regex`, `test_recovery`, `test_server`, `test_server_proper`, `test_sqlite`, `test_sqlite_proper`, plus `test.py`, `test2.py`), `scratch_query.py`, `fix_clean.py`, `fix_clean_correct.py`, `capture_screenshots.py`, `generate_screenshots.py`, `qa_leaderboard_screenshot.py`, `live_profile.js`, `check_results.txt`, `emojis_found.txt`, `final_clean_diff.txt` (376 KB), `final_verify_diff.txt` (375 KB), `index_bad.html` (340 KB), `index_new_clean.html`, `index_old_clean.html`, `render_output.html`, `error.png`, `test_screenshot.jpg`, `qa_screenshots/`, `*.db` (`runs.db` 127 KB, `test_runs.db`, `test_reproduce.db`, zero-byte `database.db`/`running.db`/`runrush.db`), `*.log` (`pytest_full.log`, `pytest_pet.log`), `.pytest_cache/`, `__pycache__/`, `.venv/` (inflates file counts; `*.py` 12400 hits include venv).

**Generated (DO NOT EDIT, ensure ignored):**
- `__pycache__/`, `.pytest_cache/`, `*.db` (ignored via `.gitignore`), `*.log` (ignored).

**Dead / duplicate candidates (traced, not assumed):**
- `blueprints/*.py` + `blueprints/api/v1/*.py` — dead (never registered). `grep register_blueprint app.py` = 0 hits. FACT.
- `schema.py` (6 lines) — not a schema; it queries `information_schema` for `users` columns. Misnamed debug helper.
- `models/user.py` vs inline `get_current_user()`/`get_user_role()` in `app.py:787-813` — parallel user logic.
- `utils/decorators.py` vs `app.py:require_login()` — parallel auth enforcement.
- `config.py` vs inline app config — parallel config.
- `schema.sql` vs `migrations/001_initial_schema.sql` vs `app.py:init_db()` PG branch vs SQLite branch — four DDL sources (see DB findings).

---

## Backend Findings

### [P0] Unauthenticated debug login `/testlogin` hardcodes session

**Area:** Backend / Security
**Evidence:** `app.py:1108-1115`
```python
@app.route('/testlogin')
def testlogin():
    session['user_id'] = 3
    session['username'] = 'Himanshu'
    ...
    return redirect(url_for('index'))
```
**What is happening:** Any visitor can become user 3 without PIN/OAuth. No env guard, no `TESTING` check, no rate limit.
**Impact:** Full account takeover of id 3 on any deploy where route exists (including prod if deployed from `main`).
**Recommendation:** Delete route. If needed for local dev, guard with `if not app.debug or os.environ.get("ALLOW_TESTLOGIN")!="1": abort(404)` and never merge to `main`.
**Priority:** P0
FACT: route exists on `main`, no guard. INFERENCE: likely leftover from `1eee80c Add testlogin route`.

### [P1] `blueprints/` is dead — all live routes duplicated in `app.py`

**Area:** Backend / Maintainability
**Evidence:** `blueprints/auth.py:13,36,74`, `runs.py:15,63,76,85`, `social.py:11,19,27,35`, `dashboard.py:13,22`, `admin.py:11,20,29`, `api/v1/*.py`; `grep register_blueprint app.py` = 0.
**What is happening:** Two route systems exist; only `app.py` serves traffic.
**Impact:** Contributors edit dead files; fixes diverge; API v1 (`/api/v1/runs|sync|users`) is documented but unreachable.
**Recommendation:** Decide: either register blueprints and migrate routes incrementally, or delete `blueprints/` and keep monolith explicitly. Do not leave both.
**Priority:** P1
FACT: no registration. INFERENCE: migration started, never finished.

### [P1] `init_db()` performs startup auto-DDL diverging from migrations

**Area:** Backend / DB
**Evidence:** `app.py:81-~680` — `CREATE TABLE IF NOT EXISTS` + ~30 `ALTER TABLE ... ADD COLUMN` with bare `except Exception` + `print DEBUG: init_db using conn` (`app.py:337`).
**What is happening:** App mutates schema at import/CLI time, independent of `yoyo` history.
**Impact:** Schema drift (PG branch lacks `profile_emoji` default consistency, `monthly_goals`, `user_pets` partial, onboarding fields, `user_dashboard_layout`); `IF NOT EXISTS` without type checks hides mismatches; bare excepts hide failures; contradicts `migrations/README.md` rule 1 ("MUST NOT run automatically").
**Recommendation:** Freeze `init_db()` to bootstrap-only for fresh SQLite dev; remove ALTERs; make PG authoritative via `schema.sql` + yoyo; add `schema.sql == yoyo head == init_db fresh` CI check.
**Priority:** P1
FACT: code + README contradiction observed. INFERENCE: source of historical PG cutover fixes (`ece57ac`, `f6aa30d`, `2ec1e26`).

### [P1] DB connection lifecycle is fragile

**Area:** Backend / Reliability
**Evidence:** `db.py:120-135 close(force=False)` is no-op; `close_db` uses `force=True` (correct but implicit); `db.py:211` on dead-conn fallback creates `PgConnectionWrapper(raw_conn, pool=None)` — never returned to pool (leak); `SimpleConnectionPool(1,20)` with no timeout/retry; `_is_conn_alive` does `SELECT 1` + `rollback` per checkout.
**What is happening:** Pool exhaustion under Neon idle-timeout/SSL drops; per-request ping adds latency.
**Impact:** Production 500s under connection churn; leaked non-pooled conns accumulate.
**Recommendation:** Always wrap pooled conn (even fresh) with pool ref + `putconn`; add `connect_timeout`, retry with backoff; move health-check to idle eviction, not hot path; add pool-exhaustion logging/metric.
**Priority:** P1
FACT: code paths cited. INFERENCE: correlates with `5ea0eae Fix database connection pool leak`.

### [P1] `app.run(debug=True)` in `__main__`

**Area:** Backend / Security / DevOps
**Evidence:** `app.py:5996-5997`.
**What is happening:** Debugger + reloader enabled if anyone starts prod via `python app.py`.
**Impact:** Werkzeug debugger allows code execution on error pages if exposed.
**Recommendation:** `app.run(debug=os.environ.get("FLASK_ENV")=="development")`; document `gunicorn` as only prod entry.
**Priority:** P1

### [P2] Auth is inline `require_login()` everywhere, not decorators

**Area:** Backend
**Evidence:** `app.py:697-698` + 60+ `if not require_login()` call sites; `utils/decorators.py:login_required/admin_required` unused by `app.py`.
**What is happening:** Easy to forget a check on new routes; inconsistent API (some return redirect where JSON expected — `decorators.py` handles `/api/` correctly but `app.py` often redirects).
**Impact:** Authorization omission risk; frontend must handle redirects on fetch.
**Recommendation:** Migrate `app.py` to `@login_required` incrementally; add test that enumerates routes and asserts protection.
**Priority:** P2

### [P2] Broad `except Exception` + `print` instead of logging

**Area:** Backend / Observability
**Evidence:** `app.py:329,825,989-1731` (~20 bare handlers), `log_activity:816-829` swallows all errors, `generate_run_insight` closes conn before use on error paths.
**What is happening:** Failures silent; no structured logs; `print` goes to stdout without levels.
**Impact:** Prod debugging blind; badge/streak/challenge failures hidden (`Badge eval warning` prints only).
**Recommendation:** Introduce `logging` with levels; keep user-facing fallback but log `exc_info`; add request-id.
**Priority:** P2

### [P2] `datetime.utcnow()` deprecated + naive datetimes

**Area:** Backend
**Evidence:** `app.py:989,1059,4792` + 34 pytest warnings.
**What is happening:** Naive UTC stored as TEXT; PG timestamps string-cast (`db.py:48-56`) to mimic SQLite.
**Impact:** Future Python removal; timezone bugs around midnight streak/weekly/monthly boundaries (history: `fix/date-boundaries`, `2ec1e26`).
**Recommendation:** Migrate to timezone-aware `datetime.now(timezone.utc)` + `TIMESTAMPTZ`; centralize `utils/dates.py` usage; add boundary tests.
**Priority:** P2

### [P2] N+1 and per-request queries

**Area:** Backend / Performance
**Evidence:** `check_pin_setup:780-782` (1 query every authed request) + `get_current_user:787-796` (another) + `get_personal_bests_for_user:705-743` (4 queries) + dashboard context building.
**What is happening:** 2+ queries before any route logic; no caching.
**Impact:** Latency + pool pressure; mobile TTFB regression.
**Recommendation:** Cache user in `g`, combine pin+user fetch, memoize PBs per request.
**Priority:** P2

---

## Frontend Findings

### [P1] `templates/index.html` 334 KB / 7394 lines monolith

**Area:** Frontend / Performance / Maintainability
**Evidence:** `Get-ChildItem templates/*.html` — `index.html` 334384 bytes vs next largest `admin.html` 43 KB, `settings.html` 42 KB.
**What is happening:** Dashboard, runs, analytics, badges, goals, pets, modals, and inline `<script>` all in one file.
**Impact:** Parse/compile cost on low-end mobile; single syntax error breaks all tabs (history: `5ea0eae JavaScript syntax error`, `switchTab`/`loadWeeklyGoal` regressions); PR diffs unreadable (`final_*_diff.txt` 375 KB).
**Recommendation:** Split by tab into includes + extracted JS modules; keep DOM contract stable (no UI redesign); add smoke test that asserts each tab container exists.
**Priority:** P1
FACT: size/line counts. INFERENCE: root cause of cascading tab failures.

### [P2] Heavy `innerHTML` templating with user data

**Area:** Frontend / Security / Reliability
**Evidence:** `grep innerHTML` hits across `index.html` (run cards, tbody, grids, badges, challenges); `{{ ...|tojson|safe }}` for `pb_run_ids`, `display_name`, `username`.
**What is happening:** Client builds HTML strings from API JSON; correctness depends on backend `bleach` sanitization (`sanitize_notes` allows zero tags — good).
**Impact:** If any field bypasses `sanitize_notes` (e.g. `display_name`, `bio`, `notes` via CSV/screenshot import), stored XSS executes; single render exception aborts whole list.
**Recommendation:** Keep `bleach` allowlist at zero tags; add server-side validation for `display_name`/`bio`; wrap each card render in try/catch + escape helper; add XSS test with `<img onerror>`.
**Priority:** P2
FACT: patterns observed + `validators.sanitize_notes` verified. INFERENCE: risk conditional on import paths.

### [P2] Tab/fetch initialization fragility (`switchTab`, `loadWeeklyGoal`, monthly, badges, pet)

**Area:** Frontend
**Evidence:** Git history `2df000c hide run cards on Home tab`, `97e41d5 pace_pet widget`, `752d95d Monthly Goal redesign`, `021... raw PG timestamps`; `static/js/goals.js` 28 KB vs inline dashboard JS.
**What is happening:** Multiple init paths (inline + `goals.js` + `profile.js`) race; missing null-guards cause silent tab death.
**Impact:** Regressions reappear when widgets added (see dashboard-layout test drift).
**Recommendation:** Single `initDashboard()` with ordered awaits + per-widget try/catch + loading/error/empty states; contract-test API shapes.
**Priority:** P2

### [P3] JS duplication (`goals.js` vs inline, `profile.js` vs modal)

**Area:** Frontend
**Evidence:** `static/js/goals.js` 28924 bytes duplicates monthly/weekly logic in `index.html`; `profile.js` 13335 bytes overlaps public-profile rendering.
**What is happening:** Two sources of truth for same endpoints (`/api/monthly-progress`, `/api/weekly-goal-progress`, `/api/user/<u>/public-profile`).
**Impact:** Drift (frontend expects field backend renamed).
**Recommendation:** Extract shared `api.js` + `render.js`; delete inline copies after trace.
**Priority:** P3

---

## Database & Migration Findings

### [P1] Four DDL sources disagree

**Area:** DB
**Evidence:** `schema.sql` (17 tables + 9 indexes, has `profile_emoji`, `monthly_goals`, `user_pets` + partial index, onboarding `experience/primary_goal/frequency`, `bio/next_race`) vs `migrations/001` (lacks `profile_emoji`, `monthly_goals`, onboarding extras) + `003_add_user_onboarding_fields.sql` (187 B) + `004_add_monthly_goals.sql` (349 B) + `005_add_profile_emoji.sql` (182 B) vs `app.py:init_db()` PG branch (minimal users/runs + ALTERs) vs SQLite branch (different types).
**What is happening:** No single source of truth; `schema.sql` is target PG schema, migrations are incremental, `init_db` is third path.
**Impact:** Fresh PG via `init_db` ≠ migrated PG ≠ `schema.sql`; production cutover (`ece57ac`) required manual fixes; future deploys risk missing columns.
**Recommendation:** Make `schema.sql` generated from `yoyo head` on empty DB; CI asserts `init_db fresh SQLite` tables ⊆ `schema.sql`; remove DDL from `app.py`.
**Priority:** P1

### [P2] PG/SQLite semantic gaps hidden, not solved

**Area:** DB
**Evidence:** `db.py:48-56` timestamp→string cast; `SERIAL` vs `INTEGER PRIMARY KEY AUTOINCREMENT`; `BOOLEAN` vs `INTEGER`; `BYTEA` avatar vs SQLite BLOB; `?`→`%s` naive replace (breaks `??`/`%` literals); `lastrowid` returns `None` on PG (`db.py:83-86`).
**What is happening:** App pretends dialects identical.
**Impact:** Date parsing, boolean, avatar, and `RETURNING id` bugs only appear in prod (history: `f6aa30d heatmap/streak type mismatch`, `04208ed raw PG timestamps`).
**Recommendation:** Document per-dialect notes; add PG-only CI job (or at least `pytest --pg` with `APPROVED_TEST_DB_URL`); fix `lastrowid` via `RETURNING id`.
**Priority:** P2

### [P2] Missing indexes / constraints review

**Area:** DB
**Evidence:** `schema.sql:190-198` indexes `runs(user_id,date)`, `runs(date)`, friends, badges, edit_history, goals, logs, pin_resets. No index on `runs(user_id, pace)`, `user_badges(badge_id)`, `activity_logs(timestamp)`, `runs(created_at)`; no CHECKs on `distance_km>0`, `time_min>0`, `pace` range; no `CHECK (follower_id != followed_id)` on friends.
**What is happening:** Leaderboard/social/PB queries scan; invalid data relies solely on app validation.
**Impact:** Slow leaderboards at scale; self-follow possible; negative distances possible via direct SQL/sync bypass.
**Recommendation:** Add indexes + CHECKs as yoyo migration with `NOT VALID` → `VALIDATE` to avoid prod lock; add self-follow guard.
**Priority:** P2

### [P2] Migration tooling correct but coverage thin

**Area:** DB
**Evidence:** `migrations/README.md` policy is sound (dedicated `MIGRATION_DATABASE_URL`, no auto-run, PR review); `002_seed_badges_challenges.sql` seeds; no `.rollback.sql`; `__pycache__` inside `migrations/`.
**What is happening:** Good policy, but `init_db` violates it; rollbacks untested.
**Impact:** Irreversible seed + partial-index migration risk.
**Recommendation:** Add rollback scripts for 004/005; remove `__pycache__`; CI `yoyo status` check.
**Priority:** P2

---

## Security Findings

### [P0] See `/testlogin` above. Additional P1 items:

### [P1] `app.run(debug=True)` + verbose error prints

**Area:** Security
**Evidence:** `app.py:5996-5997`, `print(traceback.format_exc())` in `/add:1731`, `print(conn._conn)` in `init_db:337`.
**Impact:** Stack traces + conn repr leak internals if debug exposed.
**Recommendation:** Remove prints; use logging with redaction; ensure Flask `DEBUG=False` in prod.
**Priority:** P1

### [P1] CSRF exemptions need re-verification

**Area:** Security
**Evidence:** `@csrf.exempt` on `/api/sync-run:1742` (comment: SW cannot carry token — legitimate, but then relies solely on session + hash/dup check), `/api/monthly-goals:2139`, `/api/trigger-weekly-emails:4603` (CRON_SECRET header — verify constant-time compare + rotation).
**What is happening:** Exemptions expand attack surface.
**Impact:** CSRF-triggered run/goal writes if `SameSite=Lax` bypassed via top-level POST quirks.
**Recommendation:** Keep sync exempt but add `Origin/Referer` check + idempotency hash verification (already partial); move monthly-goals under CSRF (fetch can send token); verify CRON uses `hmac.compare_digest`.
**Priority:** P1
FACT: exemptions listed. INFERENCE: need code read of CRON compare (flagged for follow-up, not assumed vulnerable).

### [P2] Session cookie `Secure=False` by default; `config.py` unused

**Area:** Security
**Evidence:** `config.py:22 SESSION_COOKIE_SECURE=False`, `ProductionConfig:78 Secure=True` but `app.py` never loads `config.py`; `app.secret_key` set directly.
**What is happening:** Prod may run with non-Secure cookies if started without explicit config.
**Impact:** Session theft over HTTP.
**Recommendation:** Load `ProductionConfig` when `FLASK_ENV=production`; set `SESSION_COOKIE_SECURE=True`, `HTTPONLY`, `SAMESITE=Lax` explicitly in `app.py`.
**Priority:** P2

### [P2] Upload/CSV/screenshot paths

**Area:** Security
**Evidence:** `/api/parse-import:2834`, `/api/confirm-import:2876` (transaction rollback claimed), `/api/parse-screenshot:2987` (Google GenAI + Pillow), `/api/profile/avatar:5402` (BYTEA).
**What is happening:** CSV parsing, image OCR, avatar bytes — all attacker-controlled.
**Impact:** CSV formula injection on export, image decompression bomb, oversized avatar DoS.
**Recommendation:** Enforce size limits (e.g. 5 MB CSV, 10 MB image), Pillow `MAX_IMAGE_PIXELS`, avatar resize + MIME sniff, CSV export prefix `'` for `=+-@`.
**Priority:** P2 (INFERENCE — limits not observed; verify before claiming exploitable).

### [P3] Secrets hygiene — no live secrets found, history clean for `.env`

**Area:** Security
**Evidence:** `git log --all -p -- .env` empty; `.gitignore` covers `.env`, `*.db`, `*.log`; `.env.example` contains placeholders only; `grep SECRET_KEY|DATABASE_URL` shows env reads, no hardcoded prod URLs. `.env` exists locally (untracked, ignored) — content not read per policy.
**Recommendation:** Add `gitleaks`/`trufflehog` to CI; document rotation for `CRON_SECRET`/`RESEND_API_KEY`/`GEMINI_API_KEY`.
**Priority:** P3
FACT: no secret values printed here (redacted by policy).

---

## Performance Findings

FACT: `db.py` pool 1–20 + health ping; `sw.js` cache-first static, network-first pages, network-only API; run-card progressive rendering + `Load More` claimed in history (`c7a7537`, `305c42a`).

- **What is optimized:** Static precache (`PRECACHE_ASSETS` 11 entries), CDN cache-first, paged run lists, `idx_runs_user_date`.
- **What is not:** `index.html` parse cost (334 KB), per-request user/pin queries, 4-query PBs, `SELECT *` everywhere, no pagination on leaderboard/social server-side (verify), `backdrop-filter`/blur + animations unbudgeted, no image optimization pipeline for avatars.
- **Regressions:** `before_request` DB hit added latency; timestamp string-cast forces JS date parsing.
- **Bottlenecks (INFERENCE, need real-device trace):** TTFB (pool ping + user queries), INP (monolith JS), LCP (heatmap Leaflet + Chart.js competing).

**Recommendation:** Budget: TTFB <600 ms 4G, INP <200 ms, JS <200 KB gz per route. Split `index.html`, add `loading=lazy` avatars, cap `activity_logs` writes (sample), add `/healthz` timing.

---

## UI/UX Findings

Static inspection (no prod visual run per REVIEW-ONLY; responsive classes + Bootstrap 5.3.2 + bottom nav + drawer observed):

- Hierarchy generally consistent (dark neon glassmorphism); onboarding collects height/weight/city (good for calories/weather).
- Issues (P2/P3): duplicate info (PBs in dashboard + profile + public profile drift — `21f2ff4` fixed preview metrics but triple source remains); empty/error states inconsistent (`Failed to load...` vs spinner forever on fetch throw); modal z-index history (`3532db9`) suggests stacking fragility; date display previously raw PG timestamps (`04208ed`) — fixed but indicates formatting centralized too late; accessibility: icon-only buttons lack `aria-label` (spot-check `index.html` theme toggle uses emoji text); contrast of neon on dark unverified without axe run.
- No redesign recommended. Add axe + 390 px screenshot CI (`scripts/screenshot_*.py` exist but not wired to CI).

---

## Testing & Quality Findings

FACT: `python -m pytest tests/ -q` → **2 failed, 195 passed, 34 warnings in 10.53 s**.

- Failures: `test_get_default_dashboard_layout` (expected 6, got 7 — `pace_pet` added, `97e41d5`) and `test_post_dashboard_layout` (expected 3, got 4 — auto-appended `personal_goal`+`pace_pet`). Evidence: `tests/test_dashboard_layout.py:43,64`. Cross-system drift, not product bug.
- Coverage: auth, goals, pets, challenges, badges, leaderboard qualification, public profile, screenshot import, ML predictor, validators, dates, rate limiter, google auth, db guardrail, smoke guardrail. Gaps: admin authz (`/admin/user/<id>/<action>`), follow/unfollow IDOR, CSV import rollback, sync-run hash/dup, migration ordering, PG-only types, frontend JS (zero JS tests), avatar upload, CRON auth, rate-limit on PIN recovery.
- Fragility: `conftest.py` uses shared-memory SQLite per test with keepalive conn (correct) but `test_dashboard_layout.py` defines its own `client` fixture bypassing `conftest` isolation + manually hacks session (no login flow). `sample_user` fixture includes `email_weekly_summary` column that may not exist in fresh schema (latent).
- Safety: `conftest.py` forces `DATABASE_URL=sqlite:///...` + `TESTING=1` + `APPROVED_TEST_DB_URL` guard in `db.py:192-198` blocks prod writes. Good.
- Root `test_*.py` + `pytest_full.log` are **not** run by CI (`python-app.yml` runs `pytest tests/ -v` only).

---

## Deployment / DevOps Findings

### [P1] Minimal `gunicorn.conf.py` + no health check

**Area:** DevOps
**Evidence:** `gunicorn.conf.py` 4 lines (bind only); no `workers`, `timeout`, `accesslog`, `preload`; no `/healthz` route (grep: none); `Procfile`/`render.yaml`/`runtime.txt` absent (Render likely uses dashboard settings).
**Impact:** Default sync worker (1) under-serves mobile burst; no Render health check → failed deploys stay live; ephemeral SQLite warning (`db.py` prints EPHEMERAL) correct but easy to miss.
**Recommendation:** Set `workers=2*CPU+1`, `timeout=30`, `accesslog=-`, `preload_app=True` (with pool `post_fork` re-init); add `/healthz` (DB ping, no auth); pin Python version (`.python-version` exists, `runtime.txt` missing).
**Priority:** P1

### [P2] Env/config drift

**Area:** DevOps
**Evidence:** `.env.example` lists `FLASK_ENV, SECRET_KEY, DATABASE_URL, REDIS_URL, ADMIN_USER_ID, WEATHER_API_KEY, RESEND_*, GEMINI_API_KEY, CRON_SECRET, SUPPORT_EMAIL` but `app.py` reads only subset; `REDIS_URL` unused (`extensions.py:18 memory://` hardcoded); `config.py` unused.
**Impact:** Rate limiting never distributed (memory store per gunicorn worker); email/weather silently disabled if keys missing.
**Recommendation:** Wire `REDIS_URL` to limiter; fail-fast check for required prod env at boot (without printing values).
**Priority:** P2

---

## Git & Repository Hygiene

FACT: `git log --oneline -30` shows fix-heavy history (`Fix mojibake`, `Fix z-index`, `Fix PG type mismatch`, `Fix pool leak`); `git status` clean; `git branch -a` lists **~40 branches** (most `feat/*`, `fix/*`, `feature/*` stale, e.g. `feat/dashboard-redesign`, `redesign-runs-page`, `virtual-pace-pet`); `git ls-files` shows no tracked `*.db`/`*.log` (correctly ignored) but large tracked HTML diffs (`final_*_diff.txt` 375 KB, `index_*.html` 320-340 KB) and `docs/RunRush_Project_Report.html` 39 KB; `migrations/__pycache__/` tracked (should be ignored).

- Temporary commits (`a72c8c4 Changes`, `226b2be Changes`) — unclear history.
- Direct-`main` pattern evident (many `Changes` on main, no squash).
- No secrets in `.env` history (file never tracked). Full-history secret scan beyond `.env` not run (tool limit noted) — recommend `gitleaks` full scan.

---

## Cross-System Consistency

| Backend expects | Frontend expects | Status |
|---|---|---|
| Dashboard layout 7 widgets incl `pace_pet` (`app.py:5704+`) | Tests expect 6 (`test_dashboard_layout.py:43`) | **FAIL** — 2 tests red |
| `user_badges(user_id,badge_id)` FK (`schema.sql:103-110`) | `badge_service.BADGE_METADATA` dict by `badge_key` | Drift — legacy `badges` table vs dict; `get_badges_status_for_user` bridges but seed sync untested |
| PG `TIMESTAMP` string-cast (`db.py:50-56`) | JS `new Date(str)` | Fragile — raw PG strings previously rendered (`04208ed`) |
| `/api/v1/*` documented | No `register_blueprint`, SW skips `/api/` only | Dead — frontend never calls `/api/v1` |
| `monthly_goals(user_id,year,month)` unique (`schema.sql:77`) | `goals.js` monthly-progress | OK if API validates dup; verify 409 vs silent overwrite |
| `friends(follower,followed)` unique, no self-check | Follow button | Missing self-follow guard (DB + API) |
| `runs.date TEXT` in `init_db` PG branch vs `TIMESTAMP` in `schema.sql` | Heatmap/streak date parsing | **Drift** — source of PG date bugs |
| Docs claim offline sync with hash/dup | `/api/sync-run` exempt + hash check | Partially verified — needs authz test |

---

## Technical Debt

1. 6000-line `app.py` god-file.
2. Dead `blueprints/` + unused `config.py` + unused decorators.
3. Four DDL sources.
4. 334 KB `index.html` monolith + inline JS duplication.
5. String-cast timestamps hiding dialect differences.
6. `print` observability + bare excepts.
7. Unpinned ML/AI deps (`google-genai`, `Pillow`, `scikit-learn`, `pandas`, `numpy`).
8. 40 stale branches + vague `Changes` commits + tracked diff dumps.
9. Root debug scripts + zero-byte DBs + screenshots in repo.
10. No JS tests, no PG CI, no visual CI.

---

## Risk Register

| ID | Risk | Likelihood | Impact | Priority |
|---|---|---|---|---|
| R1 | `/testlogin` account takeover | High if deployed | Critical | P0 |
| R2 | Startup auto-DDL causes prod drift/lock | Med | High (data loss/downtime) | P1 |
| R3 | Pool leak/exhaustion under Neon idle timeout | Med | High (500s) | P1 |
| R4 | Monolith JS single failure breaks dashboard | High | Med | P1 |
| R5 | PG-only type/date bug reappears | High | Med | P1 |
| R6 | CSRF-exempt write abuse | Low-Med | Med | P1 |
| R7 | Leaderboard/social N+1 + missing index slowness | Med | Med | P2 |
| R8 | Unpinned dep breaks build (numpy/sklearn/genai) | Med | Med | P2 |
| R9 | Single gunicorn worker + no health check failed deploy | Med | Med | P1 |
| R10 | Test drift masks real regression (layout) | High | Low-Med | P2 |

---

## Recommended Roadmap

### Quick Wins (days, no UI redesign, no schema change)

- [ ] Delete `/testlogin` or env-guard + test that route 404s in prod.
- [ ] Fix `test_dashboard_layout.py` expectations (7 default, auto-append behavior) — makes CI green.
- [ ] Remove `print(DEBUG conn)` + `traceback` prints; add `logging`.
- [ ] Replace `utcnow()` with `now(timezone.utc)` (codemod + boundary test).
- [ ] Add `.gitignore` for `migrations/__pycache__/`, `*.html` dumps, `qa_screenshots/`; untrack `final_*_diff.txt`, `index_*.html`, zero-byte DBs (keep local only).
- [ ] Pin `google-genai`, `Pillow`, `scikit-learn`, `pandas`, `numpy` in `requirements.txt` (hash-check via `pip freeze`).
- [ ] Document `CRON_SECRET` rotation + verify `compare_digest`.
- [ ] Add `/healthz` + gunicorn workers/timeout/log.

### Medium-Term Improvements (weeks)

- [ ] Freeze `init_db()` to bootstrap; reconcile `schema.sql` == yoyo head; CI schema-equality check.
- [ ] Register or remove `blueprints/`; migrate to `@login_required`.
- [ ] Split `index.html` into includes; extract `api.js`; per-widget error boundaries.
- [ ] Fix `db.py` pool leak (always pool-wrap), add timeout/retry, cache user in `g`.
- [ ] Add PG CI job + JS smoke (Playwright 390 px + desktop console-error check) + `gitleaks`.
- [ ] Add missing indexes/CHECKs via yoyo with `NOT VALID` pattern.
- [ ] Wire `REDIS_URL` to limiter; load `ProductionConfig` in prod.

### Long-Term Architecture Improvements

- [ ] Slice `app.py` by domain (runs, auth, social, goals, analytics, admin) behind registered blueprints; service-layer transactions with explicit commit/rollback.
- [ ] Replace string-cast timestamps with real `TIMESTAMPTZ` + central date utils.
- [ ] Replace `SELECT *` with projections; cursor pagination for runs/leaderboard/social.
- [ ] Avatar pipeline (resize, WebP, object storage vs BYTEA).
- [ ] Real observability (structured logs, metrics, Sentry), rate-limit sharing, background jobs outside request (email/ML).

---

## What's Already Good

- Startup SECRET_KEY guard + `APPROVED_TEST_DB_URL` prod-test guardrail.
- `bleach` zero-tag sanitization + centralized validators (distance/time/date/pace/username/email).
- Pool health-check intent + per-request teardown + SQLite/PG shim enabling local dev.
- PWA policy correct (cache-first static, network-first pages, network-only API, offline fallback, background-sync hook).
- Yoyo policy docs forbid auto-migration (needs enforcement in code).
- Test isolation via per-test in-memory SQLite + fast bcrypt + limiter disabled.
- Indexes on hot paths (`runs(user_id,date)`), FK cascades correct (`runs` cascade, `user_badges` restrict).
- CI runs `tests/` on push/PR with env isolation.

---

## What Must Be Fixed Before Major Expansion

1. Remove/guard `/testlogin` (P0).
2. Stop startup auto-DDL; single source of truth for schema (P1).
3. Fix pool leak + add `/healthz` + production gunicorn config (P1).
4. Green CI (fix layout tests) + PG CI + secret scan (P1).
5. Split `index.html` or at minimum add per-tab error boundaries + JS smoke at 390 px/desktop (P1).
6. Pin heavy deps + wire Redis/limiter + prod cookie flags (P2).

Without these, adding training plans, Strava/Garmin OAuth, or team challenges will multiply drift, auth, and mobile-perf risk.

---

## Final Engineering Assessment

FACT: RunRush ships a working offline-first running platform with thoughtful product breadth (import paths, AI screenshot, ML prediction, pets, badges, social) and evidence of iterative production hardening (PG cutover, pool leak fix, date fixes, z-index/modal fixes).

INFERENCE: It is at the classic monolith inflection point — velocity created duplication (blueprints, config, DDL, JS) and a fragile big-template frontend. The codebase does not need a rewrite; it needs enforcement of its own documented policies (no auto-migration, env-based config, yoyo as truth) plus deletion of debug/duplicate paths and decomposition of `app.py`/`index.html` behind stable contracts.

Risk-based verdict: **hold on major features until P0/P1 above are closed; then expand incrementally behind contract tests (API shapes, layout widgets, migration head, 390 px smoke).**

---

## Appendix — Verification

- Audit file: `docs/RUNRUSH_CODEBASE_AUDIT.md` (this file) — created; no app files modified.
- `git status --short` before: clean; after tests + doc creation: only untracked `docs/RUNRUSH_CODEBASE_AUDIT.md` (app tree untouched).
- Tests: `python -m pytest tests/ -q` → **195 passed, 2 failed** (`test_dashboard_layout` x2, expectation drift). 34 warnings (mostly `utcnow` deprecation + genai types).
- Secrets: none printed; `.env` content never read; history check for `.env` tracking empty; full-repo secret scan recommended via `gitleaks`.
- Visual QA: static (templates + `sw.js` + `goals.js`/`profile.js` + responsive/Bootstrap/bottom-nav inspection). Live 390 px browser run not executed (REVIEW-ONLY, no prod server started); recommend wiring existing `scripts/screenshot_*.py` to Playwright CI for 390 px + desktop console-error gates.
