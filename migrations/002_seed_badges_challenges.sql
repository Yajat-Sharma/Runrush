-- 002_seed_badges_challenges.sql
-- Seeds the initial static definitions for Badges and Challenges.
-- Uses ON CONFLICT DO NOTHING to ensure idempotence and safety on repeated executions.

INSERT INTO badges (key, name, description, criteria_type, criteria_value, icon_url) VALUES
('FIRST_5K', 'First 5K', 'Completed your first 5km run!', 'SINGLE_DISTANCE', 5.0, '/static/badges/5k.png'),
('TOTAL_50KM', '50 KM Warrior', 'Ran a total of 50 kilometers!', 'ACCUMULATIVE_DISTANCE', 50.0, '/static/badges/50km.png'),
('TOTAL_100KM', '100 KM Champion', 'Conquered 100 kilometers total!', 'ACCUMULATIVE_DISTANCE', 100.0, '/static/badges/100km.png'),
('STREAK_7DAY', '7-Day Streak', 'Ran for 7 consecutive days!', 'STREAK', 7.0, '/static/badges/streak7.png'),
('STREAK_30DAY', '30-Day Streak', 'Incredible! 30 days in a row!', 'STREAK', 30.0, '/static/badges/streak30.png'),
('FIRST_10K', 'First 10K', 'Completed your first 10km run!', 'SINGLE_DISTANCE', 10.0, '/static/badges/10k.png')
ON CONFLICT (key) DO NOTHING;

INSERT INTO challenges (key, name, description, target_value) VALUES
('MONTHLY_20KM', '20K This Month', 'Run a total of 20 km within this calendar month.', 20.0),
('MONTHLY_50KM', '50K Month', 'Run a total of 50 km within this calendar month.', 50.0),
('MONTHLY_10RUNS', '10 Runs This Month', 'Log 10 runs within this calendar month.', 10.0),
('MONTHLY_LONG_RUN', 'Long Run Month', 'Complete a single run of 15 km or more this month.', 15.0)
ON CONFLICT (key) DO NOTHING;
