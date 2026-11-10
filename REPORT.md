# RunRush Security Headers & Dependency Upgrades Report

**Date:** 2026-11-10  
**Current Branch:** `chore/dependency-upgrades` (branched from `chore/security-headers-ci`; unmerged, local working copy)  
**Status:** Complete — All 623 tests passing, Bandit 0 High severity, pip-audit 0 CVEs on upgraded packages without allowlist additions.

---

## 1. Executive Summary

This task resolved all vulnerable production dependencies reported by `pip-audit` and removed the last High-severity Bandit SAST finding:
1. **Dependency Upgrades:** Upgraded `Authlib`, `gunicorn`, `requests`, and `bleach` to the lowest secure versions that remediate all reported CVEs/GHSAs, staying within the same major versions where possible.
2. **SAST & Lint Hardening:** Switched the local execution `debug=True` in [`app.py`](file:///d:/Programming%20codes/Running-py/app.py#L9490) to an environment-controlled variable (`FLASK_DEBUG`, defaulting to off). Removed the `B201:flask_debug_true` baseline exception from [`bandit-baseline.json`](file:///d:/Programming%20codes/Running-py/bandit-baseline.json), bringing High severity findings to **zero**.
3. **pip-audit Clean Audit:** `pip-audit` passes cleanly on all four packages without adding any of them to [`.pip-audit-allowlist.txt`](file:///d:/Programming%20codes/Running-py/.pip-audit-allowlist.txt).
4. **Targeted Subsystem Verification:** Verified Google OAuth authorization flows, notes/bio HTML sanitization via `bleach.clean()`, outbound request timeout/SSL integrity, and Gunicorn configuration compatibility.

---

## 2. Dependency CVE Remediation Details

### 2.1 Summary Table

| Package | Previous Version | CVE / Advisory IDs Remedied | Lowest Fixed Version | Version Chosen | Major Bump? |
|---|---|---|---|---|---|
| **`Authlib`** | `1.3.0` | `GHSA-5357-c2jx-v7qh`, `GHSA-9ggr-2464-2j32`, `GHSA-g7f3-828f-7h7m`, `GHSA-pq5p-34cr-23v9`, `GHSA-fg6f-75jq-6523`, `GHSA-7wc2-qxgw-g8gg`, `GHSA-7432-952r-cw78`, `GHSA-m344-f55w-2m6j`, `GHSA-wvwj-cvrp-7pv5`, `GHSA-w8p2-r796-3vmq`, `GHSA-jj8c-mmj3-mmgv`, `GHSA-r95x-qfjj-fjj2`, `GHSA-jj7h-c3hg-m23x`, `GHSA-6v38-4h7w-rj9h`, `GHSA-7vr2-2fgp-9w7p`, `GHSA-c5mf-xmp2-59rc`, `GHSA-fch4-3c6x-j4gc`, `GHSA-q686-2qmg-hqc7`, `GHSA-x4rv-c3wx-4cr8`, `GHSA-8m4g-j4wp-wgcg`, `GHSA-c73q-w75p-j82v` | `1.9.1` | **`1.9.1`** | **No** (stayed on `1.x`) |
| **`gunicorn`** | `21.2.0` | `GHSA-hc5x-x2vx-497g` (PYSEC-2026-1433), `GHSA-w3h3-4rj7-4ph4` (PYSEC-2026-1434) | `22.0.0` | **`22.0.0`** | **Yes** (`21.x` -> `22.0.0`) |
| **`requests`** | `2.31.0` | `GHSA-9wx4-h78v-vm56` (PYSEC-2026-1873), `GHSA-9hjg-9r4m-mvj7` (PYSEC-2026-1872), `GHSA-gc5v-m9x4-r6x2` (PYSEC-2026-2275) | `2.33.0` | **`2.33.0`** | **No** (stayed on `2.x`) |
| **`bleach`** | `6.1.0` | `GHSA-8rfp-98v4-mmr6`, `GHSA-gj48-438w-jh9v` | `6.4.0` | **`6.4.0`** | **No** (stayed on `6.x`) |

---

### 2.2 Deep-Dive per Package

#### 1. Authlib (`1.3.0` -> `1.9.1`)
- **Vulnerabilities Fixed:**
  - `GHSA-5357-c2jx-v7qh` (fixed in 1.3.1): Algorithm confusion between asymmetric public keys and HMAC.
  - `GHSA-9ggr-2464-2j32` (fixed in 1.6.4): Acceptance of unknown `crit` headers in JWS/JWT.
  - `GHSA-g7f3-828f-7h7m` & `GHSA-pq5p-34cr-23v9` (fixed in 1.6.5): JWE `zip=DEF` decompression bomb and oversized JOSE segment DoS.
  - `GHSA-fg6f-75jq-6523` (fixed in 1.6.6): 1-click Account Takeover via authorization code handling.
  - `GHSA-7wc2-qxgw-g8gg` (fixed in 1.6.7): `alg: none` signature verification bypass.
  - `GHSA-7432-952r-cw78` (fixed in 1.6.9): Bleichenbacher padding oracle in JWE RSA1_5.
  - `GHSA-wvwj-cvrp-7pv5` (fixed in 1.6.9): JWS JWK header injection signature bypass.
  - `GHSA-w8p2-r796-3vmq` (fixed in 1.6.10): Open redirect in authorization API.
  - `GHSA-jj8c-mmj3-mmgv` (fixed in 1.6.11): CSRF vulnerability when caching authorization states.
  - `GHSA-r95x-qfjj-fjj2` (fixed in 1.6.12/1.7.1): Open redirect in OIDC hybrid flow.
  - `GHSA-jj7h-c3hg-m23x` (fixed in 1.8.0): Loopback exemption bypass in `is_secure_transport()`.
  - `GHSA-6v38-4h7w-rj9h` & `GHSA-7vr2-2fgp-9w7p` (fixed in 1.9.0): Empty signatures in JWS JSON and HMAC prefix forgery.
  - `GHSA-c5mf-xmp2-59rc`, `GHSA-fch4-3c6x-j4gc`, `GHSA-q686-2qmg-hqc7`, `GHSA-x4rv-c3wx-4cr8` (fixed in 1.9.0): Nonce bypass, assertion audience check, scope validation, and JAR SSRF.
  - `GHSA-8m4g-j4wp-wgcg` & `GHSA-c73q-w75p-j82v` (fixed in 1.9.1): Empty HMAC key signature forgery and RFC 7592 client binding.
- **Breaking Changes Evaluation:**
  - Major version remained `1.x`.
  - The client API used in RunRush (`from authlib.integrations.flask_client import OAuth`, `oauth.register()`, `oauth.google.authorize_redirect()`, `oauth.google.authorize_access_token()`, and `oauth.google.userinfo()`) is fully backwards-compatible.
  - All 10 Google OAuth integration tests passed without changes.

#### 2. Gunicorn (`21.2.0` -> `22.0.0`)
- **Vulnerabilities Fixed:**
  - `GHSA-hc5x-x2vx-497g` / `PYSEC-2026-1433`: HTTP request smuggling via ambiguous `Transfer-Encoding` / `Content-Length` headers.
  - `GHSA-w3h3-4rj7-4ph4` / `PYSEC-2026-1434`: Request smuggling leading to upstream security control bypass when fronted by reverse proxies.
- **Breaking Changes in 22.0.0:**
  - **Python Compatibility:** Dropped support for Python 3.7 (minimum is 3.8; RunRush runs on Python 3.12+ in CI and 3.14 locally).
  - **Removed Flags:** Dropped the legacy `--paste` command-line option.
  - **RFC 9112 Conformance:** Enforces strict HTTP request parsing: header folding is forbidden, conflicting chunked headers are rejected with 400 Bad Request, and trailing chunk validation is tightened.
  - **Render Deployment Impact:** RunRush configures Gunicorn via [`gunicorn.conf.py`](file:///d:/Programming%20codes/Running-py/gunicorn.conf.py) (`bind = f"0.0.0.0:{port}"`). No deprecated options or flags are used.

#### 3. Requests (`2.31.0` -> `2.33.0`)
- **Vulnerabilities Fixed:**
  - `GHSA-9wx4-h78v-vm56` / `PYSEC-2026-1873` (fixed in 2.32.0): `requests.Session` failed to re-enable certificate verification on subsequent calls after a `verify=False` request.
  - `GHSA-9hjg-9r4m-mvj7` / `PYSEC-2026-1872` (fixed in 2.32.4): `.netrc` credentials leaked across cross-origin redirects.
  - `GHSA-gc5v-m9x4-r6x2` / `PYSEC-2026-2275` (fixed in 2.33.0): Insecure temporary file reuse in `extract_zipped_paths()`.
- **Breaking Changes Evaluation:**
  - Major version remained `2.x`.
  - Subsystems relying on `requests` (Authlib OAuth requests client, developer test scripts) retain exact timeout and TLS verification behavior.

#### 4. Bleach (`6.1.0` -> `6.4.0`)
- **Vulnerabilities Fixed:**
  - `GHSA-8rfp-98v4-mmr6` (fixed in 6.4.0): URI sanitization allowed disallowed URI schemes containing Unicode codepoints > U+00A0.
  - `GHSA-gj48-438w-jh9v` (fixed in 6.4.0): `clean()` / `Cleaner()` failed to sanitize dangerous URI schemes in allowed `formaction` attributes.
- **Breaking Changes Evaluation:**
  - Major version remained `6.x`.
  - Usage in RunRush: [`utils/validators.py:178`](file:///d:/Programming%20codes/Running-py/utils/validators.py#L178) (`bleach.clean(notes, tags=[], strip=True)`) and [`app.py:9022`](file:///d:/Programming%20codes/Running-py/app.py#L9022) (`bleach.clean(bio, tags=[], strip=True)`).
  - Because RunRush disallows all HTML tags (`tags=[]`), the sanitization behavior is identical and completely backwards-compatible.

---

## 3. Bleach Assessment & `nh3` Replacement Proposal

### 3.1 Bleach Assessment
Bleach `6.4.0` is currently safe for RunRush because the application strips all HTML tags (`tags=[]`). However, **Mozilla officially deprecated Bleach in 2023** and no longer actively maintains it for new features or ecosystem shifts.

### 3.2 Proposed `nh3` Replacement (Follow-Up Task)
[`nh3`](https://github.com/messense/nh3) is Python bindings to Rust's battle-tested `ammonia` HTML sanitizer. It is the official replacement recommended by the Bleach maintainers:
- **Performance:** ~20x faster than Bleach (written in Rust, zero Python-level parsing overhead).
- **Security:** Built on WHATWG HTML parsing standards; immune to ReDoS and regex-based bypasses.
- **Direct Replacement Pattern:**
  ```python
  # Current Bleach implementation:
  import bleach
  clean_text = bleach.clean(raw_text, tags=[], strip=True).strip()

  # Proposed nh3 implementation:
  import nh3
  clean_text = nh3.clean(raw_text, tags=set()).strip()
  ```
- **Recommendation:** Implement `nh3` as a dedicated follow-up task to retire Bleach permanently.

---

## 4. App Debug Line & Bandit Baseline Removal

### 4.1 Implementation in `app.py`
In [`app.py`](file:///d:/Programming%20codes/Running-py/app.py#L9490):
```python
if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
```
- Default state: `debug_mode` is `False`.
- Local developers can opt in via `FLASK_DEBUG=1`.
- Production runs via Gunicorn WSGI and does not execute `__main__`.

### 4.2 Bandit Baseline Cleaned
- Removed the `B201:flask_debug_true` result from [`bandit-baseline.json`](file:///d:/Programming%20codes/Running-py/bandit-baseline.json).
- Bandit now scans with **0 High-severity issues** natively (`Test results: No issues identified`).

---

## 5. Subsystem Verification

1. **Login & OAuth Flows (Authlib 1.9.1):**
   - Verified PIN-based login, lockout, registration, and session cookies via `tests/test_auth.py`.
   - Verified Google OAuth registration, authorization redirect, token exchange, user info fetching, linking, collision handling, and notifications via `tests/test_google_auth.py` (10/10 passed).
2. **HTML Sanitization (Bleach 6.4.0):**
   - Verified run notes sanitization in `utils/validators.py`.
   - Verified profile bio and next race sanitization in `app.py`.
   - Verified XSS payloads (`<script>`, `<iframe>`, `on*`) are completely stripped with `tags=[]`.
3. **Outbound Requests (Requests 2.33.0):**
   - Verified that HTTP calls maintain explicit timeouts (`timeout=5`, `timeout=10`) and default SSL verification behavior.
4. **Gunicorn Configuration ([`gunicorn.conf.py`](file:///d:/Programming%20codes/Running-py/gunicorn.conf.py)):**
   - `bind = f"0.0.0.0:{port}"` remains standard and supported in Gunicorn 22.0.0.
   - No deprecated flags (`--paste`, etc.) exist in the repository.

---

## 6. Test & Scan Results

| Tool / Suite | Command | Result |
|---|---|---|
| **pytest (Full Suite)** | `pytest -q` | **623 passed** (100% pass rate in 17.05s) |
| **pip-audit** | `pip-audit -r requirements.txt $ALLOWLIST_ARGS` | **PASS** (Authlib, gunicorn, requests, bleach 0 vulns) |
| **bandit (High Severity)** | `bandit -r . -x ./.venv,./pgsql,./scratch,./tests -lll` | **PASS** (0 High findings, 0 issues identified) |
| **ruff** | `ruff check app.py tests/test_security_headers.py tests/test_google_auth.py` | **PASS** (Clean, missing `json` import resolved) |

---

## 7. Git Diff Summary

```diff
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -5,6 +5,7 @@ import re
 import math
 import hashlib
 import click
+import json
 
 if __name__ == "__main__":
-    app.run(debug=True, host="0.0.0.0", port=5000)
+    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
+    app.run(debug=debug_mode, host="0.0.0.0", port=5000)

diff --git a/bandit-baseline.json b/bandit-baseline.json
--- a/bandit-baseline.json
+++ b/bandit-baseline.json
@@ -10,7 +10,7 @@
-      "SEVERITY.HIGH": 1,
+      "SEVERITY.HIGH": 0,
@@ -684,7 +684,7 @@
-      "SEVERITY.HIGH": 1,
+      "SEVERITY.HIGH": 0,
@@ -700,18 +700,1 @@
-  "results": [ ...B201... ]
+  "results": []

diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -9,1 +9,1 @@
-gunicorn==21.2.0
+gunicorn==22.0.0
@@ -20,4 +20,4 @@
-Authlib==1.3.0
-requests==2.31.0
+Authlib==1.9.1
+requests==2.33.0
 python-dotenv==1.0.1
-bleach==6.1.0
+bleach==6.4.0
```
