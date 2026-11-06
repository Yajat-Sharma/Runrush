-- Migration 015: Add Friendly Challenges V1 Schema
-- Tables: friendly_challenges, challenge_participants, challenge_awards, challenge_activity

CREATE TABLE IF NOT EXISTS friendly_challenges (
    id SERIAL PRIMARY KEY,
    challenger_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    opponent_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    challenge_type TEXT NOT NULL,
    title TEXT,
    message TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    challenge_timezone TEXT NOT NULL DEFAULT 'UTC',
    status TEXT NOT NULL DEFAULT 'INVITED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,
    expires_at TIMESTAMP,
    completed_at TIMESTAMP,
    winner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    result_type TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (challenger_id != opponent_id)
);

CREATE TABLE IF NOT EXISTS challenge_participants (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    final_score REAL DEFAULT 0.0,
    score_unit TEXT NOT NULL,
    result TEXT DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(challenge_id, user_id)
);

CREATE TABLE IF NOT EXISTS challenge_awards (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    award_type TEXT NOT NULL DEFAULT 'FRIENDLY_CHALLENGE_WIN',
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(challenge_id, user_id)
);

CREATE TABLE IF NOT EXISTS challenge_activity (
    id SERIAL PRIMARY KEY,
    challenge_id INTEGER NOT NULL REFERENCES friendly_challenges(id) ON DELETE CASCADE,
    actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_friendly_challenges_status ON friendly_challenges(status);
CREATE INDEX IF NOT EXISTS idx_friendly_challenges_challenger ON friendly_challenges(challenger_id);
CREATE INDEX IF NOT EXISTS idx_friendly_challenges_opponent ON friendly_challenges(opponent_id);
CREATE INDEX IF NOT EXISTS idx_friendly_challenges_dates ON friendly_challenges(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_challenge_participants_user ON challenge_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_challenge_participants_challenge ON challenge_participants(challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_awards_user ON challenge_awards(user_id);
CREATE INDEX IF NOT EXISTS idx_challenge_awards_challenge ON challenge_awards(challenge_id);
CREATE INDEX IF NOT EXISTS idx_challenge_activity_challenge ON challenge_activity(challenge_id);
