-- migrations/009_drop_user_pets.sql
--
-- Pace Pet has been removed from RunRush. user_pets was the only Pace Pet
-- table (no other table references it); its index unique_active_pet is
-- dropped with it. For manual application against an existing database —
-- init_db() no longer creates the table on fresh installs.
--
-- Irreversible: this deletes every user's pet data.

DROP TABLE IF EXISTS user_pets;
