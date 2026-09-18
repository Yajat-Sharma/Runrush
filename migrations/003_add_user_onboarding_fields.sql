-- Add missing onboarding fields to users table
ALTER TABLE users ADD COLUMN experience TEXT;
ALTER TABLE users ADD COLUMN primary_goal TEXT;
ALTER TABLE users ADD COLUMN frequency TEXT;
