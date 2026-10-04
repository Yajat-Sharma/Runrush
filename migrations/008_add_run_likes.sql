-- migrations/008_add_run_likes.sql
--
-- Likes on runs for the Home activity feed. For manual application against an
-- existing production database (init_db() also creates it on fresh installs,
-- following the same dual pattern as migrations/006 and 007).

CREATE TABLE IF NOT EXISTS run_likes (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_run_likes_run_id ON run_likes(run_id);
