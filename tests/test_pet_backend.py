import pytest
import os
from datetime import datetime, date
from db import get_db
from app import app
from services.pet_service import (
    calculate_level, 
    adopt_pet, 
    adopt_new_pet, 
    switch_active_pet, 
    get_user_collection,
    get_active_pet,
    rename_pet,
    feed_pet
)

@pytest.fixture
def setup_db(app):
    with app.app_context():
        conn = get_db()
        conn.execute("DELETE FROM user_pet_collection")
        conn.execute("DELETE FROM user_pets")
        conn.execute("DELETE FROM runs WHERE user_id IN (SELECT id FROM users WHERE username = 'pet_tester2')")
        conn.execute("DELETE FROM users WHERE username = 'pet_tester2'")
        
        conn.execute("INSERT INTO users (username, pin) VALUES ('pet_tester2', '1234')")
        user = conn.execute("SELECT id FROM users WHERE username = 'pet_tester2'").fetchone()
        user_id = user['id']
        conn.commit()
        
        yield user_id
        
        conn.execute("DELETE FROM user_pet_collection WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_pets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM runs WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()


def test_level_boundaries():
    # 0 KM → Level 1 — Egg
    assert calculate_level(0.0) == 1
    assert calculate_level(9.9) == 1
    # 10 KM → Level 2 — Baby
    assert calculate_level(10.0) == 2
    assert calculate_level(10.1) == 2
    assert calculate_level(29.9) == 2
    # 30 KM → Level 3 — Growing
    assert calculate_level(30.0) == 3
    assert calculate_level(30.1) == 3
    assert calculate_level(59.9) == 3
    # 60 KM → Level 4 — Developing
    assert calculate_level(60.0) == 4
    assert calculate_level(60.1) == 4
    assert calculate_level(99.9) == 4
    # 100 KM → Level 5 — Full Grown
    assert calculate_level(100.0) == 5
    assert calculate_level(150.0) == 5


def test_new_pet_starts_at_0_and_progression_persists(setup_db):
    user_id = setup_db
    with app.app_context():
        # Adopt first pet
        adopt_pet(user_id, "Fido", "dog")
        active = get_active_pet(user_id)
        assert active['pet_name'] == "Fido"
        assert active['total_km_fed'] == 0.0
        assert active['level'] == 1
        
        # Feed it some distance
        feed_pet(user_id, 10.0, "2026-09-14")
        active = get_active_pet(user_id)
        assert active['total_km_fed'] == 10.0
        assert active['level'] == 2
        
        # Adopt second pet (will be active)
        success, err = adopt_new_pet(user_id, "Sky", "bird")
        assert success is True
        
        active2 = get_active_pet(user_id)
        assert active2['pet_name'] == "Sky"
        # It should start at 0 independently of the dog's 10.0km
        assert active2['total_km_fed'] == 0.0
        assert active2['level'] == 1


def test_pet_switching_does_not_reset_progression(setup_db):
    user_id = setup_db
    with app.app_context():
        adopt_pet(user_id, "Fido", "dog")
        feed_pet(user_id, 35.0, "2026-09-14")
        
        # Fido is level 3, 35 KM
        fido = get_active_pet(user_id)
        assert fido['level'] == 3
        
        # Adopt bird
        adopt_new_pet(user_id, "Tweety", "bird")
        
        # Now Tweety is active and at 0km
        active = get_active_pet(user_id)
        assert active['pet_type'] == 'bird'
        assert active['total_km_fed'] == 0.0
        
        # Feed Tweety
        feed_pet(user_id, 15.0, "2026-09-14")
        active = get_active_pet(user_id)
        assert active['total_km_fed'] == 15.0
        
        # Switch back to dog (we need dog's collection_id)
        collection = get_user_collection(user_id)
        dog_id = next(c['id'] for c in collection if c['pet_type'] == 'dog')
        switch_active_pet(user_id, dog_id)
        
        # Fido's progression should be intact (still 35km), Tweety's feed didn't leak
        restored = get_active_pet(user_id)
        assert restored['pet_type'] == 'dog'
        assert restored['level'] == 3
        assert restored['total_km_fed'] == 35.0


def test_duplicate_pet_type_rejected(setup_db):
    user_id = setup_db
    with app.app_context():
        adopt_pet(user_id, "Fido1", "dog")
        # Trying to adopt a second dog should return (False, error)
        success, err = adopt_new_pet(user_id, "Fido2", "dog")
        assert success is False
        assert err == "You already have this pet type"
        
        collection = get_user_collection(user_id)
        assert len(collection) == 1
        assert collection[0]['pet_name'] == "Fido1"


def test_rename_works(setup_db):
    user_id = setup_db
    with app.app_context():
        adopt_pet(user_id, "Fido", "dog")
        collection = get_user_collection(user_id)
        dog_id = collection[0]['id']
        
        success = rename_pet(user_id, dog_id, "Rex")
        assert success is True
        
        active = get_active_pet(user_id)
        assert active['pet_name'] == "Rex"
