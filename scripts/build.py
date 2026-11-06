#!/usr/bin/env python3
"""Build the approved Safwa institutional website without runtime dependencies."""
from html import escape
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
DIST = ROOT / "dist"
ORIGIN = "https://thesafwa.onrender.com"
PAGES = json.loads((CONTENT / "pages.json").read_text(encoding="utf-8"))
CLEAN_LINKS = {
    "/about.html": "/about", "/contact.html": "/contact",
    "/connect.html": "/contact", "/institute.html": "/institute",
    "/studios.html": "/studios", "/studios/quran.html": "/studios/quran",
    "/quran.html": "/studios/quran", "/portfolio.html": "/portfolio",
    "/work.html": "/portfolio", "/journal.html": "/journal",
    "/opportunities.html": "/opportunities",
}
CSP = ("default-src 'self'; img-src 'self' data:; font-src 'self'; "
       "script-src 'self'; style-src 'self'; object-src 'none'; "
       "base-uri 'self'; form-action 'none'")


def clean_link(match):
    href = match[1]
    parts = re.split(r"(?=[?#])", href, maxsplit=1)
    return 'href="' + CLEAN_LINKS.get(parts[0], parts[0]) + "".join(parts[1:]) + '"'


def metadata(page, origin=ORIGIN):
    url = origin + page["path"]
    title = escape(page["title"], quote=True)
    description = escape(page["description"], quote=True)
    theme = "#102c24" if page["theme"] else "#f7f4ed"
    return f"""<meta name="robots" content="index,follow">
<meta name="description" content="{description}">
<meta name="theme-color" content="{theme}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{origin}/assets/the-safwa-logo-hd.jpg">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta http-equiv="Content-Security-Policy" content="{CSP}">"""


def main():
    layout = (CONTENT / "layout.html").read_text(encoding="utf-8")
    DIST.mkdir(exist_ok=True)
    for page in PAGES:
        body = (CONTENT / "pages" / page["fragment"]).read_text(encoding="utf-8")
        html = (layout.replace("@@TITLE@@", escape(page["title"]))
                .replace("@@THEME@@", page["theme"])
                .replace("@@PAGE@@", page["page"])
                .replace("@@METADATA@@", metadata(page))
                .replace("@@CONTENT@@", body))
        html = re.sub(r'href="([^"]+)"', clean_link, html)
        current = {"institute": "/institute", "studios": "/studios", "journal": "/journal",
                   "about": "/about", "opportunities": "/opportunities"}.get(page["page"])
        if current:
            html = html.replace(f'<a href="{current}">', f'<a href="{current}" aria-current="page">', 1)
        if page["path"] == "/":
            outputs = ["index.html"]
        else:
            route = page["path"].lstrip("/")
            outputs = [route + ".html", route + "/index.html"]
        for name in outputs + page["aliases"]:
            destination = DIST / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(html, encoding="utf-8")
        print("Built " + page["path"])
    urls = "".join(f'<url><loc>{xml_escape(ORIGIN + page["path"])}</loc></url>' for page in PAGES)
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + urls + '</urlset>\n', encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    main()
