# RunRush Database Migration Map (Current → Target)

This document maps the tables and columns from the legacy SQLite/PostgreSQL schema to the target optimized PostgreSQL schema.

## Users & Identity

| Current Table | Current Column | Target Table | Target Column | Migration Strategy |
| --- | --- | --- | --- | --- |
| `users` | `id` | `users` | `id` | Exact transfer (preserve PK) |
| `users` | `username`, `pin`, etc. | `users` | *same* | Exact transfer |
| `users` | `weekly_goal_km` | *removed* | *removed* | Legacy duplicate. Values should be preserved in `user_weekly_goals`. |
| `user_weekly_goals` | `user_id`, `goal_km` | `user_weekly_goals` | `user_id`, `goal_km` | Exact transfer |
| `pin_resets` | *all columns* | `pin_resets` | *all columns* | Exact transfer |
| `admin_notes` | *all columns* | `admin_notes` | *all columns* | Exact transfer |

## Runs & Activities

| Current Table | Current Column | Target Table | Target Column | Migration Strategy |
| --- | --- | --- | --- | --- |
| `runs` | `id` | `runs` | `id` | Exact transfer (preserve PK) |
| `runs` | *all columns* | `runs` | *same* | Exact transfer |
| `user_stats` | *all columns* | `user_stats` | *same* | Exact transfer |
| `edit_history` | *all columns* | `edit_history` | *same* | Exact transfer |
| `activity_logs` | *all columns* | `activity_logs` | *same* | Exact transfer |

## Social

| Current Table | Current Column | Target Table | Target Column | Migration Strategy |
| --- | --- | --- | --- | --- |
| `friends` | *all columns* | `friends` | *same* | Exact transfer |

## Goals & Achievements (Foreign Key Refactoring)

| Current Table | Current Column | Target Table | Target Column | Migration Strategy |
| --- | --- | --- | --- | --- |
| `user_goals` | *all columns* | `user_goals` | *same* | Exact transfer |
| `badges` | `key` (TEXT) | `badges` | `key` (TEXT) | Create `badges` dictionary items with `id` (SERIAL). |
| `user_badges` | `badge_key` (TEXT) | `user_badges` | `badge_id` (INTEGER) | Look up `badges.id` by `badge_key` and map it during transfer. |
| *none* | *none* | `challenges` | *all columns* | Create authoritative dictionary table for challenges. |
| `user_challenge_progress` | `challenge_key` (TEXT) | `user_challenge_progress` | `challenge_id` (INTEGER) | Look up `challenges.id` by `challenge_key` and map it during transfer. |

## Pets (Consolidation)

| Current Table | Current Column | Target Table | Target Column | Migration Strategy |
| --- | --- | --- | --- | --- |
| `user_pet_collection` | *all columns* | `user_pets` | *all columns* | Direct 1:1 transfer of all user pets into the new unified `user_pets` table. |
| `user_pets` (Legacy) | `pet_type` | `user_pets` | `is_active` | Update `user_pets` in target schema: `SET is_active = TRUE` where `user_pets.user_id = Legacy.user_id` AND `user_pets.pet_type = Legacy.pet_type`. |
