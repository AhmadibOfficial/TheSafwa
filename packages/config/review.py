"""Defaults shared by the SQLite CMS and its loopback review server."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "dist"
PRIVATE = ROOT / "private"
DATABASE = PRIVATE / "review.sqlite3"
SEED = Path(__file__).with_name("institutional-content.json")

PORT = 4173
SESSION_SECONDS = 4 * 60 * 60
LOGIN_WINDOW = 10 * 60
MEDIA = {
    "": ("No image", ""),
    "the-safwa-logo-hd.jpg": ("The Safwa", "The Safwa logo"),
    "institute-logo-hd.jpg": ("Institute identity", "Safwa Institute logo"),
    "white-horse-hd.jpg": ("Parent brand photograph", "A white horse in a finely detailed bridle"),
    "studios-brand-hd.jpg": ("Studios identity", "Safwa Studios logo"),
}
