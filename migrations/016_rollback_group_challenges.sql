-- Rollback Migration 016: Group Friendly Challenges (V2 -> V1)
-- Reverts FFA Group challenge additions to restore standard 1v1 schema.

-- 1. Drop added indexes
DROP INDEX IF EXISTS idx_challenge_participants_invitation_status;
DROP INDEX IF EXISTS idx_friendly_challenges_mode;

-- 2. Clean up any GROUP challenges or participants before dropping columns (PostgreSQL)
DO $$
BEGIN
    -- Delete group challenges if rolling back to strict 1v1
    DELETE FROM friendly_challenges WHERE challenge_mode = 'GROUP';
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- 3. Restore NOT NULL constraint on opponent_id (PostgreSQL)
DO $$
BEGIN
    ALTER TABLE friendly_challenges ALTER COLUMN opponent_id SET NOT NULL;
    ALTER TABLE friendly_challenges DROP CONSTRAINT IF EXISTS friendly_challenges_check;
    ALTER TABLE friendly_challenges ADD CONSTRAINT friendly_challenges_check CHECK (challenger_id != opponent_id);
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- 4. Drop added columns (PostgreSQL)
DO $$
BEGIN
    ALTER TABLE challenge_awards DROP COLUMN IF EXISTS rank;
    ALTER TABLE challenge_participants DROP COLUMN IF EXISTS rank;
    ALTER TABLE challenge_participants DROP COLUMN IF EXISTS invitation_status;
    ALTER TABLE friendly_challenges DROP COLUMN IF EXISTS max_participants;
    ALTER TABLE friendly_challenges DROP COLUMN IF EXISTS challenge_mode;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;
