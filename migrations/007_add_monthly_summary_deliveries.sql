-- migrations/007_add_monthly_summary_deliveries.sql
--
-- For manual application against an existing production database that
-- predates this table (init_db() also creates it on any fresh install,
-- following the same dual pattern established by migrations/006 +
-- apply_migration_006.py).

CREATE TABLE IF NOT EXISTS monthly_summary_deliveries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error TEXT,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_summary_deliveries_user ON monthly_summary_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_monthly_summary_deliveries_status ON monthly_summary_deliveries(status);

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_monthly_summary INTEGER DEFAULT 1;
