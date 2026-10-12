"""Database access layer for AI-resume_matcher.

Supports TWO backends, switchable in config.py via DB_BACKEND:
  * "mysql"  -> your device's MySQL server (database resume_matcher1)  [default]
  * "sqlite" -> a single portable file data/resume_matcher.db

All helper functions (query / query_one / execute / log) accept the SAME
SQL written with '?' placeholders; this module translates to '%s' for MySQL.
"""
import os
import re
import sqlite3
from contextlib import contextmanager

import config

MYSQL = config.DB_BACKEND == "mysql"

if MYSQL:
    import pymysql
    import pymysql.cursors

# --------------------------------------------------------------------- #
#  Placeholder + dialect translation
# --------------------------------------------------------------------- #
_INSERT_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE", re.IGNORECASE)
_INSERT_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE", re.IGNORECASE)
_DATETIME_NOW = re.compile(r"datetime\('now'\)", re.IGNORECASE)


def _translate(sql):
    """Turn SQLite-flavoured SQL into MySQL-flavoured SQL."""
    if not MYSQL:
        return sql
    sql = _INSERT_IGNORE.sub("INSERT IGNORE", sql)
    sql = _INSERT_REPLACE.sub("REPLACE", sql)
    sql = _DATETIME_NOW.sub("NOW()", sql)
    return sql.replace("?", "%s")


@contextmanager
def get_conn():
    if MYSQL:
        conn = pymysql.connect(
            host=config.MYSQL_HOST, port=config.MYSQL_PORT,
            user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, autocommit=False)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


# --------------------------------------------------------------------- #
#  Schema init
# --------------------------------------------------------------------- #
def init_db(reset: bool = False):
    """Create the schema (optionally wipe existing data)."""
    if MYSQL:
        with get_conn() as conn:
            cur = conn.cursor()
            need = reset
            if not reset:
                cur.execute("SHOW TABLES LIKE 'users'")
                need = cur.fetchone() is None
            if need:
                _run_mysql_schema(conn)
        return

    with get_conn() as conn:
        if reset:
            for v in ("v_match_summary", "v_skill_demand", "v_top_candidates",
                      "v_applications"):
                conn.execute(f"DROP VIEW IF EXISTS {v}")
            for t in ("applications", "match_skill_details", "match_results",
                      "job_skills", "resume_files", "resume_skills", "resumes",
                      "job_postings", "skills", "candidates", "companies",
                      "users", "activity_log", "email_log"):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
        with open(config.SCHEMA_PATH, "r", encoding="utf-8") as fh:
            conn.executescript(fh.read())


def _run_mysql_schema(conn):
    """Execute mysql/schema_mysql.sql (drops + recreates all objects)."""
    path = os.path.join(config.BASE_DIR, "mysql", "schema_mysql.sql")
    with open(path, "r", encoding="utf-8") as fh:
        script = fh.read()
    # strip full-line comments
    script = "\n".join(ln for ln in script.splitlines()
                       if not ln.strip().startswith("--"))
    cur = conn.cursor()
    for st in script.split(";"):
        st = st.strip()
        if not st or st.upper().startswith(("USE ", "CREATE DATABASE")):
            continue
        cur.execute(st)


# --------------------------------------------------------------------- #
#  Query helpers  (work for both backends)
# --------------------------------------------------------------------- #
def query(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_translate(sql), params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(_translate(sql), params)
        return cur.lastrowid


def log(event_type, message, user_id=None):
    execute(
        "INSERT INTO activity_log (user_id, event_type, message) VALUES (?, ?, ?)",
        (user_id, event_type, message),
    )


# --------------------------------------------------------------------- #
#  Schema introspection (used by the SQL report tab)
# --------------------------------------------------------------------- #
def list_tables():
    if MYSQL:
        return [r["name"] for r in query(
            "SELECT TABLE_NAME AS name FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' "
            "ORDER BY TABLE_NAME")]
    return [r["name"] for r in query(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def list_views():
    if MYSQL:
        return [r["name"] for r in query(
            "SELECT TABLE_NAME AS name FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='VIEW' "
            "ORDER BY TABLE_NAME")]
    return [r["name"] for r in query(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]


def table_columns(table):
    if MYSQL:
        rows = query(
            "SELECT COLUMN_NAME AS name, DATA_TYPE AS type "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME=? ORDER BY ORDINAL_POSITION", (table,))
        return rows
    return [{"name": r["name"], "type": r["type"]}
            for r in query(f"PRAGMA table_info({table})")]


# --------------------------------------------------------------------- #
#  Skill extraction used while inserting a resume / job
# --------------------------------------------------------------------- #
def all_skill_terms():
    rows = query("SELECT skill_id, name, aliases FROM skills")
    terms = {}
    for r in rows:
        aliases = [a for a in (r["aliases"] or "").split("|") if a]
        terms[r["skill_id"]] = (r["name"], aliases)
    return terms


def extract_skill_ids(text):
    """Find skill ids mentioned in free text (word-boundary safe)."""
    text_low = " " + re.sub(r"[^a-z0-9+#./ ]", " ", text.lower()) + " "
    found = {}
    for skill_id, (name, aliases) in all_skill_terms().items():
        count = 0
        for term in [name] + aliases:
            term = term.lower()
            pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
            count += len(re.findall(pattern, text_low))
        if count:
            found[skill_id] = count
    return found
