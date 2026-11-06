"""Individual staff accounts, encrypted MFA, recovery and server-side sessions."""
import base64
import hashlib
import hmac
import re
import secrets
import time
from urllib.parse import quote, urlencode

from packages.config.review import LOGIN_WINDOW, SESSION_SECONDS
from packages.content.contracts import ARMS, Invalid, Missing
from packages.content.store import audit
from packages.security.vault import decrypt

ROLES = {"editor": "Editor", "reviewer": "Reviewer", "publisher": "Publisher",
         "admin": "Administrator"}
PASSWORD_ITERATIONS = 600_000
MAX_FAILURES_PER_ACCOUNT = 5
MAX_FAILURES_TOTAL = 30


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).digest()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def totp(key, counter, digits=6):
    """RFC 6238 time counter with the default SHA-1 interoperable profile."""
    mac = hmac.digest(key, counter.to_bytes(8, "big"), "sha1")
    offset = mac[-1] & 15
    number = int.from_bytes(mac[offset:offset + 4], "big") & 0x7fffffff
    return f"{number % (10 ** digits):0{digits}d}"


def valid_name(name):
    return bool(re.fullmatch(r"[a-z][a-z0-9._-]{2,31}", name))


def create_user(db, name, role, arm, password, *, actor="local-operator", must_change=False):
    if not valid_name(name):
        raise Invalid("Use 3 to 32 lowercase characters, beginning with a letter.")
    if role not in ROLES or (arm is not None if role == "admin" else arm not in ARMS):
        raise Invalid("Select a role and, for editorial staff, one institutional area.")
    if not 14 <= len(password) <= 256:
        raise Invalid("Use a passphrase of 14 to 256 characters.")
    if db.execute("SELECT name FROM users WHERE name = ?", (name,)).fetchone():
        raise Invalid("That user name is already in use.")
    salt = secrets.token_bytes(16)
    key = secrets.token_bytes(20)
    db.execute(
        "INSERT INTO users(name, role, arm, password_hash, salt, otp_key, must_change) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, role, arm, password_hash(password, salt), salt, db.vault.encrypt(key), int(must_change)),
    )
    audit(db, actor, "create user", note=name)
    secret = base64.b32encode(key).decode("ascii")
    return "otpauth://totp/" + quote(f"The Safwa:{name}", safe="") + "?" + urlencode(
        {"secret": secret, "issuer": "The Safwa"}
    )


def revoke_user(db, name, *, actor="local-operator"):
    user = db.execute("SELECT role FROM users WHERE name = ? AND active = 1", (name,)).fetchone()
    if user and user["role"] == "admin" and db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
    ).fetchone()[0] <= 1:
        raise Invalid("Keep at least one active administrator.")
    if not db.execute("UPDATE users SET active = 0 WHERE name = ? AND active = 1", (name,)).rowcount:
        raise Missing("That active account does not exist.")
    db.execute("DELETE FROM sessions WHERE name = ?", (name,))
    audit(db, actor, "revoke user", note=name)


def recovery_codes(db, name, *, actor):
    codes = [secrets.token_hex(8).upper() for _ in range(8)]
    db.execute("DELETE FROM recovery_codes WHERE name = ?", (name,))
    db.executemany("INSERT INTO recovery_codes VALUES (?, ?)",
                   [(name, digest("recovery:" + name + ":" + code)) for code in codes])
    audit(db, actor, "replace recovery codes", note=name)
    return codes


def change_password(db, user, current, new):
    row = db.execute("SELECT * FROM users WHERE name = ?", (user["name"],)).fetchone()
    if not hmac.compare_digest(password_hash(current, row["salt"]), row["password_hash"]):
        raise Invalid("The current passphrase is incorrect.")
    if not 14 <= len(new) <= 256 or new == current:
        raise Invalid("Choose a different passphrase of 14 to 256 characters.")
    salt = secrets.token_bytes(16)
    db.execute("UPDATE users SET salt = ?, password_hash = ?, must_change = 0 WHERE name = ?",
               (salt, password_hash(new, salt), user["name"]))
    db.execute("DELETE FROM sessions WHERE name = ?", (user["name"],))
    audit(db, user["name"], "change passphrase")


def update_staff(db, actor, name, role, arm, active):
    if actor["role"] != "admin":
        from packages.content.contracts import Forbidden
        raise Forbidden("Only an administrator can manage staff.")
    row = db.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise Missing("That staff account does not exist.")
    if name == actor["name"]:
        raise Invalid("Ask another administrator to change your own permissions.")
    if role not in ROLES or (arm is not None if role == "admin" else arm not in ARMS):
        raise Invalid("Choose a valid role and institutional area.")
    if row["active"] and row["role"] == "admin" and (role != "admin" or not active) and db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
    ).fetchone()[0] <= 1:
        raise Invalid("Keep at least one active administrator.")
    db.execute("UPDATE users SET role = ?, arm = ?, active = ? WHERE name = ?", (role, arm, int(active), name))
    db.execute("DELETE FROM sessions WHERE name = ?", (name,))
    audit(db, actor["name"], "change staff permissions", note=name)


def reset_access(db, name, password):
    if not 14 <= len(password) <= 256:
        raise Invalid('Use a passphrase of 14 to 256 characters.')
    if not db.execute('SELECT name FROM users WHERE name = ?', (name,)).fetchone():
        raise Missing('That staff account does not exist.')
    salt, key = secrets.token_bytes(16), secrets.token_bytes(20)
    db.execute('UPDATE users SET password_hash = ?, salt = ?, otp_key = ?, otp_counter = -1, must_change = 1 WHERE name = ?',
               (password_hash(password, salt), salt, db.vault.encrypt(key), name))
    db.execute('DELETE FROM sessions WHERE name = ?', (name,))
    db.execute('DELETE FROM recovery_codes WHERE name = ?', (name,))
    audit(db, 'local-operator', 'reset staff access', note=name)
    return 'otpauth://totp/' + quote(f'The Safwa:{name}', safe='') + '?' + urlencode(
        {'secret': base64.b32encode(key).decode('ascii'), 'issuer': 'The Safwa'})


def sign_in(db, name, password, code, *, now=None):
    now = int(time.time()) if now is None else now
    db.execute("DELETE FROM login_attempts WHERE attempted <= ?", (now - LOGIN_WINDOW,))
    db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
    identifier = digest(name)
    total, matching = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(account_hash = ?), 0) FROM login_attempts", (identifier,)
    ).fetchone()
    if total >= MAX_FAILURES_TOTAL or matching >= MAX_FAILURES_PER_ACCOUNT:
        return None, True
    user = db.execute("SELECT * FROM users WHERE name = ? AND active = 1", (name,)).fetchone()
    salt = user["salt"] if user else b"\0" * 16
    expected = user["password_hash"] if user else b"\0" * 32
    hashed = password_hash(password, salt)
    counter = now // 30
    valid_factor = False
    if user and hmac.compare_digest(hashed, expected) and re.fullmatch(r"[A-Fa-f0-9]{16}", code):
        valid_factor = bool(db.execute("DELETE FROM recovery_codes WHERE name = ? AND code_hash = ?",
                          (name, digest("recovery:" + name + ":" + code.upper()))).rowcount)
        if valid_factor:
            audit(db, name, "use recovery code")
    if user and hmac.compare_digest(hashed, expected) and re.fullmatch(r"[0-9]{6}", code):
        key = decrypt(db, user["otp_key"])
        for step in (counter, counter - 1):
            if step > user["otp_counter"] and step >= 0 and hmac.compare_digest(totp(key, step), code):
                db.execute("UPDATE users SET otp_counter = ? WHERE name = ?", (step, name))
                valid_factor = True
                break
    if valid_factor:
        token = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)",
                   (digest(token), name, secrets.token_urlsafe(32), now + SESSION_SECONDS))
        db.execute("DELETE FROM login_attempts WHERE account_hash = ?", (identifier,))
        audit(db, name, "sign in")
        return token, False
    db.execute("INSERT INTO login_attempts VALUES (?, ?)", (identifier, now))
    return None, False


def session(db, token, *, now=None):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return None
    now = int(time.time()) if now is None else now
    return db.execute(
        """SELECT u.name, u.role, u.arm, u.must_change, s.csrf, s.token_hash FROM sessions s
        JOIN users u ON u.name = s.name
        WHERE s.token_hash = ? AND s.expires > ? AND u.active = 1""", (digest(token), now)
    ).fetchone()


def sign_out(db, user):
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (user["token_hash"],))
    audit(db, user["name"], "sign out")


def matches_token(expected, supplied):
    return bool(expected and re.fullmatch(r"[A-Za-z0-9_-]{43}", supplied)
                and hmac.compare_digest(expected, supplied))
