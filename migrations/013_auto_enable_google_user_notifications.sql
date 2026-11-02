-- migrations/013_auto_enable_google_user_notifications.sql
-- Automatically enable weekly and monthly email notifications for users with Google accounts
UPDATE users 
SET email = COALESCE(NULLIF(email, ''), google_email),
    email_monthly_summary = 1,
    email_weekly_summary = 1
WHERE (google_id IS NOT NULL OR google_email IS NOT NULL);
