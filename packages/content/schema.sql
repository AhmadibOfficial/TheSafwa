CREATE TABLE users (
    name TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('editor', 'reviewer', 'publisher', 'admin')),
    arm TEXT CHECK (arm IN ('parent', 'institute', 'studios')),
    password_hash BLOB NOT NULL,
    salt BLOB NOT NULL,
    otp_key BLOB NOT NULL,
    otp_counter INTEGER NOT NULL DEFAULT -1,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change INTEGER NOT NULL DEFAULT 0 CHECK (must_change IN (0, 1)),
    CHECK ((role = 'admin' AND arm IS NULL) OR (role <> 'admin' AND arm IS NOT NULL))
);
CREATE TABLE sessions (
    token_hash BLOB PRIMARY KEY,
    name TEXT NOT NULL REFERENCES users(name),
    csrf TEXT NOT NULL,
    expires INTEGER NOT NULL
);
CREATE TABLE login_attempts (account_hash BLOB NOT NULL, attempted INTEGER NOT NULL);
CREATE INDEX attempts_by_time ON login_attempts(attempted);
CREATE TABLE recovery_codes (
    name TEXT NOT NULL REFERENCES users(name),
    code_hash BLOB NOT NULL UNIQUE,
    PRIMARY KEY(name, code_hash)
);
CREATE TABLE media (
    id TEXT PRIMARY KEY,
    arm TEXT NOT NULL CHECK (arm IN ('parent', 'institute', 'studios')),
    alt TEXT NOT NULL,
    mime TEXT NOT NULL CHECK (mime IN ('image/jpeg', 'image/png')),
    width INTEGER NOT NULL CHECK (width > 0),
    height INTEGER NOT NULL CHECK (height > 0),
    size INTEGER NOT NULL CHECK (size > 0),
    digest TEXT NOT NULL,
    data BLOB NOT NULL,
    author TEXT NOT NULL REFERENCES users(name),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(arm, digest, alt)
);
CREATE TABLE entries (
    id INTEGER PRIMARY KEY,
    arm TEXT NOT NULL CHECK (arm IN ('parent', 'institute', 'studios')),
    kind TEXT NOT NULL CHECK (kind IN ('activity', 'project', 'article', 'opportunity', 'page')),
    slug TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('draft', 'review', 'approved', 'published', 'archived')),
    working INTEGER NOT NULL CHECK (working > 0),
    published INTEGER,
    version INTEGER NOT NULL CHECK (version > 0),
    UNIQUE(kind, slug),
    FOREIGN KEY(id, working) REFERENCES revisions(entry_id, number) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(id, published) REFERENCES revisions(entry_id, number) DEFERRABLE INITIALLY DEFERRED,
    CHECK (state <> 'published' OR (published IS NOT NULL AND working = published)),
    CHECK (state <> 'archived' OR published IS NULL)
);
CREATE TABLE revisions (
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    media TEXT NOT NULL,
    blocks TEXT NOT NULL DEFAULT '{}',
    author TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(entry_id, number)
);
CREATE TABLE audit (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER REFERENCES entries(id),
    revision INTEGER,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(entry_id, revision) REFERENCES revisions(entry_id, number)
);
CREATE INDEX audit_by_entry ON audit(entry_id, id);
CREATE VIEW public_content AS
SELECT e.id, e.kind, e.arm, e.slug, r.title, r.summary, r.body, r.status, r.media, r.blocks
FROM entries e JOIN revisions r ON r.entry_id = e.id AND r.number = e.published;
