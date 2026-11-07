-- Migration 016: Add Group Friendly Challenges (3-10 Participants) V2
-- Supports Free-For-All (FFA) group challenges while preserving 1v1 functionality.

-- 1. Alter friendly_challenges for challenge mode and max participants
ALTER TABLE friendly_challenges ADD COLUMN IF NOT EXISTS challenge_mode TEXT NOT NULL DEFAULT '1V1';
ALTER TABLE friendly_challenges ADD COLUMN IF NOT EXISTS max_participants INTEGER NOT NULL DEFAULT 2;

-- Allow opponent_id to be NULL for group challenges (PostgreSQL)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'friendly_challenges' AND column_name = 'opponent_id' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE friendly_challenges ALTER COLUMN opponent_id DROP NOT NULL;
    END IF;
END $$;

-- Update CHECK constraint if exists
DO $$
BEGIN
    ALTER TABLE friendly_challenges DROP CONSTRAINT IF EXISTS friendly_challenges_check;
    ALTER TABLE friendly_challenges ADD CONSTRAINT friendly_challenges_check CHECK (opponent_id IS NULL OR challenger_id != opponent_id);
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- 2. Alter challenge_participants for invitation status and leaderboard rank
ALTER TABLE challenge_participants ADD COLUMN IF NOT EXISTS invitation_status TEXT NOT NULL DEFAULT 'ACCEPTED';
ALTER TABLE challenge_participants ADD COLUMN IF NOT EXISTS rank INTEGER;

-- 3. Alter challenge_awards for placement rank
ALTER TABLE challenge_awards ADD COLUMN IF NOT EXISTS rank INTEGER DEFAULT 1;

-- 4. Indexes for group queries
CREATE INDEX IF NOT EXISTS idx_friendly_challenges_mode ON friendly_challenges(challenge_mode);
CREATE INDEX IF NOT EXISTS idx_challenge_participants_invitation_status ON challenge_participants(invitation_status);
