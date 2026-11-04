CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS am_collab;
CREATE TABLE IF NOT EXISTS am_collab.installation (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), id uuid NOT NULL
);
CREATE TABLE IF NOT EXISTS am_collab.accounts (
    id uuid PRIMARY KEY, name text NOT NULL, upload_prompts boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true, sequence bigint NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS am_collab.credentials (
    id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES am_collab.accounts(id),
    device_id uuid NOT NULL, name text NOT NULL, digest text NOT NULL UNIQUE,
    writable boolean NOT NULL, revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS am_collab.memories (
    user_id uuid NOT NULL REFERENCES am_collab.accounts(id), id uuid NOT NULL,
    project text NOT NULL, kind text NOT NULL CHECK(kind IN ('memory','summary','prompt')),
    revision bigint NOT NULL, deleted boolean NOT NULL, text text,
    device_id uuid NOT NULL, embedding vector(384), updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id,id)
);
CREATE TABLE IF NOT EXISTS am_collab.changes (
    user_id uuid NOT NULL REFERENCES am_collab.accounts(id), sequence bigint NOT NULL,
    op_id uuid NOT NULL, digest text NOT NULL, body jsonb NOT NULL,
    PRIMARY KEY(user_id,sequence), UNIQUE(user_id,op_id)
);
CREATE TABLE IF NOT EXISTS am_collab.teams (
    id uuid PRIMARY KEY, name text NOT NULL
);
CREATE TABLE IF NOT EXISTS am_collab.members (
    team_id uuid NOT NULL REFERENCES am_collab.teams(id),
    user_id uuid NOT NULL REFERENCES am_collab.accounts(id),
    role text NOT NULL CHECK(role IN ('owner','member','viewer')), active boolean NOT NULL DEFAULT true,
    PRIMARY KEY(team_id,user_id)
);
CREATE TABLE IF NOT EXISTS am_collab.projects (
    team_id uuid NOT NULL REFERENCES am_collab.teams(id), id uuid NOT NULL, name text NOT NULL,
    PRIMARY KEY(team_id,id)
);
CREATE TABLE IF NOT EXISTS am_collab.grants (
    team_id uuid NOT NULL, user_id uuid NOT NULL, project_id uuid NOT NULL,
    PRIMARY KEY(team_id,user_id,project_id),
    FOREIGN KEY(team_id,user_id) REFERENCES am_collab.members(team_id,user_id),
    FOREIGN KEY(team_id,project_id) REFERENCES am_collab.projects(team_id,id)
);
CREATE TABLE IF NOT EXISTS am_collab.invites (
    digest text PRIMARY KEY, team_id uuid NOT NULL REFERENCES am_collab.teams(id),
    role text NOT NULL CHECK(role IN ('member','viewer')), projects uuid[] NOT NULL,
    expires_at timestamptz NOT NULL, used_by uuid REFERENCES am_collab.accounts(id)
);
CREATE TABLE IF NOT EXISTS am_collab.sharing (
    team_id uuid NOT NULL, user_id uuid NOT NULL, source_project text NOT NULL, project_id uuid NOT NULL,
    PRIMARY KEY(team_id,user_id,source_project),
    FOREIGN KEY(team_id,user_id) REFERENCES am_collab.members(team_id,user_id),
    FOREIGN KEY(team_id,project_id) REFERENCES am_collab.projects(team_id,id)
);
CREATE TABLE IF NOT EXISTS am_collab.audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id uuid NOT NULL,
    action text NOT NULL, target text NOT NULL, at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memories_project ON am_collab.memories(user_id,project,updated_at);
CREATE INDEX IF NOT EXISTS memories_fts ON am_collab.memories USING gin(to_tsvector('simple',coalesce(text,''))) WHERE NOT deleted;

-- Idempotent migration from the unreleased 0.1 preview. Existing keys remain
-- usable for data access, but only an operator-issued manager may mint keys.
ALTER TABLE am_collab.installation ADD COLUMN IF NOT EXISTS sync_epoch uuid;
ALTER TABLE am_collab.accounts ADD COLUMN IF NOT EXISTS log_hash text NOT NULL DEFAULT repeat('0',64);
ALTER TABLE am_collab.changes ADD COLUMN IF NOT EXISTS chain_hash text;
ALTER TABLE am_collab.credentials ADD COLUMN IF NOT EXISTS manage_keys boolean NOT NULL DEFAULT false;
ALTER TABLE am_collab.credentials ADD COLUMN IF NOT EXISTS parent_id uuid REFERENCES am_collab.credentials(id);
ALTER TABLE am_collab.credentials ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE am_collab.memories ADD COLUMN IF NOT EXISTS session_id text;
ALTER TABLE am_collab.memories ADD COLUMN IF NOT EXISTS source_id text;
