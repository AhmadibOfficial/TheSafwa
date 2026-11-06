"""Explicit, offline v1-to-v2 migration. No schema changes occur during server startup."""
from contextlib import closing
from pathlib import Path
import sqlite3

from packages.content import store
from packages.content.contracts import Invalid
from packages.security import vault


def statements(source):
    pending = ""
    for line in source.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            yield pending
            pending = ""
    if pending.strip():
        raise Invalid("Incomplete migration SQL.")


def migrate(path, backup):
    with closing(store.connect(path)) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        identity = db.execute("PRAGMA application_id").fetchone()[0]
        if identity != store.APPLICATION_ID or version != 1:
            raise Invalid("Migration requires a Safwa version 1 database. Version 2 needs no migration.")
    store.copy_database(path, backup, legacy=True)
    cipher = vault.load(path, create=True)
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    with closing(store.connect(path)) as db:
        # Foreign keys are checked explicitly before the single atomic commit.
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("BEGIN EXCLUSIVE")
        try:
            db.execute("DROP VIEW public_content")
            create_entries = next(s for s in statements(schema) if s.lstrip().startswith("CREATE TABLE entries"))
            db.execute(create_entries.replace("CREATE TABLE entries (", "CREATE TABLE entries_v2 (", 1))
            db.execute("INSERT INTO entries_v2 SELECT * FROM entries")
            db.execute("DROP TABLE entries")
            db.execute("ALTER TABLE entries_v2 RENAME TO entries")
            db.execute("ALTER TABLE revisions ADD COLUMN blocks TEXT NOT NULL DEFAULT '{}'")
            db.execute("ALTER TABLE users ADD COLUMN must_change INTEGER NOT NULL DEFAULT 0 CHECK (must_change IN (0, 1))")
            for statement in statements(schema):
                if statement.lstrip().startswith(("CREATE TABLE media", "CREATE TABLE recovery_codes", "CREATE VIEW public_content")):
                    db.execute(statement)
            for row in db.execute("SELECT name, otp_key FROM users").fetchall():
                db.execute("UPDATE users SET otp_key = ? WHERE name = ?", (cipher.encrypt(row["otp_key"]), row["name"]))
            db.execute("DELETE FROM sessions")
            db.execute("DELETE FROM login_attempts")
            store.seed_pages(db)
            store.audit(db, "local-operator", "migrate schema", note="Version 1 to version 2")
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise Invalid("The migrated database failed relationship checks.")
            db.execute(f"PRAGMA user_version = {store.SCHEMA_VERSION}")
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
