"""
Tests for Security Headers, Talisman, ProxyFix, and Content Security Policy.
"""

import json

from app import app as flask_app


class TestSecurityHeaders:
    """Verify security headers are applied to HTTP responses."""

    def test_security_headers_present_on_normal_response(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

        # X-Content-Type-Options
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'

        # Referrer-Policy
        assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

        # Frame protection (X-Frame-Options: DENY)
        assert resp.headers.get('X-Frame-Options') == 'DENY'

        # Permissions-Policy
        perm_policy = resp.headers.get('Permissions-Policy', '')
        assert 'geolocation=(self)' in perm_policy
        assert 'microphone=(self)' in perm_policy
        assert 'camera=()' in perm_policy
        assert 'payment=()' in perm_policy
        assert 'usb=()' in perm_policy

    def test_hsts_header_present_on_secure_request(self, client):
        resp = client.get('/login', headers={'X-Forwarded-Proto': 'https'})
        assert resp.status_code == 200

        hsts = resp.headers.get('Strict-Transport-Security')
        assert hsts is not None
        assert 'max-age=31536000' in hsts
        assert 'includeSubDomains' in hsts
        assert 'preload' not in hsts  # NO preload yet

    def test_csp_is_report_only_and_configured(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

        # Must be report-only, NOT enforced
        assert 'Content-Security-Policy' not in resp.headers
        csp = resp.headers.get('Content-Security-Policy-Report-Only')
        assert csp is not None

        # Verify core directives
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp
        assert "worker-src 'self'" in csp
        assert "manifest-src 'self'" in csp
        assert "base-uri 'self'" in csp
        assert "form-action 'self'" in csp
        assert "report-uri /csp-report" in csp

        # Verify no unsafe-inline or unsafe-eval in script-src
        # Extract script-src directive
        directives = {d.strip().split()[0]: d.strip() for d in csp.split(';') if d.strip()}
        script_src = directives.get('script-src', '')
        assert "'unsafe-inline'" not in script_src
        assert "'unsafe-eval'" not in script_src

        # Verify expected origins
        assert "https://cdn.jsdelivr.net" in script_src
        assert "https://cdnjs.cloudflare.com" in script_src
        assert "https://unpkg.com" in script_src

    def test_session_cookies_have_correct_flags(self, client):
        resp = client.post('/login', data={'username': 'testuser', 'pin': '1234'})
        cookie_header = resp.headers.get('Set-Cookie', '')
        assert 'session=' in cookie_header
        assert 'HttpOnly' in cookie_header
        assert 'SameSite=Lax' in cookie_header
        assert 'Secure' in cookie_header


class TestHttpsAndProxyFix:
    """Verify HTTPS enforcement and ProxyFix behavior behind reverse proxy."""

    def test_http_to_https_redirect_and_no_loop_with_proxy_fix(self, client):
        flask_app.config['FORCE_HTTPS'] = True
        try:
            # 1. Plain HTTP forwarded request -> should redirect to https
            http_resp = client.get(
                '/login',
                base_url='http://localhost',
                headers={'X-Forwarded-Proto': 'http'}
            )
            assert http_resp.status_code in (301, 302)
            assert http_resp.headers.get('Location', '').startswith('https://')

            # 2. Forwarded HTTPS request -> should serve 200 without redirect loop
            https_resp = client.get(
                '/login',
                base_url='http://localhost',
                headers={'X-Forwarded-Proto': 'https'}
            )
            assert https_resp.status_code == 200
        finally:
            flask_app.config.pop('FORCE_HTTPS', None)


class TestCspReportEndpoint:
    """Verify the /csp-report endpoint."""

    def test_csp_report_accepts_valid_payload(self, client):
        payload = {
            "csp-report": {
                "document-uri": "https://runrush.me/dashboard",
                "referrer": "",
                "violated-directive": "script-src 'self'",
                "effective-directive": "script-src",
                "original-policy": "default-src 'self'; report-uri /csp-report",
                "blocked-uri": "inline",
                "status-code": 200
            }
        }
        resp = client.post(
            '/csp-report',
            data=json.dumps(payload),
            content_type='application/csp-report'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == 'received'

    def test_csp_report_rejects_oversized_payload(self, client):
        # Create a payload larger than 10 KB limit
        oversized_payload = {"data": "X" * (12 * 1024)}
        resp = client.post(
            '/csp-report',
            data=json.dumps(oversized_payload),
            content_type='application/json'
        )
        assert resp.status_code == 413
        data = resp.get_json()
        assert 'Payload too large' in data.get('error', '')

    def test_csp_report_is_csrf_exempt(self, app):
        app.config['WTF_CSRF_ENABLED'] = True
        client = app.test_client()
        try:
            resp = client.post(
                '/csp-report',
                data=json.dumps({"csp-report": {"blocked-uri": "inline"}}),
                content_type='application/json'
            )
            # Should succeed with 200 and NOT be rejected with 400 Bad Request (CSRF error)
            assert resp.status_code == 200
        finally:
            app.config['WTF_CSRF_ENABLED'] = False


class TestPwaAndStaticIntegrity:
    """Verify Service Worker, Manifest, and static routes function properly."""

    def test_sw_served_with_correct_headers(self, client):
        resp = client.get('/sw.js')
        assert resp.status_code == 200
        assert 'javascript' in resp.headers.get('Content-Type', '')
        assert resp.headers.get('Service-Worker-Allowed') == '/'

    def test_offline_page_accessible(self, client):
        resp = client.get('/offline')
        assert resp.status_code == 200
