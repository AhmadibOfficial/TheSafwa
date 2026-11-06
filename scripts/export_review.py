#!/usr/bin/env python3
"""Export the approved institutional review baseline for a private static preview."""
import argparse
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from shutil import copyfile
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.parent.server import ALIASES, ASSET_PATHS, public_page
from packages.config.review import ASSETS
from packages.content.store import initialize, transaction
from packages.ui.pages import heading, shell

ROUTES = ("/", "/about", "/contact", "/institute", "/journal", "/opportunities",
          "/portfolio", "/studios", "/studios/quran")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a" and "href" in values:
            self.hrefs.append(values["href"])


def export(destination, archive):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose a new, empty output directory.")
    destination.mkdir(parents=True, exist_ok=True)
    for path in ASSET_PATHS:
        target = destination / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ASSETS / path.lstrip("/"), target)
    copyfile(archive, destination / "Safwa-System-Review.zip")
    static = {route: route + ".html" if route != "/" else "/" for route in ROUTES}

    def rewrite(match):
        parts = urlsplit(match[1])
        key = ALIASES.get(parts.path, parts.path)
        if parts.scheme or parts.netloc or key not in static:
            return match[0]
        suffix = ("?" + parts.query if parts.query else "") + ("#" + parts.fragment if parts.fragment else "")
        return f'href="{static[key]}{suffix}"'

    def write(filename, html):
        html = re.sub(r'href="([^"]+)"', rewrite, html)
        target = destination / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")

    with TemporaryDirectory(prefix="safwa-editorial-baseline-") as data:
        database = Path(data) / "review.sqlite3"
        initialize(database)
        with transaction(database) as db:
            for route in ROUTES:
                name = "index.html" if route == "/" else static[route].lstrip("/")
                write(name, public_page(db, route))
    commands = """mkdir -p "$HOME/Projects/Safwa" &&
unzip -n "$HOME/Downloads/Safwa-System-Review.zip" -d "$HOME/Projects/Safwa" &&
cd "$HOME/Projects/Safwa/Safwa-System-Review" &&
./safwa setup &&
./safwa create-user yourname --role admin &&
./safwa local"""
    setup = heading("Run the local Safwa system", "Download the review package and save it in Downloads.", "Private review tools")
    setup += f"""<section class="platform-section platform-prose wrap">
      <a class="button" href="/Safwa-System-Review.zip" download="Safwa-System-Review.zip">Download review package</a>
      <h2>Start the local server</h2><pre class="review-command"><code>{escape(commands)}</code></pre>
      <p>Leave the terminal running and open <a href="http://127.0.0.1:4173/">http://127.0.0.1:4173/</a>.</p>
      <p>Follow the README to create local editorial accounts. Use a fresh review database for this revised baseline.</p>
      </section>"""
    write("local-setup.html", shell("Local review setup", setup))
    (destination / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    for page in destination.rglob("*.html"):
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parts = urlsplit(href)
            if not parts.scheme and not parts.netloc and parts.path.startswith("/") and parts.path != "/":
                if not (destination / parts.path.lstrip("/")).is_file():
                    raise ValueError(f"Unresolved local link in {page.name}.")
    print(f"Exported and checked {len(ROUTES) + 1} review pages.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    export(args.destination, args.archive)


if __name__ == "__main__":
    main()
