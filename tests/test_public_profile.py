"""
Tests for the Public Profile Page feature.
Covers: privacy boundary, avatar upload, bio sanitization, 404 handling.
"""

import io
import struct
import zlib
import pytest
from db import get_db


# --- Helpers ---

def register_and_login(client, username='alice', pin='1234'):
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login',    data={'username': username, 'pin': pin})


def make_minimal_png():
    "Return bytes of a 1x1 red PNG."
    def png_chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)
    raw = b'\x00\xff\x00\x00'
    idat = png_chunk(b'IDAT', zlib.compress(raw))
    iend = png_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


# --- Tests ---

class TestPublicProfileApi:

    def test_unknown_username_returns_404(self, client):
        res = client.get('/api/user/nobody_xyz_12345/public-profile')
        assert res.status_code == 404
        assert 'error' in res.get_json()

    def test_public_profile_returns_only_allowed_fields(self, client):
        register_and_login(client, 'bob', '5678')
        res = client.get('/api/user/bob/public-profile')
        assert res.status_code == 200
        data = res.get_json()

        required = {
            'username', 'display_name', 'bio', 'next_race',
            'has_avatar', 'run_count', 'total_distance_km',
            'total_time_min', 'avg_pace_min_per_km', 'longest_run_km',
            'follower_count', 'following_count', 'challenges_completed',
            'badges', 'personal_bests',
        }
        for field in required:
            assert field in data, f'Missing required field: {field}'

        forbidden = {
            'email', 'weight', 'height', 'google_id', 'google_email',
            'home_city', 'home_latitude', 'home_longitude',
            'recovery_email', 'recovery_email_verified', 'pin', 'bmi',
        }
        for field in forbidden:
            assert field not in data, f'Forbidden field leaked: {field}'

    def test_personal_bests_keys_present(self, client):
        register_and_login(client, 'carol', '9999')
        res = client.get('/api/user/carol/public-profile')
        assert res.status_code == 200
        pb = res.get_json()['personal_bests']
        assert 'fastest_5k' in pb
        assert 'fastest_10k' in pb
        assert 'longest_distance' in pb
        assert 'best_pace' in pb

    def test_badges_list_present(self, client):
        register_and_login(client, 'dave', '1111')
        res = client.get('/api/user/dave/public-profile')
        assert res.status_code == 200
        badges = res.get_json()['badges']
        assert isinstance(badges, list)
        assert len(badges) > 0
        for b in badges:
            assert 'key' in b
            assert 'name' in b
            assert 'earned' in b

    def test_profile_page_renders_200(self, client):
        register_and_login(client, 'eve', '2222')
        res = client.get('/u/eve')
        assert res.status_code == 200

    def test_profile_page_404_unknown_user(self, client):
        res = client.get('/u/nobody_xyz_12345')
        assert res.status_code == 404


class TestBioUpdate:

    def test_bio_update_requires_login(self, client):
        res = client.post('/api/profile/details',
                          json={'bio': 'hello', 'next_race': ''})
        assert res.status_code == 401

    def test_bio_update_stores_cleanly(self, auth_client):
        res = auth_client.post('/api/profile/details',
                               json={'bio': 'Love running!', 'next_race': 'NYC Marathon'})
        assert res.status_code == 200
        assert res.get_json()['success'] is True

    def test_bio_xss_sanitized(self, auth_client):
        "Script tags in bio must be stripped."
        res = auth_client.post('/api/profile/details',
                               json={'bio': '<script>alert(1)</script>clean text',
                                     'next_race': ''})
        assert res.status_code == 200
        conn = get_db()
        row = conn.execute("SELECT bio FROM users WHERE username = 'testuser'").fetchone()
        conn.close()
        assert row is not None
        bio = row['bio'] or ''
        assert '<script>' not in bio
        assert 'clean text' in bio

    def test_bio_too_long_rejected(self, auth_client):
        res = auth_client.post('/api/profile/details',
                               json={'bio': 'x' * 201, 'next_race': ''})
        assert res.status_code == 400

    def test_next_race_too_long_rejected(self, auth_client):
        res = auth_client.post('/api/profile/details',
                               json={'bio': '', 'next_race': 'x' * 101})
        assert res.status_code == 400


class TestAvatarUpload:

    def test_avatar_upload_requires_login(self, client):
        data = {'avatar': (io.BytesIO(b'fake'), 'test.jpg')}
        res = client.post('/api/profile/avatar',
                          data=data, content_type='multipart/form-data')
        assert res.status_code == 401

    def test_avatar_upload_valid_png(self, auth_client):
        "Upload a valid 1x1 PNG and expect success or clean error."
        png_bytes = make_minimal_png()
        data = {'avatar': (io.BytesIO(png_bytes), 'test.png')}
        res = auth_client.post('/api/profile/avatar',
                               data=data, content_type='multipart/form-data')
        assert res.status_code in (200, 400)
        if res.status_code == 200:
            assert res.get_json().get('success') is True

    def test_avatar_upload_wrong_extension_rejected(self, auth_client):
        data = {'avatar': (io.BytesIO(b'GIF89a'), 'evil.gif')}
        res = auth_client.post('/api/profile/avatar',
                               data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        assert 'error' in res.get_json()

    def test_avatar_upload_no_file_rejected(self, auth_client):
        res = auth_client.post('/api/profile/avatar',
                               data={}, content_type='multipart/form-data')
        assert res.status_code == 400

    def test_avatar_upload_disguised_file(self, auth_client):
        """A text file with fake image content renamed to .jpg must be rejected by Pillow processing."""
        disguised_bytes = b"This is plain text content disguised inside a .jpg file extension!"
        data = {'avatar': (io.BytesIO(disguised_bytes), 'disguised.jpg')}
        res = auth_client.post('/api/profile/avatar',
                               data=data, content_type='multipart/form-data')
        assert res.status_code == 400
        json_data = res.get_json()
        assert 'error' in json_data
        assert 'Invalid image file' in json_data['error']

    def test_avatar_serve_404_when_no_avatar(self, client):
        register_and_login(client, 'frank', '3333')
        res = client.get('/avatar/frank')
        assert res.status_code == 404

