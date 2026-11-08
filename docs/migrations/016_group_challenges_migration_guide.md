# Migration 016: Friendly Challenges V2 (Group & Duel Formats)

## Overview
Migration `016_add_group_challenges.sql` extends RunRush Friendly Challenges from strict 1v1 duels to Free-For-All (FFA) group challenges supporting 3 to 10 total participants, while maintaining 100% backward compatibility for all existing 1v1 challenge records and workflows.

---

## 1. Schema Changes & Diff

### `friendly_challenges` table
| Column | Type | Default | Description |
|---|---|---|---|
| `challenge_mode` | `TEXT` / `VARCHAR(20)` | `'1V1'` | Format of challenge: `'1V1'`, `'DUEL'`, or `'GROUP'`. |
| `max_participants` | `INTEGER` | `2` | Maximum capacity (2 for DUEL, 3–10 for GROUP). |
| `opponent_id` | `INTEGER REFERENCES users(id)` | `NULL` | Nullable in PostgreSQL for multi-runner FFA groups. |

- **Constraint Change:**
  - Old constraint: `CHECK (challenger_id != opponent_id)` (with `opponent_id NOT NULL`)
  - New constraint: `CHECK (opponent_id IS NULL OR challenger_id != opponent_id)`

### `challenge_participants` table
| Column | Type | Default | Description |
|---|---|---|---|
| `invitation_status` | `TEXT` / `VARCHAR(20)` | `'ACCEPTED'` | Per-runner invitation state: `'INVITED'`, `'ACCEPTED'`, `'REJECTED'`, `'EXPIRED'`. |
| `rank` | `INTEGER` | `NULL` | Final leaderboard placement (1, 2, 3, etc.). |

- **Unique Constraint:**
  - `UNIQUE(challenge_id, user_id)` guarantees a runner cannot be added to a challenge more than once.

### `challenge_awards` table
| Column | Type | Default | Description |
|---|---|---|---|
| `rank` | `INTEGER` | `1` | Placement rank for which medal was awarded (1 for Gold / Shared Gold). |

### Added Indexes
- `idx_friendly_challenges_mode` ON `friendly_challenges(challenge_mode)`
- `idx_challenge_participants_invitation_status` ON `challenge_participants(invitation_status)`

---

## 2. Compatibility (SQLite & PostgreSQL)

1. **SQLite In-Memory & File Databases:**
   - SQLite does not support `ALTER COLUMN DROP NOT NULL`. For SQLite development and test environments, `create_group_challenge` stores the first invitee in `opponent_id` while setting `challenge_mode = 'GROUP'`.
   - All columns and indexes are added idempotently in `services/friendly_challenge_service.py:create_friendly_challenge_tables()`.

2. **PostgreSQL Production Databases:**
   - Migration 016 uses a `DO $$` block to drop `NOT NULL` on `opponent_id` and replace the check constraint safely without table recreation or data loss.

---

## 3. SCHEDULED Status Resolution

- **Database Truth:**
  - The `status` column in `friendly_challenges` strictly stores lifecycle transitions: `'INVITED'`, `'ACCEPTED'`, `'COMPLETED'`, `'REJECTED'`, `'CANCELLED'`, and `'EXPIRED'`.
- **Dynamic Display Layer:**
  - `SCHEDULED` is not a persisted database state; rather, it is a dynamic status computed by `get_challenge_display_status(chal)`.
  - When `chal['status'] == 'ACCEPTED'` and `now_local < chal['start_date']`, the display status is `'SCHEDULED'`.
  - Once `now_local >= chal['start_date']`, the display status automatically shifts to `'ACTIVE'`.
  - This ensures all SQL queries for active/ongoing duels filter on `status = 'ACCEPTED'` without needing cron jobs to flip status strings on midnight.

---

## 4. Participant Limits & Roster Locking

- **Capacity Bounds:**
  - Free-For-All Group challenges require a minimum of 3 total participants (creator + 2 invitees) and a maximum of 10 total participants (creator + 9 invitees).
  - Enforced transactionally in `validate_group_challenge_params()` and `create_group_challenge()`.
- **Roster Locking:**
  - When the challenge start date arrives (`now_local > start_date`), the roster is permanently locked. Unaccepted invitations can no longer be accepted.
  - No new participants may be added to an existing challenge once created.
- **Activation Threshold:**
  - A group challenge activates to `status = 'ACCEPTED'` when at least 3 participants accept (the creator plus at least 2 invitees).
  - If fewer than 3 participants have accepted by challenge start date / `expires_at`, the challenge transitions to `EXPIRED`.

---

## 5. Medal Awarding & Tie-Breaker Rule

- **Medal Policy:**
  - Each completed challenge awards medals only for a unique 1st place (`rank == 1`) provided the participant logged a non-zero score (`final_score > 0`).
- **Tie for First Place:**
  - In the event of a tie for 1st place in a Group Challenge (e.g., two runners both finish with 25.0 km), the challenge concludes in a `DRAW` and NO medal is awarded.
  - Runners finishing below 1st place receive `result = 'LOSS'` and no medal.
  - Participation alone does not earn a medal.
  - If runs are subsequently edited or deleted, `recalibrate_user_challenges_on_run_change()` dynamically re-evaluates ranks and grants or revokes medals as necessary, writing an audit log in `challenge_activity`.

---

## 6. Rollback & Disaster Recovery Procedures

To roll back Migration 016 on PostgreSQL:
```bash
psql $DATABASE_URL -f migrations/016_rollback_group_challenges.sql
```
This script:
1. Drops the added indexes.
2. Removes any group challenge records (`challenge_mode = 'GROUP'`).
3. Restores `NOT NULL` on `opponent_id` and reverts the check constraint.
4. Drops columns `max_participants`, `challenge_mode`, `invitation_status`, and `rank`.
