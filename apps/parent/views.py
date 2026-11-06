"""The approved public templates, populated exclusively from published revisions."""
import json
import re
from html import escape

from packages.content import page_content, store
from packages.content.contracts import Missing
from packages.ui.pages import collection, media, paragraphs, shell, status


def page(db, path, *, preview=None):
    key = page_content.BY_PATH.get(path)
    if key is None:
        raise Missing("This page is unavailable.")
    rows = store.published_entries(db, kind="page", slug=key)
    item = preview or (rows[0] if rows else None)
    if item is None:
        raise Missing("This page is unavailable.")
    specification = page_content.BY_KEY[key]
    body = page_content.render_body(key, json.loads(item["blocks"]))
    kind = {"journal": "article", "opportunities": "opportunity"}.get(key, "project")
    if key in {"home", "studios", "portfolio", "journal", "opportunities"}:
        rows = store.published_entries(db, kind=kind, arm="studios" if key == "studios" else None)
        if rows:
            title = {"article": "From Safwa", "project": "The work", "opportunity": "Current opportunities"}[kind]
            body = re.sub(r'<section[^>]*class="institution-quiet wrap"[^>]*>.*?</section>',
                          lambda _: collection(title, rows, anchor="published-content"), body, count=1, flags=re.S)
    if key == "institute":
        rows = store.published_entries(db, kind="activity", arm="institute")
        if rows:
            body += collection("Learning and community", rows, anchor="learning")
    if key == 'quran':
        rows = store.published_entries(db, kind='project', arm='studios', slug='safwa-quran')
        if rows:
            project = rows[0]
            section = ('<section class="platform-section platform-prose wrap"><h2>About the project</h2>'
                       '<p class="status">' + escape(status(project)) + '</p>' + media(project)
                       + '<p><strong>' + escape(project['summary']) + '</strong></p>'
                       + paragraphs(project['body'])
                       + '<a class="text-link" href="/contact?interest=quran">Ask about Safwa Quran</a></section>')
            body = re.sub(r'<section class="platform-section platform-prose wrap">.*?</section>',
                          lambda _: section, body, count=1, flags=re.S)
    return shell(item["title"], body, current=specification["page"], theme=specification["theme"],
                 path=path, description=item["summary"])
