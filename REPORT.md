# RunRush Security Headers & CI Security Scans Report

**Date:** 2026-11-10  
**Branch:** `chore/security-headers-ci` (unmerged, local working copy)  
**Status:** Complete — All tests passing (623/623), Bandit passing against baseline, CI workflows and Dependabot configured.

---

## 1. Executive Summary

This task implemented defense-in-depth HTTP security headers and automated CI security scanning for the RunRush Flask application:
1. **Reverse Proxy & Header Management:** Configured Werkzeug's `ProxyFix` (`x_for=1, x_proto=1, x_host=1`) before header enforcement to properly trust Render's reverse proxy and avoid redirect loops.
2. **Security Headers (`flask-talisman==1.1.0`):** Added HSTS, MIME sniffing protection, frame protection (`DENY`), referrer policy, strict permissions policy for GPS/audio, and hardened session cookie flags (`Secure`, `HttpOnly`, `SameSite=Lax`).
3. **Content Security Policy (Report-Only):** Performed an exhaustive scan of all external origins and inline scripts/styles/handlers. Deployed a strict CSP in **Report-Only** mode (`Content-Security-Policy-Report-Only`) without `'unsafe-inline'` or `'unsafe-eval'` in `script-src`.
4. **CSP Reporting Endpoint (`/csp-report`):** Implemented a rate-limited, size-limited (10 KB max), CSRF-exempt endpoint that logs anonymized violation reports without leaking personal data.
5. **CI Security Workflows (GitHub Actions):** Created `.github/workflows/security.yml` with least-privilege permissions (`contents: read`) and pinned commit SHAs for **Bandit** SAST, **pip-audit** dependency checks, and **Gitleaks** secret scanning across the full git history. Added `.github/dependabot.yml` for automated weekly dependency updates.

---

## 2. Security Headers Implemented

| Header | Value | Purpose |
|---|---|---|
| **`Strict-Transport-Security`** | `max-age=31536000; includeSubDomains` | Enforces HTTPS for 1 year across all subdomains. `preload` intentionally omitted until production stability is established. |
| **`X-Content-Type-Options`** | `nosniff` | Prevents MIME-type confusion / content sniffing attacks. |
| **`Referrer-Policy`** | `strict-origin-when-cross-origin` | Sends full referrer to same origin; sends only origin over HTTPS to third parties; sends no referrer over HTTP. |
| **`X-Frame-Options`** | `DENY` | Prevents framing in all contexts (clickjacking protection). Paired with CSP `frame-ancestors 'none'`. |
| **`Permissions-Policy`** | `geolocation=(self), microphone=(self), camera=(), payment=(), usb=()` | Explicitly permits geolocation (GPS run tracking) and microphone (voice logging) for same-origin only; disables camera, payment, and USB APIs. |
| **`Session Cookies`** | `Secure; HttpOnly; SameSite=Lax; Path=/` | Prevents JavaScript cookie access (`HttpOnly`), prevents cross-site request leakage (`SameSite=Lax`), and ensures transmission only over HTTPS (`Secure`). |
| **`Content-Security-Policy-Report-Only`** | Directives detailed below | Evaluates resource and script safety without breaking application functionality; logs violations to `/csp-report`. |

---

## 3. Content Security Policy (Report-Only)

### 3.1 Policy Configuration

```text
default-src 'self';
script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com;
style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net data:;
img-src 'self' data: blob: https:;
connect-src 'self' https: wss: ws:;
worker-src 'self';
manifest-src 'self';
object-src 'none';
base-uri 'self';
form-action 'self';
frame-ancestors 'none';
report-uri /csp-report
```

> **Note on Script Execution:** Neither `'unsafe-inline'` nor `'unsafe-eval'` is added to `script-src`. Because the policy is deployed as `Content-Security-Policy-Report-Only`, inline scripts and event handlers continue executing while generating violation reports to guide the refactoring roadmap.

### 3.2 External Origin Inventory

The following external origins were discovered and whitelisted in CSP directives:
- **`https://cdn.jsdelivr.net`** (Bootstrap 5.3.2 bundle, Bootstrap CSS, Chart.js)
- **`https://cdnjs.cloudflare.com`** (Font Awesome 6.4/6.5 CSS/webfonts, Cropper.js 1.6.1, html2canvas 1.4.1)
- **`https://unpkg.com`** (Leaflet 1.9.4 JS and CSS)
- **`https://fonts.googleapis.com`** (Google Fonts stylesheet links)
- **`https://fonts.gstatic.com`** (Google Fonts woff2 font files)
- **`https://*.tile.openstreetmap.org` / `https:`** (Leaflet GPS map tiles)

### 3.3 Inline Script, Style & Event Handler Inventory

An automated scan of `templates/` and `static/` cataloged the following inline blocks:

#### A. Inline `<script>` Tags (48 occurrences)
| File | Line | Snippet / Purpose |
|---|---|---|
| `templates/admin.html` | 720, 779 | Chart.js initialization & admin management scripts |
| `templates/admin_notifications.html` | 235 | Notification broadcast UI handlers |
| `templates/dev_design_system.html` | 221 | Design system preview toggle scripts |
| `templates/edit.html` | 406 | Edit run form validation & calculation scripts |
| `templates/forgot_pin_reset.html` | 108 | PIN strength & matching validation |
| `templates/forgot_pin_verify.html` | 82 | Verification code input auto-advance |
| `templates/index.html` | 2096, 2304, 2771, 3372, 3820, 4845, 5140, 5319, 5361, 5479, 5626, 5851, 6283, 6287, 6388, 6549, 6639, 6658, 6875, 8549, 9407, 9488, 9638, 9955, 9987, 10087 | Main application logic: live GPS tracking, audio logging, modal controls, feeds, charts |
| `templates/index.html` (JSON data) | 4818, 4821, 8125 | `<script id="..." type="application/json">` (safe JSON data containers) |
| `templates/landing.html` | 22 | Hero animation & redirect handlers |
| `templates/login.html` | 190 | PIN input pad & form submit |
| `templates/offline.html` | 269 | Offline caching retry & network listener |
| `templates/onboarding.html` | 558 | Multi-step onboarding carousel navigation |
| `templates/public_profile.html` | 124 | Public runner profile stats tab toggle |
| `templates/register.html` | 187 | Registration form PIN verification |
| `templates/settings.html` | 575, 929, 1121 | Tab navigation, GPS history deletion, theme toggle |
| `templates/partials/_coming_soon_modal.html` | 179 | Modal dismissal |
| `templates/partials/_quick_actions_fab.html` | 325 | Floating Action Button open/close toggle |
| `templates/partials/_theme_init.html` | 20 | Anti-flash theme initialization script in `<head>` |

#### B. Inline `<style>` Blocks (34 occurrences)
- `templates/403.html:19`
- `templates/admin.html:29, 708`
- `templates/admin_notifications.html:13`
- `templates/dev_design_system.html:14`
- `templates/edit.html:24`
- `templates/forgot_pin.html:15`
- `templates/forgot_pin_methods.html:15`
- `templates/forgot_pin_reset.html:15`
- `templates/forgot_pin_verify.html:15`
- `templates/index.html:36, 1729, 1735, 1740, 1745, 1750, 1755, 1760, 2039, 2186, 2582, 3352, 3960, 4880, 5683, 6231, 8089`
- `templates/landing.html:14`
- `templates/login.html:34`
- `templates/offline.html:18`
- `templates/onboarding.html:23`
- `templates/public_profile.html:28`
- `templates/register.html:34`
- `templates/set_pin.html:20`
- `templates/settings.html:27`

#### C. Inline Event Handlers (`on*=` - 206 occurrences)
- `onclick`: modal triggers, emoji selection, run filters, navigation, logout, tabs.
- `onchange`: image file upload, measurement unit toggle (metric/imperial).
- `oninput`: PIN pad digit entry, real-time pace/duration validation.
- `onsubmit`: form submission guards.
- `onerror`: fallback default images for broken avatars.

### 3.4 Roadmap to Enforced CSP

To transition from `Content-Security-Policy-Report-Only` to an enforced `Content-Security-Policy`:
1. **Nonce Integration for Script Blocks:**
   - Flask-Talisman provides `csp_nonce()` in Jinja2 templates via `content_security_policy_nonce_in=['script-src', 'style-src']`.
   - Update inline `<script>` tags to `<script nonce="{{ csp_nonce() }}">`.
2. **Externalize JavaScript:**
   - Extract page-specific inline `<script>` tags into dedicated modules under `static/js/` (e.g., `static/js/pages/admin.js`, `static/js/pages/settings.js`).
3. **Eliminate Inline Event Handlers (`onclick=...`):**
   - Refactor inline event attributes to standard DOM event listeners (`addEventListener`) in external scripts.
4. **Enforce Policy:**
   - Set `content_security_policy_report_only=False` in `RunRushTalisman`.

---

## 4. CSP Report Endpoint (`/csp-report`)

An endpoint was added to receive violation reports dispatched by user agents:
- **Route:** `POST /csp-report`
- **CSRF Protection:** `@csrf.exempt` (browser-initiated report POSTs cannot send CSRF tokens).
- **Rate Limiting:** `@limiter.limit("60/minute")` via Flask-Limiter to prevent flood/DoS.
- **Payload Size Enforcement:** Rejects bodies larger than 10 KB with `HTTP 413 Payload Too Large`.
- **Privacy & Logging:** Query parameters and user IDs are stripped from reported URLs before logging. Only directive name, truncated blocked URI (max 200 chars), and sanitized document URI (max 200 chars) are recorded in application logs.

---

## 5. CI Security Workflows & Dependabot

### 5.1 `.github/workflows/security.yml`
Runs automatically on:
- `push` to `main`
- `pull_request` to `main`
- Weekly schedule every Monday at 04:00 UTC (`cron: '0 4 * * 1'`)

Security properties:
- **Least Privilege:** Top-level `permissions: contents: read`.
- **Pinned Actions:** Pinned to immutable commit SHAs with semantic version comments:
  - `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683` (# v4.2.2)
  - `actions/setup-python@42375524e23c412d93fb67b49958b491fbc71c33` (# v5.5.0)
  - `gitleaks/gitleaks-action@ff98106e84b2c5df1deeec5b383e8a42a6e8d8a6` (# v2.3.9)

Job breakdown:
1. **`bandit`:** Scans Python source code. Reports `MEDIUM` severity findings in job output, and enforces `HIGH` severity checks against `bandit-baseline.json`.
2. **`pip-audit`:** Scans `requirements.txt` for known CVEs. Fails the build on known vulnerabilities while applying `.pip-audit-allowlist.txt` for documented, context-specific false positives.
3. **`gitleaks`:** Performs git secret scanning across the full commit history (`fetch-depth: 0`).

### 5.2 `.github/dependabot.yml`
Configured to track:
- `pip` ecosystem: weekly scans, root directory (`/`).
- `github-actions` ecosystem: weekly scans, root directory (`/`).

---

## 6. Scan Findings & Documented Baselines

Per task instructions, existing findings were neither hidden nor patched prematurely. Confirmed context-specific false positives were documented in baseline/allowlist files, and all real findings are cataloged below.

### 6.1 Bandit SAST Findings

- **Total Lines Scanned:** 15,618
- **High Severity Findings:** 1
  - `B201:flask_debug_true` at `app.py:9492` (`app.run(debug=True, host="0.0.0.0", port=5000)`).
  - **Baseline Rationale:** Confirmed false positive for production. In deployment on Render, RunRush is executed as a WSGI module via Gunicorn (`gunicorn wsgi:app`), which never executes `__main__`. Line 9492 is strictly for local dev. Documented in `bandit-baseline.json`.
- **Medium Severity Findings (29 occurrences):**
  - `B608:hardcoded_sql_expressions` (24 occurrences): Query construction in analytics, filtering, and monthly summaries (e.g. `services/social_service.py`, `services/monthly_summary_service.py`). These use parameterized inputs (`?`) for values and construct structural clauses from controlled constants.
  - `B310:urllib_urlopen` (5 occurrences): `urlopen` calls in `weather_service.py`, `pin_recovery_service.py`, and `app.py`. Scheme validation should be added in a future task.

### 6.2 Pip-Audit Findings (Real Dependency Vulnerabilities)

The following real CVEs exist in the pinned production packages in `requirements.txt`:

| Package | Pinned Version | Vulnerability IDs | Summary & Context | Recommended Upgrade |
|---|---|---|---|---|
| **`Authlib`** | `1.3.0` | `GHSA-5357-c2jx-v7qh`, `GHSA-6v38-4h7w-rj9h`, `GHSA-7432-952r-cw78`, `GHSA-8m4g-j4wp-wgcg` | Algorithm confusion and signature validation bypass in JWS/JWE. Used in RunRush only for Google OAuth2 authorization code flow. | Bump to `>=1.4.0` |
| **`gunicorn`** | `21.2.0` | `GHSA-hc5x-x2vx-497g`, `GHSA-w3h3-4rj7-4ph4` | HTTP request smuggling when fronted by unconventional reverse proxies. | Bump to `>=22.0.0` |
| **`requests`** | `2.31.0` | `GHSA-9hjg-9r4m-mvj7`, `GHSA-9wx4-h78v-vm56`, `GHSA-gc5v-m9x4-r6x2` | `.netrc` credential leak on cross-origin redirects; session certificate verification reuse. | Bump to `>=2.32.3` |
| **`bleach`** | `6.1.0` | `GHSA-8rfp-98v4-mmr6`, `GHSA-gj48-438w-jh9v` | URI sanitization bypass with high Unicode codepoints and formaction attributes. | Bump to `>=6.2.0` |

#### Documented False Positives (`.pip-audit-allowlist.txt`):
- `GHSA-g6x2-hccm-hh4m` / `PYSEC-2026-4312` (`Werkzeug 3.1.8`): Windows special device name bypass in `safe_join()`. RunRush runs exclusively in a Linux container on Render where Windows special devices (`CON`, `PRN`) do not exist.
- `GHSA-mf9w-mj56-hr94` / `PYSEC-2026-2270` (`python-dotenv 1.0.1`): Symlink following in `set_key()`. RunRush uses `python-dotenv` exclusively for read-only `load_dotenv()` on startup; `set_key()` is never called.

---

## 7. Verification & Test Results

### 7.1 New Security Test Suite (`tests/test_security_headers.py`)
10 tests created and passing:
- `test_security_headers_present_on_normal_response`: Verifies `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, and `Permissions-Policy`.
- `test_hsts_header_present_on_secure_request`: Verifies HSTS max-age and subdomains on HTTPS, confirms no preload.
- `test_csp_is_report_only_and_configured`: Verifies CSP header is Report-Only, no `unsafe-inline` or `unsafe-eval` in `script-src`, verifies external CDNs and `report-uri`.
- `test_session_cookies_have_correct_flags`: Verifies `Secure`, `HttpOnly`, `SameSite=Lax` on session cookies.
- `test_http_to_https_redirect_and_no_loop_with_proxy_fix`: Simulates Render proxy with `X-Forwarded-Proto` (`http` -> 302 redirect to HTTPS; `https` -> 200 without loop).
- `test_csp_report_accepts_valid_payload`: Verifies `/csp-report` accepts JSON reports and logs without error.
- `test_csp_report_rejects_oversized_payload`: Verifies `/csp-report` returns HTTP 413 for payloads > 10 KB.
- `test_csp_report_is_csrf_exempt`: Verifies `/csp-report` functions without CSRF token.
- `test_sw_served_with_correct_headers`: Verifies Service Worker header integrity (`Service-Worker-Allowed: /`).
- `test_offline_page_accessible`: Verifies `/offline` is accessible.

### 7.2 Full Project Test Suite
```text
623 passed, 9 warnings in 16.70s
```

### 7.3 Tool Checks
- **Bandit:** Clean run (`0 issues identified` against `bandit-baseline.json`).
- **Ruff:** 0 errors on new security test and workflow files.

---

## 8. New Dependencies Added

Pinned in `requirements.txt`:
```text
flask-talisman==1.1.0
```

---

## 9. Open Questions & Recommendations

1. **Dependency Upgrade Window:** When would you like to schedule bumping the 4 vulnerable dependencies (`Authlib` -> `1.4.0+`, `gunicorn` -> `22.0.0+`, `requests` -> `2.32.3+`, `bleach` -> `6.2.0+`)? These require running full integration tests to ensure no breaking changes in OAuth or HTML sanitization.
2. **CSP Enforcement Timeline:** We recommend running in `Content-Security-Policy-Report-Only` for 1–2 weeks to monitor `/csp-report` logs in production before initiating the inline-script refactoring plan.
3. **HSTS Preload:** Once production HTTPS is verified across all domains with zero regressions, HSTS can be updated to include `preload` and submitted to the Chrome HSTS preload list (`hstspreload.org`).
