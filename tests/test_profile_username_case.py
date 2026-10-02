"""
The public profile page passes the raw URL segment (e.g. /u/ALICE) to its
follow-up data calls. /api/user/<u>/public-profile and /heatmap already match
usernames case-insensitively, but /api/pet-collection and /avatar/<u> matched
exactly, so a mixed-case profile URL lost the Pace Pet section and the avatar
image while everything else loaded.
"""

import pytest
from tests.test_public_profile import make_minimal_png


def register_and_login(client, username='alice', pin='1234'):
    client.post('/register', data={'username': username, 'pin': pin})
    client.post('/login', data={'username': username, 'pin': pin})


def adopt(client, name='Zoomie'):
    r = client.post('/api/adopt-pet', json={'pet_name': name, 'pet_type': 'dog'})
    assert r.status_code == 200, r.get_data(as_text=True)


def owned(client, username):
    res = client.get(f'/api/pet-collection?username={username}')
    return res, [p for p in (res.get_json() or {}).get('collection', []) if p.get('status') == 'owned']


class TestPetCollectionUsernameCase:

    @pytest.mark.parametrize('spelling', ['alice', 'ALICE', 'Alice', 'aLiCe'])
    def test_owned_pet_found_for_any_casing(self, client, spelling):
        register_and_login(client)
        adopt(client)
        res, pets = owned(client, spelling)
        assert res.status_code == 200
        assert [p['pet_name'] for p in pets] == ['Zoomie']

    def test_unknown_user_still_404(self, client):
        register_and_login(client)
        res, _ = owned(client, 'nobody_xyz')
        assert res.status_code == 404

    def test_still_requires_login(self, client):
        res = client.get('/api/pet-collection?username=alice')
        assert res.status_code == 401


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
