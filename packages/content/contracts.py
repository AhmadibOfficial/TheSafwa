"""Content fields and the editorial contract shared by the applications."""
import re

from packages.config.review import MEDIA

ARMS = {"parent": "The Safwa", "institute": "Safwa Institute", "studios": "Safwa Studios"}
KINDS = {"activity": "Learning activity", "project": "Project", "article": "Journal entry",
         "opportunity": "Way to contribute", "page": "Website page"}
ALLOWED_ARMS = {
    "activity": {"institute"}, "project": {"parent", "studios"},
    "article": set(ARMS), "opportunity": set(ARMS),
    "page": set(ARMS),
}
STATUSES = {
    "activity": {"ongoing": "Ongoing", "previous": "Previous programmes", "planned": "Planned"},
    "project": {"ongoing": "Ongoing", "development": "In development",
                "preparation": "In preparation", "planned": "Planned"},
    "article": {"note": "Institutional note"},
    "opportunity": {"enquiry": "Enquiries welcome"},
    "page": {"page": "Website page"},
}
ROUTES = {"activity": "/institute/learning/", "project": "/work/",
          "article": "/journal/", "opportunity": "/opportunities/"}
EDITABLE = ("title", "summary", "body", "status", "media")


class Invalid(ValueError):
    pass


class Forbidden(PermissionError):
    pass


class Missing(LookupError):
    pass


class Conflict(RuntimeError):
    pass


def validate_content(data, kind, *, db=None, arm=None, slug=None):
    import json
    from packages.content.page_content import BY_KEY, defaults
    values = {key: data.get(key, "").strip() for key in EDITABLE}
    if kind == "page":
        if slug not in BY_KEY:
            raise Invalid("This website page is unavailable.")
        fields = defaults(slug)
        blocks = {key: data.get(key, "").strip() for key in fields}
        if any(not value or len(value) > 3000 or any(ord(c) < 32 and c not in '\n\r\t' for c in value)
               for value in blocks.values()):
            raise Invalid("Complete each page text field using up to 3,000 characters.")
        values.update(body="", status="page", media="", blocks=json.dumps(blocks, ensure_ascii=False))
    else:
        values["blocks"] = "{}"
    for key, label, limit in (("title", "Title", 100), ("summary", "Summary", 280),
                              ("body", "Body", 8000)):
        if key == "body" and kind == "page":
            continue
        if not 1 <= len(values[key]) <= limit:
            raise Invalid(f"{label} must contain between 1 and {limit} characters.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in values[key]):
            raise Invalid(f"{label} contains an unsupported character.")
    if values["status"] not in STATUSES[kind]:
        raise Invalid("Choose a status for this content type.")
    if values["media"] not in MEDIA:
        match = re.fullmatch(r"upload:([0-9a-f]{32})", values["media"])
        if not match or db is None or not db.execute(
            "SELECT id FROM media WHERE id = ? AND arm = ?", (match[1], arm)
        ).fetchone():
            raise Invalid("Choose an image from your institutional area.")
    return values


def validate_entry(kind, arm, slug):
    if kind not in ALLOWED_ARMS or arm not in ALLOWED_ARMS[kind]:
        raise Invalid("Choose a content type supported by this institutional area.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 80:
        raise Invalid("Use a short URL name with lowercase letters, digits and hyphens.")
