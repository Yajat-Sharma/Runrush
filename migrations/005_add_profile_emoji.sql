-- 005_add_profile_emoji.sql
-- Add profile_emoji column to users table with a fallback default for legacy users

ALTER TABLE users ADD COLUMN profile_emoji TEXT DEFAULT '🏃🏻';
