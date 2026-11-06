"""Validated, metadata-free images stored in the same SQLite backup as their revisions."""
import hashlib
from io import BytesIO
import secrets
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from packages.content.contracts import Forbidden, Invalid, Missing
from packages.content.store import audit, require_scope

MAX_UPLOAD = 4 * 1024 * 1024
MAX_LIBRARY = 500 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 12_000_000


def upload(db, user, raw, alt):
    if user["role"] != "editor":
        raise Forbidden("Only an editor can add an image.")
    alt = alt.strip()
    if not 1 <= len(alt) <= 240 or any(ord(c) < 32 for c in alt):
        raise Invalid("Describe the image in 1 to 240 characters for readers who cannot see it.")
    if not 1 <= len(raw) <= MAX_UPLOAD:
        raise Invalid("Choose a JPEG or PNG image no larger than 4 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=("JPEG", "PNG")) as source:
                if source.width * source.height > Image.MAX_IMAGE_PIXELS or getattr(source, "n_frames", 1) != 1:
                    raise Invalid("Use a still image of no more than 12 million pixels.")
                source.load()
                image = ImageOps.exif_transpose(source)
                alpha = "A" in image.getbands() or "transparency" in image.info
                image = image.convert("RGBA" if alpha else "RGB")
                image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                output = BytesIO()
                format_name, mime = ("PNG", "image/png") if alpha else ("JPEG", "image/jpeg")
                # A fresh image prevents source metadata being retained by encoders.
                clean = Image.new(image.mode, image.size)
                clean.paste(image)
                clean.save(output, format=format_name, **({"quality": 90} if format_name == "JPEG" else {}))
                data = output.getvalue()
                width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Invalid("The image could not be read safely. Use a valid JPEG or PNG.") from None
    digest = hashlib.sha256(data).hexdigest()
    found = db.execute("SELECT id FROM media WHERE arm = ? AND digest = ? AND alt = ?",
                       (user["arm"], digest, alt)).fetchone()
    if found:
        return found[0]
    if db.execute("SELECT COALESCE(SUM(size), 0) FROM media").fetchone()[0] + len(data) > MAX_LIBRARY:
        raise Invalid("The image library has reached its storage limit. Contact the administrator.")
    identifier = secrets.token_hex(16)
    db.execute("""INSERT INTO media(id, arm, alt, mime, width, height, size, digest, data, author)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
               (identifier, user["arm"], alt, mime, width, height, len(data), digest, data, user["name"]))
    audit(db, user["name"], "upload image", note=identifier)
    return identifier


def library(db, user, *, limit=100, offset=0):
    return db.execute("""SELECT id, arm, alt, mime, width, height, size, author, created_at FROM media
                       WHERE (? IS NULL OR arm = ?) ORDER BY created_at DESC, id LIMIT ? OFFSET ?""",
                      (user["arm"], user["arm"], limit, offset)).fetchall()


def get(db, identifier, *, user=None):
    row = db.execute("SELECT * FROM media WHERE id = ?", (identifier,)).fetchone()
    if row is None:
        raise Missing("This image is unavailable.")
    if user:
        require_scope(user, row["arm"])
    elif not db.execute("SELECT id FROM public_content WHERE media = ?", ("upload:" + identifier,)).fetchone():
        raise Missing("This image is unavailable.")
    return row


def options(db, user):
    return {"upload:" + row["id"]: row["alt"] for row in library(db, user, limit=1000)}
