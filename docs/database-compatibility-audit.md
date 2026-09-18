# RunRush Database Compatibility Audit

This document identifies SQL queries in the application codebase that will break or require modification once the new PostgreSQL target schema is applied.

## 1. `user_pets` and `user_pet_collection`

**Findings**: 
The codebase (`app.py`, `services/pet_service.py`) currently reads and writes from two separate tables for pet management: `user_pets` (active pet) and `user_pet_collection` (all pets).

**Required Changes**:
- **Consolidation**: Any `INSERT` or `UPDATE` targeting `user_pet_collection` must instead target `user_pets`.
- **Active Pet Retrieval**: Queries like `SELECT pet_name FROM user_pets WHERE user_id = ?` must be appended with `AND is_active = TRUE`.
- **Switching Pets**: Logic that updates `user_pets.pet_type` will need to be rewritten to toggle `is_active = FALSE` for the old pet and `is_active = TRUE` for the newly selected pet in the unified `user_pets` table.

## 2. `user_badges` & `badges`

**Findings**:
The application currently inserts text identifiers directly into the database:
`INSERT INTO user_badges (user_id, badge_key, unlocked_at, activity_id) VALUES (?, 'first_5k', ?, ?)`

**Required Changes**:
- **Foreign Key Lookup**: The codebase must query the `badges` dictionary table to fetch the `badge_id` for `'first_5k'` before inserting into `user_badges`.
- **Profile Rendering**: The route fetching unlocked badges will need to `JOIN badges ON user_badges.badge_id = badges.id` to retrieve the `badge_key`, `name`, and `icon_url`.

## 3. `user_challenge_progress`

**Findings**:
Similar to badges, challenges are tracked via `challenge_key` string matching.

**Required Changes**:
- Code must `JOIN` against the new `challenges` authoritative table, or query `challenge_id` before inserting progress updates.

## 4. `user_weekly_goals`

**Findings**:
The application reads and writes `goal_km` from `user_weekly_goals`.
*Compatibility Check*: **100% Compatible**. The final target schema retains this table exactly as expected by the current application logic.

## 5. `runs`

**Findings**:
Heavily referenced across all stats, dashboard, and analytics logic.
*Compatibility Check*: **100% Compatible**. The schema remains identical (with the addition of database-level foreign key cascades which are invisible to the application queries).

## 6. `friends`

**Findings**:
Used for follow/unfollow and activity feed logic.
*Compatibility Check*: **100% Compatible**. The application logic will continue functioning without modification.

## 7. Next Steps for Development Team
Prior to Phase H (Render Cutover), a Pull Request must be prepared containing the aforementioned application-level SQL query refactors for `pets`, `badges`, and `challenges` to ensure the codebase gracefully interfaces with the newly structured PostgreSQL schema.
