-- Paz Rav engine tables live in their own schema so the console's `public` tables are
-- never touched. The engine's asyncpg repos (src/paz_rav/store/*) all issue an
-- UNQUALIFIED `CREATE TABLE IF NOT EXISTS`, so the role's default search_path is what
-- routes them into `engine` -- that is what makes this a zero-code-change split.
--
-- NOTE: docker-entrypoint-initdb.d only runs against an EMPTY data directory. On a
-- database that already has data, apply this once by hand:
--   docker compose exec postgres psql -U condor -d condor \
--     -f /docker-entrypoint-initdb.d/10-engine-schema.sql

CREATE SCHEMA IF NOT EXISTS engine;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'paz') THEN
    CREATE ROLE paz LOGIN PASSWORD 'paz';
  END IF;
END $$;

GRANT ALL ON SCHEMA engine TO paz;
ALTER ROLE paz IN DATABASE condor SET search_path = engine, public;

-- Created here as the superuser: store/postgres_case_memory.py issues
-- `CREATE EXTENSION IF NOT EXISTS vector` as `paz`, which cannot create it itself.
-- Landing it in `public` keeps the `vector` type resolvable from paz's search_path.
CREATE EXTENSION IF NOT EXISTS vector;
