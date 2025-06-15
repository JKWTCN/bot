PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- 表：gambling
CREATE TABLE IF NOT EXISTS gambling (
    user_id INTEGER,
    times   INTEGER
);


-- 表：group_message
CREATE TABLE IF NOT EXISTS group_message (
    time            INTEGER,
    user_id         INTEGER,
    sender_nickname TEXT,
    raw_message     TEXT,
    group_id        INTEGER,
    self_id         INTEGER,
    sub_type        TEXT,
    message_id      INTEGER
);


-- 表：record
CREATE TABLE IF NOT EXISTS record (
    record_name TEXT,
    record_time INTEGER
);


-- 表：russian_pve
CREATE TABLE IF NOT EXISTS russian_pve (
    user_id INTEGER PRIMARY KEY,
    shots   INTEGER
);


-- 表：unwelcome
CREATE TABLE IF NOT EXISTS unwelcome (
    user_id  INTEGER,
    time     INTEGER,
    group_id INTEGER
);


-- 表：user_point
CREATE TABLE IF NOT EXISTS user_point (
    user_id INTEGER PRIMARY KEY,
    point   INTEGER,
    time    NUMERIC
);


-- 表：vcode
CREATE TABLE IF NOT EXISTS vcode (
    user_id  INTEGER,
    group_id INTEGER,
    text     TEXT,
    times    INTEGER,
    time     INTEGER
);


COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
