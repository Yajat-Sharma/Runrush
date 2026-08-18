# Step 4: Security Investigation Summary

## Current Security Posture
*   `extensions.py` has initialized `CSRFProtect`, `Limiter` (with default memory limits of 200 per day, 50 per hour), and a custom `BcryptWrapper` mimicking the Flask-Bcrypt API.
*   `tests/conftest.py` has been adjusted to handle the new bcrypt initialization and all tests are passing.
*   A backup of the database (`runs.db.backup`) exists and is available for safe, isolated PIN migration testing.

## Route Classification (CSRF Handling)
A full review of the POST routes in `app.py` has been conducted to determine the appropriate CSRF strategy for each:

### 1. Standard POST Routes
These are browser-submitted forms that require standard `Flask-WTF` CSRF protection.
*   `/register`
*   `/login`
*   `/onboarding`
*   `/profile`
*   `/settings/update`
*   `/settings/email`
*   `/settings/change-pin`
*   `/settings/clear-data`
*   `/delete-account`
*   `/add`
*   `/edit`
*   `/delete`
*   `/weekly-goal`
*   `/follow`
*   `/unfollow`
*   Admin actions (various)

**Action:** Standard template forms will be updated to include `{{ csrf_token() }}`. 

### 2. Online API Routes
These routes are triggered via AJAX `fetch()` calls from inline JavaScript in `templates/index.html`. They are NOT invoked by the offline service worker or background sync queue.
*   `/api/parse-import`
*   `/api/confirm-import`

**Action:** These routes will remain protected by CSRF, but the frontend JS `fetch()` calls will be updated to include the CSRF token in a header (e.g., `X-CSRFToken`).

### 3. Offline API Routes
This route is invoked by the background sync service worker (`sw.js` and `sync-engine.js`).
*   `/api/sync-run`

**Action:** Because the service worker runs in the background while offline and will be unable to fetch or refresh CSRF tokens seamlessly, this route will be marked with `@csrf.exempt`. The route currently enforces basic data integrity through a `hash` field (SHA256), which provides sufficient tamper protection in lieu of CSRF for this specific use case.

### 4. Automated/Cron Routes
This route is meant to be hit by a scheduled background job, not a browser session.
*   `/api/trigger-weekly-emails`

**Action:** The current implementation relies on a user session check (`require_login()` and an admin role check). This is inappropriate for a cron job. This route will be marked with `@csrf.exempt`. Its session-based authentication will be removed and replaced with a `CRON_SECRET` check via an HTTP header (e.g. `Authorization: Bearer <secret>`) or query parameter to authenticate the cron worker.
