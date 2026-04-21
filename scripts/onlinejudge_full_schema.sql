-- OnlineJudge PostgreSQL schema (database + core tables)
-- This file is standalone SQL intended to be run with psql.
-- Example:
--   psql -h 127.0.0.1 -p 5432 -U postgres -f scripts/onlinejudge_full_schema.sql

-- 1) Role and database
DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'onlinejudge'
    ) THEN
        CREATE ROLE onlinejudge LOGIN PASSWORD 'onlinejudge';
    END IF;
END
$$;

SELECT 'CREATE DATABASE onlinejudge OWNER onlinejudge ENCODING ''UTF8'''
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'onlinejudge'
)\gexec

GRANT ALL PRIVILEGES ON DATABASE onlinejudge TO onlinejudge;

\connect onlinejudge

-- 2) Core app tables

CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    password TEXT NOT NULL,
    last_login TIMESTAMPTZ NULL,
    username TEXT NOT NULL UNIQUE,
    email TEXT NULL,
    create_time TIMESTAMPTZ NULL,
    admin_type TEXT NOT NULL DEFAULT 'Regular User',
    problem_permission TEXT NOT NULL DEFAULT 'None',
    reset_password_token TEXT NULL,
    reset_password_token_expire_time TIMESTAMPTZ NULL,
    auth_token TEXT NULL,
    two_factor_auth BOOLEAN NOT NULL DEFAULT FALSE,
    tfa_token TEXT NULL,
    session_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    open_api BOOLEAN NOT NULL DEFAULT FALSE,
    open_api_appkey TEXT NULL,
    is_disabled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_profile (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES "user"(id) ON DELETE CASCADE,
    acm_problems_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    oi_problems_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    real_name TEXT NULL,
    avatar TEXT NOT NULL DEFAULT '/public/avatar/default.png',
    blog VARCHAR(200) NULL,
    mood TEXT NULL,
    github TEXT NULL,
    school TEXT NULL,
    major TEXT NULL,
    language VARCHAR(32) NULL,
    accepted_number INTEGER NOT NULL DEFAULT 0,
    total_score BIGINT NOT NULL DEFAULT 0,
    submission_number INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS announcement (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    last_update_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    visible BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS contest (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    real_time_rank BOOLEAN NOT NULL,
    password TEXT NULL,
    rule_type TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_update_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    allowed_ip_ranges JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS contest_announcement (
    id SERIAL PRIMARY KEY,
    contest_id INTEGER NOT NULL REFERENCES contest(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_by_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS acm_contest_rank (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    contest_id INTEGER NOT NULL REFERENCES contest(id) ON DELETE CASCADE,
    submission_number INTEGER NOT NULL DEFAULT 0,
    accepted_number INTEGER NOT NULL DEFAULT 0,
    total_time INTEGER NOT NULL DEFAULT 0,
    submission_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT acm_contest_rank_user_contest_uniq UNIQUE (user_id, contest_id)
);

CREATE TABLE IF NOT EXISTS oi_contest_rank (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    contest_id INTEGER NOT NULL REFERENCES contest(id) ON DELETE CASCADE,
    submission_number INTEGER NOT NULL DEFAULT 0,
    total_score INTEGER NOT NULL DEFAULT 0,
    submission_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT oi_contest_rank_user_contest_uniq UNIQUE (user_id, contest_id)
);

CREATE TABLE IF NOT EXISTS problem_tag (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS problem (
    id SERIAL PRIMARY KEY,
    _id TEXT NOT NULL,
    contest_id INTEGER NULL REFERENCES contest(id) ON DELETE CASCADE,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    input_description TEXT NOT NULL,
    output_description TEXT NOT NULL,
    samples JSONB NOT NULL,
    test_case_id TEXT NOT NULL,
    test_case_score JSONB NOT NULL,
    hint TEXT NULL,
    languages JSONB NOT NULL,
    template JSONB NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_update_time TIMESTAMPTZ NULL,
    created_by_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    time_limit INTEGER NOT NULL,
    memory_limit INTEGER NOT NULL,
    io_mode JSONB NOT NULL DEFAULT '{"io_mode":"Standard IO","input":"input.txt","output":"output.txt"}'::jsonb,
    spj BOOLEAN NOT NULL DEFAULT FALSE,
    spj_language TEXT NULL,
    spj_code TEXT NULL,
    spj_version TEXT NULL,
    spj_compile_ok BOOLEAN NOT NULL DEFAULT FALSE,
    rule_type TEXT NOT NULL,
    visible BOOLEAN NOT NULL DEFAULT TRUE,
    difficulty TEXT NOT NULL,
    source TEXT NULL,
    total_score INTEGER NOT NULL DEFAULT 0,
    submission_number BIGINT NOT NULL DEFAULT 0,
    accepted_number BIGINT NOT NULL DEFAULT 0,
    statistic_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    share_submission BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT problem_display_contest_uniq UNIQUE (_id, contest_id)
);

CREATE INDEX IF NOT EXISTS problem_display_id_idx ON problem(_id);

CREATE TABLE IF NOT EXISTS problem_problem_tags (
    id SERIAL PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES problem(id) ON DELETE CASCADE,
    problemtag_id INTEGER NOT NULL REFERENCES problem_tag(id) ON DELETE CASCADE,
    CONSTRAINT problem_problem_tags_unique UNIQUE (problem_id, problemtag_id)
);

CREATE TABLE IF NOT EXISTS submission (
    id TEXT PRIMARY KEY,
    contest_id INTEGER NULL REFERENCES contest(id) ON DELETE CASCADE,
    problem_id INTEGER NOT NULL REFERENCES problem(id) ON DELETE CASCADE,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    code TEXT NOT NULL,
    result INTEGER NOT NULL DEFAULT 6,
    info JSONB NOT NULL DEFAULT '{}'::jsonb,
    language TEXT NOT NULL,
    shared BOOLEAN NOT NULL DEFAULT FALSE,
    statistic_info JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip TEXT NULL
);

CREATE INDEX IF NOT EXISTS submission_user_id_idx ON submission(user_id);
CREATE INDEX IF NOT EXISTS submission_result_idx ON submission(result);

CREATE TABLE IF NOT EXISTS judge_server (
    id SERIAL PRIMARY KEY,
    hostname TEXT NOT NULL,
    ip TEXT NULL,
    judger_version TEXT NOT NULL,
    cpu_core INTEGER NOT NULL,
    memory_usage DOUBLE PRECISION NOT NULL,
    cpu_usage DOUBLE PRECISION NOT NULL,
    last_heartbeat TIMESTAMPTZ NOT NULL,
    create_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    task_number INTEGER NOT NULL DEFAULT 0,
    service_url TEXT NULL,
    is_disabled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS options_sysoptions (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS options_sysoptions_key_idx ON options_sysoptions(key);

-- 3) Minimal Django framework tables usually needed by the app
CREATE TABLE IF NOT EXISTS django_migrations (
    id SERIAL PRIMARY KEY,
    app VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    applied TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS django_content_type (
    id SERIAL PRIMARY KEY,
    app_label VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    CONSTRAINT django_content_type_app_model_uniq UNIQUE (app_label, model)
);

CREATE TABLE IF NOT EXISTS auth_permission (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    content_type_id INTEGER NOT NULL REFERENCES django_content_type(id) ON DELETE CASCADE,
    codename VARCHAR(100) NOT NULL,
    CONSTRAINT auth_permission_content_codename_uniq UNIQUE (content_type_id, codename)
);

CREATE TABLE IF NOT EXISTS django_session (
    session_key VARCHAR(40) PRIMARY KEY,
    session_data TEXT NOT NULL,
    expire_date TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS django_session_expire_date_idx ON django_session(expire_date);

-- End of schema
