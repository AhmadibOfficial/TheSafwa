"""Fernet encryption for authenticator secrets; key remains outside the database."""
import os
from pathlib import Path
import stat

from cryptography.fernet import Fernet, InvalidToken

from packages.content.contracts import Invalid


def key_path(database):
    return Path(database).parent / "cms.key"


def load(database, *, create=False):
    path = key_path(database)
    if create and not path.exists():
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(Fernet.generate_key())
    if not path.is_file() or path.is_symlink():
        raise Invalid("The CMS encryption key is missing. Restore cms.key to the private data directory.")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise Invalid("The CMS encryption key must be readable only by its owner (chmod 600).")
    try:
        return Fernet(path.read_bytes().strip())
    except ValueError:
        raise Invalid("The CMS encryption key is invalid.") from None


def decrypt(db, value):
    try:
        return db.vault.decrypt(value)
    except InvalidToken:
        raise Invalid("The database and CMS encryption key do not match.") from None
