-- Migration 017: Add race name and AI plan data to user_goals
ALTER TABLE user_goals ADD COLUMN IF NOT EXISTS race_name TEXT;
ALTER TABLE user_goals ADD COLUMN IF NOT EXISTS ai_plan_json TEXT;
