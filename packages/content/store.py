"""SQLite CMS repository. Public reads expose published revisions only."""
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile

from packages.config.review import ASSETS, SEED
from packages.content.contracts import (
    Conflict, Forbidden, Invalid, Missing, validate_content, validate_entry,
)

APPLICATION_ID = 0x53414657
SCHEMA_VERSION = 2
TRANSITIONS = {
    ("draft", "submit"): ("editor", "review"),
    ("review", "approve"): ("reviewer", "approved"),
    ("review", "return"): ("reviewer", "draft"),
    ("approved", "return"): ("publisher", "draft"),
    ("approved", "publish"): ("publisher", "published"),
}
TRANSITIONS.update({(state, "archive"): ("publisher", "archived")
                    for state in ("draft", "review", "approved", "published")})
WORKING_SELECT = """
    SELECT e.*, r.title, r.summary, r.body, r.status, r.media, r.blocks,
           (SELECT alt FROM media WHERE 'upload:' || media.id = r.media) AS media_alt
    FROM entries e JOIN revisions r ON r.entry_id = e.id AND r.number = e.working
"""


class CMSConnection(sqlite3.Connection):
    vault = None


def connect(path, read_only=False):
    from packages.security import vault
    mode = "ro" if read_only else "rw"
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode={mode}", uri=True, timeout=5, factory=CMSConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA trusted_schema = OFF")
    if vault.key_path(path).exists():
        db.vault = vault.load(path)
    return db


@contextmanager
def transaction(path, *, write=False):
    with closing(connect(path, read_only=not write)) as db, db:
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db


def audit(db, actor, action, entry_id=None, revision=None, note=""):
    db.execute(
        "INSERT INTO audit(actor, action, entry_id, revision, note) VALUES (?, ?, ?, ?, ?)",
        (actor, action, entry_id, revision, note),
    )


def add_revision(db, entry_id, number, content, actor):
    db.execute(
        """INSERT INTO revisions(entry_id, number, title, summary, body, status, media, blocks, author)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entry_id, number, content["title"], content["summary"], content["body"],
         content["status"], content["media"], content.get("blocks", "{}"), actor),
    )


def check_identity(db):
    if (db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
            or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION):
        raise Invalid("The database needs an explicit CMS migration or is incompatible. Run cms.py check.")


def private_destination(path):
    if path.resolve().is_relative_to(ASSETS.resolve()):
        raise Invalid("Keep review data outside the public asset directory.")
    if path.is_symlink():
        raise Invalid("Use a regular file path for review data.")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)


@contextmanager
def new_database_file(path):
    """Prepare a private file and publish it atomically without replacing an existing file."""
    private_destination(path)
    if path.exists():
        raise Invalid("The destination already exists.")
    with NamedTemporaryFile(prefix=".safwa-", dir=path.parent) as temp:
        temporary = Path(temp.name)
        yield temporary
        try:
            os.link(temporary, path)
        except FileExistsError:
            raise Invalid("The destination already exists.") from None


def initialize(path):
    from packages.security import vault
    private_destination(path)
    if path.exists():
        with transaction(path) as db:
            check_identity(db)
        return
    vault.load(path, create=True)
    with new_database_file(path) as temporary, closing(connect(temporary)) as db, db:
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        db.executescript("BEGIN IMMEDIATE;\n" + schema)
        db.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        for item in json.loads(SEED.read_text(encoding="utf-8")):
            kind, arm, slug = item["kind"], item["arm"], item["slug"]
            validate_entry(kind, arm, slug)
            content = validate_content(item, kind)
            entry_id = db.execute(
                """INSERT INTO entries(arm, kind, slug, state, working, version)
                VALUES (?, ?, ?, 'draft', 1, 1)""",
                (arm, kind, slug),
            ).lastrowid
            add_revision(db, entry_id, 1, content, "institutional-profile")
            audit(db, "institutional-profile", "review seed", entry_id, 1)
        seed_pages(db)
        db.commit()
    with closing(connect(path)) as db:
        db.execute("PRAGMA journal_mode = WAL")


def seed_pages(db):
    from packages.content.page_content import BY_KEY, arm_for, defaults
    for slug, page in BY_KEY.items():
        content = {"title": page["title"].replace(" | The Safwa", ""), "summary": page["description"],
                   "body": "", "status": "page", "media": "",
                   "blocks": json.dumps(defaults(slug), ensure_ascii=False)}
        entry_id = db.execute(
            """INSERT INTO entries(arm, kind, slug, state, working, published, version)
            VALUES (?, 'page', ?, 'published', 1, 1, 1)""", (arm_for(slug), slug)
        ).lastrowid
        add_revision(db, entry_id, 1, content, "approved-public-release")
        audit(db, "approved-public-release", "import approved page", entry_id, 1)


def copy_database(source, destination, *, restore=False, legacy=False):
    if not source.is_file():
        raise Missing("The source database does not exist.")
    with closing(connect(source, read_only=True)) as original:
        if not legacy:
            check_identity(original)
        with new_database_file(destination) as temporary, closing(connect(temporary)) as target:
            original.backup(target)
            if not legacy:
                check_identity(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise Invalid("Database integrity check failed.")
            if target.execute("PRAGMA foreign_key_check").fetchone():
                raise Invalid("Database relationship check failed.")
            with target:
                # Neither backups nor restored instances can re-enable a prior session.
                target.execute("DELETE FROM sessions")
                target.execute("DELETE FROM login_attempts")
                if restore:
                    audit(target, "local-operator", "restore")


def published_entries(db, *, kind, arm=None, slug=None):
    return db.execute(
        """SELECT *, (SELECT alt FROM media WHERE 'upload:' || media.id = public_content.media) AS media_alt FROM public_content
        WHERE kind = ? AND (? IS NULL OR arm = ?) AND (? IS NULL OR slug = ?)
        ORDER BY id""",
        (kind, arm, arm, slug, slug),
    ).fetchall()


def require_scope(user, arm):
    if user["role"] != "admin" and user["arm"] != arm:
        raise Forbidden("This record belongs to another institutional area.")


def work_list(db, user, *, state="", kind="", search="", offset=0, limit=50):
    return db.execute(
        WORKING_SELECT + """ WHERE (? IS NULL OR e.arm = ?)
        AND (? = '' OR e.state = ?) AND (? = '' OR e.kind = ?)
        AND (? = '' OR instr(lower(r.title || ' ' || e.slug), lower(?)) > 0)
        ORDER BY (e.kind = 'page') DESC, e.id DESC LIMIT ? OFFSET ?""",
        (user["arm"], user["arm"], state, state, kind, kind, search, search, limit, offset),
    ).fetchall()


def work_item(db, user, entry_id):
    item = db.execute(WORKING_SELECT + " WHERE e.id = ?", (entry_id,)).fetchone()
    if item is None:
        raise Missing("This record does not exist.")
    require_scope(user, item["arm"])
    return item


def item_history(db, entry_id):
    return db.execute(
        "SELECT * FROM revisions WHERE entry_id = ? ORDER BY number DESC", (entry_id,)
    ).fetchall()


def audit_log(db, user, entry_id=None):
    if entry_id is not None:
        work_item(db, user, entry_id)
        return db.execute(
            "SELECT * FROM audit WHERE entry_id = ? ORDER BY id DESC", (entry_id,)
        ).fetchall()
    if user["role"] != "admin":
        raise Forbidden("Only an administrator can view the system audit log.")
    return db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200").fetchall()


def create(db, user, data):
    if user["role"] != "editor":
        raise Forbidden("An editor must create a draft.")
    kind, slug = data.get("kind", ""), data.get("slug", "")
    if kind == "page":
        raise Forbidden("Edit an existing website page from the workspace.")
    arm = user["arm"]
    validate_entry(kind, arm, slug)
    content = validate_content(data, kind, db=db, arm=arm, slug=slug)
    if db.execute("SELECT id FROM entries WHERE kind = ? AND slug = ?", (kind, slug)).fetchone():
        raise Invalid("That URL name is already in use for this content type.")
    entry_id = db.execute(
        """INSERT INTO entries(arm, kind, slug, state, working, version)
        VALUES (?, ?, ?, 'draft', 1, 1)""", (arm, kind, slug)
    ).lastrowid
    add_revision(db, entry_id, 1, content, user["name"])
    audit(db, user["name"], "create", entry_id, 1)
    return entry_id


def change(db, user, entry_id, data):
    item = work_item(db, user, entry_id)
    if data.get("version") != str(item["version"]):
        raise Conflict("This record changed since you opened it. Reload and review the latest version.")
    action = data.get("action", "")
    if action in {"save", "restore"}:
        if user["role"] != "editor" or item["state"] not in {"draft", "published", "archived"}:
            raise Forbidden("An editor can save a draft outside the review queue.")
        if action == "restore":
            revision = db.execute("SELECT * FROM revisions WHERE entry_id = ? AND number = ?",
                                  (entry_id, data.get("revision", ""))).fetchone()
            if revision is None:
                raise Missing("This revision does not exist.")
            data = dict(revision)
            data.update(json.loads(data["blocks"]))
        content = validate_content(data, item["kind"], db=db, arm=item["arm"], slug=item["slug"])
        number = item["working"] + 1
        add_revision(db, entry_id, number, content, user["name"])
        db.execute(
            "UPDATE entries SET working = ?, state = 'draft', version = version + 1 WHERE id = ?",
            (number, entry_id),
        )
        audit(db, user["name"], action, entry_id, number)
        return
    role, next_state = TRANSITIONS.get((item["state"], action), (None, None))
    if action == "archive" and item["kind"] == "page":
        raise Invalid("Website pages stay available. Publish a revised page instead.")
    if user["role"] != role or (action == "archive" and item["published"] is None):
        raise Forbidden("Your role cannot take that action at this stage.")
    if action == 'approve' and db.execute(
        'SELECT author FROM revisions WHERE entry_id = ? AND number = ?', (entry_id, item['working'])
    ).fetchone()[0] == user['name']:
        raise Forbidden('A different staff member must review the author’s work.')
    note = data.get("note", "").strip()
    if len(note) > 500 or (action in {"return", "archive"} and not note):
        raise Invalid("Give a short reason of up to 500 characters.")
    published = item["published"]
    if action == "publish":
        published = item["working"]
    elif action == "archive":
        published = None
    db.execute(
        "UPDATE entries SET state = ?, published = ?, version = version + 1 WHERE id = ?",
        (next_state, published, entry_id),
    )
    affected = item["published"] if action == "archive" else item["working"]
    audit(db, user["name"], action, entry_id, affected, note)
