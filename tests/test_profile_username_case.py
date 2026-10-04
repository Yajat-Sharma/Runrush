"""
The public profile page passes the raw URL segment (e.g. /u/ALICE) to its
follow-up data calls. /api/user/<u>/public-profile and /heatmap already match
usernames case-insensitively, but /avatar/<u> matched exactly, so a mixed-case
profile URL lost the avatar image while everything else loaded.
"""

import pytest
from tests.test_public_profile import make_minimal_png


def register_and_login(client, username='alice', pin='1234'):
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


class TestAvatarUsernameCase:

    def _upload(self, client):
        import io
        res = client.post('/api/profile/avatar', data={
            'avatar': (io.BytesIO(make_minimal_png()), 'a.png', 'image/png')
        }, content_type='multipart/form-data')
        assert res.status_code == 200, res.get_data(as_text=True)

    @pytest.mark.parametrize('spelling', ['alice', 'ALICE', 'Alice'])
    def test_avatar_served_for_any_casing(self, client, spelling):
        register_and_login(client)
        self._upload(client)
        res = client.get(f'/avatar/{spelling}')
        assert res.status_code == 200
        assert res.mimetype.startswith('image/')

    def test_unknown_avatar_still_404(self, client):
        assert client.get('/avatar/nobody_xyz').status_code == 404
