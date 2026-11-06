"""Shared page shell and accessible content components."""
from html import escape

from packages.config.review import MEDIA
from packages.config.site import PUBLIC_ORIGIN
from packages.content.contracts import ARMS, ROUTES, STATUSES
from packages.content.page_content import CONTENT
from scripts.build import clean_link, metadata
import re


def shell(title, body, *, current="", theme="", staff=False, path="/", description=""):
    if not staff:
        page = {"title": title + " | The Safwa", "description": description or title,
                "theme": theme, "page": current, "path": path}
        layout = (CONTENT / "layout.html").read_text(encoding="utf-8")
        result = layout.replace("@@CONTENT@@", body).replace("@@TITLE@@", escape(page["title"]))
        result = result.replace("@@METADATA@@", metadata(page, PUBLIC_ORIGIN.get())).replace("@@THEME@@", theme).replace("@@PAGE@@", current)
        return re.sub(r'href="([^"]+)"', clean_link, result)
    scripts = "" if staff else '<script src="/app.js" defer></script>'
    masthead = """
        <a class="skip-link" href="#main">Skip to content</a>
        <header class="editor-masthead"><a href="/editor">The Safwa <span>Editorial</span></a>
        <a href="/">View public site</a></header>
    """
    foot = '<footer class="editor-foot">The Safwa · Editorial workspace</footer>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{escape(title)} | The Safwa</title>
<link rel="icon" href="/assets/the-safwa-logo-hd.jpg" type="image/jpeg">
<link rel="stylesheet" href="/experience.css"><link rel="stylesheet" href="/platform.css">{scripts}
</head><body data-theme="{theme}" data-page="{current}">{masthead}
<main id="main" tabindex="-1">{body}</main>{foot}</body></html>"""


def heading(title, intro, label):
    return f"""<section class="platform-heading wrap">
        <p class="eyebrow gold">{escape(label)}</p>
        <h1>{escape(title)}</h1><p class="platform-lede">{escape(intro)}</p>
    </section>"""


def content_url(item):
    if item["kind"] == "page":
        from packages.content.page_content import BY_KEY
        return BY_KEY[item["slug"]]["path"]
    if item["kind"] == "project" and item["slug"] == "safwa-quran":
        return "/studios/quran"
    return ROUTES[item["kind"]] + item["slug"]


def media(item, *, staff=False):
    path = item["media"]
    if re.fullmatch(r"upload:[a-f0-9]{32}", path):
        prefix = "/editor/media/" if staff else "/media/"
        alt = item["media_alt"] if "media_alt" in item.keys() else "Publication image"
        return f'<img src="{prefix}{path[7:]}" alt="{escape(alt)}" loading="lazy">'
    if not path or path not in MEDIA:
        return ""
    _, alt = MEDIA[path]
    return f'<img src="/assets/{path}" alt="{escape(alt)}" loading="lazy">'


def status(item):
    return STATUSES[item["kind"]][item["status"]]


def cards(items):
    if not items:
        return '<p class="platform-empty">There are no published entries in this section yet.</p>'
    items_html = []
    for item in items:
        items_html.append(f"""<article class="platform-card">
            {media(item)}
            <div class="platform-card-copy"><p class="eyebrow">{escape(status(item))}</p>
            <h3><a href="{escape(content_url(item))}">{escape(item["title"])}</a></h3>
            <p>{escape(item["summary"])}</p></div></article>""")
    return '<div class="platform-cards">' + "".join(items_html) + '</div>'


def collection(title, items, *, anchor):
    return f"""<section id="{anchor}" class="platform-section wrap" aria-labelledby="{anchor}-title">
        <h2 id="{anchor}-title">{escape(title)}</h2>{cards(items)}</section>"""


def paragraphs(text):
    return "".join(f"<p>{escape(paragraph.strip())}</p>"
                   for paragraph in text.replace("\r\n", "\n").split("\n\n") if paragraph.strip())


def detail(item):
    kind = item["kind"]
    current = {"article": "journal", "project": "work", "activity": "institute",
               "opportunity": "opportunities"}[kind]
    target = {"parent": "general", "institute": "learning", "studios": "studios"}[item["arm"]]
    body = heading(item["title"], item["summary"], ARMS[item["arm"]]) + f"""
        <section class="platform-article wrap"><p class="status">{escape(status(item))}</p>
        <div class="platform-article-media">{media(item)}</div>
        <div class="platform-prose">{paragraphs(item["body"])}</div>
        <div class="platform-actions">
        <a class="text-link" href="/contact?interest={target}">Ask about {escape(item["title"])}</a>
        <a class="text-link" href="/{current}">Back to {current}</a></div></section>"""
    return shell(item["title"], body, current=current, path=content_url(item), description=item["summary"])
