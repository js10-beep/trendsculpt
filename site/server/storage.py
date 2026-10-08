"""Local SQLite or hosted PostgreSQL storage, with the same private API schema."""

import os
import pathlib
import re
import sqlite3
import ssl
from contextlib import contextmanager
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = pathlib.Path(os.environ.get("TRENDSCULPT_DATA_DIR", str(ROOT / ".data")))
DATABASE = DATA / "app.sqlite"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
STORAGE = "postgresql" if DATABASE_URL else "sqlite"

SCHEMA = """
 CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,recovery TEXT NOT NULL,profile TEXT NOT NULL,created REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,report TEXT NOT NULL,saved INTEGER NOT NULL DEFAULT 0,media BLOB,mime TEXT,created REAL NOT NULL);
 CREATE TABLE IF NOT EXISTS datasets(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,platform TEXT,model BLOB NOT NULL,info TEXT NOT NULL,PRIMARY KEY(user_id,platform));
 CREATE INDEX IF NOT EXISTS own_reports ON reports(user_id,saved,created);
 CREATE TABLE IF NOT EXISTS usage(user_id TEXT REFERENCES users(id) ON DELETE CASCADE,month TEXT,count INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,month));
 CREATE TABLE IF NOT EXISTS attempts(key TEXT,created REAL);
 CREATE INDEX IF NOT EXISTS recent_attempts ON attempts(key,created);
"""


class Record(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return Record(row) if row is not None else None

    def fetchall(self):
        return [Record(row) for row in self.cursor.fetchall()]


class Postgres:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, parameters=()):
        import psycopg

        # Serialize the existing quota transaction across processes/servers.
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            sql = "SELECT pg_advisory_xact_lock(846327101)"
        try:
            return Result(self.connection.execute(sql.replace("?", "%s"), parameters))
        except psycopg.IntegrityError:
            # Preserve the API's existing duplicate-account handling.
            raise sqlite3.IntegrityError(
                "Database constraint rejected this change."
            ) from None


@contextmanager
def db():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        parsed = urlsplit(DATABASE_URL)
        if parsed.scheme not in {"postgres", "postgresql"}:
            raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL.")
        local_test = (
            parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and os.environ.get("TRENDSCULPT_ALLOW_LOCAL_DATABASE") == "true"
        )
        options = (
            {"sslmode": "disable"}
            if local_test
            else {
                "sslmode": "verify-full",
                "sslrootcert": ssl.get_default_verify_paths().cafile or "system",
            }
        )
        try:
            conn = psycopg.connect(
                DATABASE_URL, row_factory=dict_row, connect_timeout=15, **options
            )
        except psycopg.Error:
            raise RuntimeError(
                "Could not connect to hosted storage. Check DATABASE_URL and database availability in server settings."
            ) from None
        adapter = Postgres(conn)
    else:
        conn = sqlite3.connect(DATABASE, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        adapter = conn
    try:
        yield adapter
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize():
    if not DATABASE_URL:
        DATA.mkdir(parents=True, exist_ok=True)
        os.chmod(DATA, 0o700)
    with db() as c:
        if DATABASE_URL:
            c.execute("SELECT pg_advisory_xact_lock(846327102)")
            schema = re.sub(r"\bBLOB\b", "BYTEA", SCHEMA)
            schema = re.sub(r"\bREAL\b", "DOUBLE PRECISION", schema)
            for statement in schema.split(";"):
                if statement.strip():
                    c.execute(statement)
        else:
            c.executescript("PRAGMA journal_mode=WAL;" + SCHEMA)
    if not DATABASE_URL:
        os.chmod(DATABASE, 0o600)
