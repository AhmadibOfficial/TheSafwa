"""Server-rendered editorial pages. Permissions are enforced by the service."""
from html import escape
import json
from urllib.parse import urlencode

from packages.config.review import MEDIA
from packages.content.contracts import ALLOWED_ARMS, ARMS, KINDS, STATUSES
from packages.content.store import TRANSITIONS
from packages.security.auth import ROLES
from packages.ui.pages import content_url, media, paragraphs, shell, status

STATE = {"draft": "Draft", "review": "In review", "approved": "Approved",
         "published": "Published", "archived": "Archived"}
ACTION = {"submit": "Send for review", "approve": "Approve revision", "return": "Return to draft",
          "publish": "Publish revision", "archive": "Archive publication"}


def hidden(name, value):
    return f'<input type="hidden" name="{name}" value="{escape(str(value))}">'


def message(text):
    return f'<p class="editor-notice" role="alert">{escape(text)}</p>' if text else ""


def layout(title, body, user=None):
    toolbar = ""
    if user:
        scope = ARMS[user["arm"]] if user["arm"] else "All institutional areas"
        audit = '<a href="/editor/audit">System audit</a>' if user["role"] == "admin" else ""
        staff = '<a href="/editor/staff">Staff</a>' if user["role"] == "admin" else ""
        toolbar = f"""<div class="editor-toolbar">
        <nav aria-label="Editorial navigation"><a href="/editor">Workspace</a><a href="/editor/media">Images</a>{staff}{audit}<a href="/editor/account">Your account</a></nav>
        <div><span>{escape(user["name"])} · {ROLES[user["role"]]} · {scope}</span>
        <form method="post" action="/editor/sign-out">{hidden("csrf", user["csrf"])}
        <button type="submit" class="editor-plain">Sign out</button></form></div></div>"""
    return shell(title, f'<div class="editor-wrap">{toolbar}{body}</div>', current="editor", staff=True)


def login(csrf, error=""):
    body = f"""<section class="editor-login editor-panel">
      <p class="eyebrow gold">Staff access</p><h1>Editorial workspace</h1>
      <p>Sign in with your individual account and the current code from your authenticator.</p>
      {message(error)}
      <form method="post" action="/editor/sign-in">{hidden("csrf", csrf)}
        <label for="username">User name</label>
        <input id="username" name="username" autocomplete="username" required maxlength="32" autocapitalize="none">
        <label for="password">Passphrase</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256">
        <label for="code">Authenticator or recovery code</label>
        <input id="code" name="code" autocomplete="one-time-code" maxlength="16" required>
        <button type="submit" class="button">Sign in</button>
      </form></section>"""
    return layout("Staff sign-in", body)


def dashboard(user, entries, selected="", *, kind="", search="", page=1, more=False, counts=None):
    kinds = "".join(
        f'<a class="editor-chip" href="/editor/new?kind={kind}">New {label.lower()}</a>'
        for kind, label in KINDS.items() if kind != "page" and user["arm"] in ALLOWED_ARMS[kind]
    ) if user["role"] == "editor" else ""
    filters = "".join(
        f'<a class="editor-chip"{aria_current(selected == state)} href="/editor{query}">{label}</a>'
        for state, label, query in [("", "All", "")] + [
            (key, name, "?state=" + key) for key, name in STATE.items()
        ]
    )
    rows = "".join(
        f"""<li><div><p class="eyebrow">{ARMS[item["arm"]]} · {KINDS[item["kind"]]}</p>
        <h2><a href="/editor/entries/{item["id"]}">{escape(item["title"])}</a></h2></div>
        <div><span class="editor-chip">{STATE[item["state"]]}</span>
        <span>Working revision {item["working"]} · {publication(item)}</span></div></li>"""
        for item in entries if not selected or selected == item["state"]
    ) or '<li>No records match this view.</li>'
    stats = '<div class="editor-stats">' + ''.join(
        f'<div><strong>{(counts or {}).get(key, 0)}</strong><span>{label}</span></div>'
        for key, label in (("page", "Website pages"), ("draft", "Drafts"), ("review", "Awaiting review"), ("approved", "Ready to publish"))
    ) + '</div>'
    paging = '<nav class="editor-chips" aria-label="Workspace pages">'
    for number, label in ((page - 1, "Previous page"), (page + 1, "Next page")):
        if number >= 1 and (number < page or more):
            paging += '<a class="editor-chip" href="/editor?' + escape(urlencode({"state": selected, "kind": kind, "q": search, "page": number})) + '">' + label + '</a>'
    paging += '</nav>'
    body = f"""<section class="editor-heading"><p class="eyebrow gold">Publishing</p><h1>Content workspace</h1>
      <p>Review the working revision and its publication status separately.</p>
      {stats}<div class="editor-chips">{kinds}</div></section>
      <form method="get" action="/editor" class="editor-search">
      <label for="q">Find content</label><input id="q" name="q" maxlength="100" value="{escape(search)}" placeholder="Title or URL name">
      <label for="kind">Content type</label><select id="kind" name="kind">{choices({'': 'All content', **KINDS}, kind)}</select>
      {hidden('state', selected)}<button type="submit" class="button">Search</button></form>
      <nav class="editor-chips editor-filters" aria-label="Filter by editorial state">{filters}</nav>
      <ul class="editor-records" aria-label="Content records">{rows}</ul>{paging}"""
    return layout("Content workspace", body, user)


def aria_current(active):
    return ' aria-current="page"' if active else ""


def publication(item):
    return f'Public revision {item["published"]}' if item["published"] is not None else "Unpublished"


def choices(values, selected):
    return "".join(
        f'<option value="{key}"{" selected" if key == selected else ""}>{escape(label)}</option>'
        for key, label in values.items()
    )


def content_fields(kind, values, *, slug=None, images=None):
    if kind == "page":
        from packages.content.page_content import template
        fields = json.loads(values.get("blocks", "{}"))
        fields.update({key: value for key, value in values.items() if key.startswith("block_")})
        blocks = ''.join(f'<label for="{slot["key"]}">{index}. {slot["label"]}</label>'
                         f'<textarea id="{slot["key"]}" name="{slot["key"]}" rows="2" maxlength="3000" required>{escape(fields.get(slot["key"], slot["text"]))}</textarea>'
                         for index, slot in enumerate(template(slug)[1], 1))
        return f'''<label for="title">Page title for search and sharing</label>
        <input id="title" name="title" value="{escape(values.get('title', ''))}" maxlength="100" required>
        <label for="summary">Search description</label><textarea id="summary" name="summary" rows="3" maxlength="280" required>{escape(values.get('summary', ''))}</textarea>
        <h3 class="editor-section">Page text, in display order</h3><p>The layout, navigation and approved brand images are preserved.</p>{blocks}'''
    status_options = choices(STATUSES[kind], values.get("status"))
    media_options = choices({**{key: label for key, (label, _) in MEDIA.items()}, **(images or {})}, values.get("media"))
    return f"""
    <label for="title">Title</label>
    <input id="title" name="title" required maxlength="100" value="{escape(values.get('title', ''))}">
    <label for="summary">Summary</label>
    <textarea id="summary" name="summary" rows="3" required maxlength="280">{escape(values.get('summary', ''))}</textarea>
    <label for="body">Body</label><p id="body-help">Use plain text. A blank line starts a new paragraph.</p>
    <textarea id="body" name="body" rows="8" required maxlength="8000" aria-describedby="body-help">{escape(values.get('body', ''))}</textarea>
    <label for="status">Public status</label><select id="status" name="status">{status_options}</select>
    <label for="media">Publication image</label><select id="media" name="media">{media_options}</select>
    <p><a href="/editor/media">Add or review images</a> before selecting one.</p>"""


def new_entry(user, kind, data=None, error="", *, images=None):
    data = {} if data is None else data
    fields = content_fields(kind, data, images=images)
    body = f"""<section class="editor-panel editor-form">
      <p class="eyebrow gold">{ARMS[user["arm"]]}</p><h1>New {KINDS[kind].lower()}</h1>
      {message(error)}
      <form method="post" action="/editor/new">{hidden("csrf", user["csrf"])}{hidden("kind", kind)}
      <label for="slug">URL name</label><p id="slug-help">Use lowercase letters, digits and hyphens. This address is permanent.</p>
      <input id="slug" name="slug" maxlength="80" pattern="[a-z0-9]+(-[a-z0-9]+)*" required
        aria-describedby="slug-help" value="{escape(data.get('slug', ''))}">
      {fields}<button class="button" type="submit">Create draft</button></form></section>"""
    return layout("New draft", body, user)


def action_forms(user, item, action_path):
    choices_html = []
    for (state, action), (role, _) in TRANSITIONS.items():
        if state != item["state"] or role != user["role"]:
            continue
        if action == "archive" and item["published"] is None:
            continue
        if action == "archive" and item["kind"] == "page":
            continue
        note_id = f"{action}-note"
        required = " required" if action in {"return", "archive"} else ""
        help_text = "Reason (required)" if required else "Decision note (optional)"
        choices_html.append(f"""<form method="post" action="{action_path}" class="editor-panel">
        {hidden("csrf", user["csrf"])}{hidden("version", item["version"])}{hidden("action", action)}
        <h3>{ACTION[action]}</h3><label for="{note_id}">{help_text}</label>
        <textarea id="{note_id}" name="note" rows="2" maxlength="500"{required}></textarea>
        <button class="button" type="submit">{ACTION[action]}</button></form>""")
    if not choices_html:
        return ""
    return '<section class="editor-section"><h2>Editorial decisions</h2><div class="editor-actions">' + "".join(choices_html) + '</div></section>'


def audit_rows(events):
    rows = []
    for event in events:
        revision = f' · Revision {event["revision"]}' if event["revision"] is not None else ""
        entry = f' · Record {event["entry_id"]}' if event["entry_id"] is not None else ""
        note = f'<p>{escape(event["note"])}</p>' if event["note"] else ""
        rows.append(f"""<li><strong>{escape(event["action"].capitalize())}</strong>
        <span>{escape(event["actor"])}{entry}{revision} · {escape(event["created_at"])} UTC</span>{note}</li>""")
    return '<ol class="editor-history">' + ("".join(rows) or "<li>No events recorded.</li>") + "</ol>"


def revisions_list(revisions, published):
    return "".join(f"""<details class="editor-revision">
        <summary>Revision {rev["number"]} · {escape(rev["title"])}
        {" · Current public revision" if rev["number"] == published else ""}</summary>
        <p>{escape(rev["author"])} · {escape(rev["created_at"])} UTC</p>
        <p>{escape(rev["summary"])}</p>{paragraphs(rev["body"])}</details>""" for rev in revisions)


def entry(user, item, revisions, events, *, error="", values=None, images=None):
    path = f'/editor/entries/{item["id"]}'
    edit = ""
    if user["role"] == "editor" and item["state"] in {"draft", "published", "archived"}:
        edit = f"""<section class="editor-section editor-panel editor-form"><h2>Edit working copy</h2>
        <p>Saving creates a private revision. The existing publication stays available while your changes are reviewed.</p>
        <form method="post" action="{path}">
        {hidden("csrf", user["csrf"])}{hidden("version", item["version"])}{hidden("action", "save")}
        {content_fields(item["kind"], dict(item) if values is None else values, slug=item['slug'], images=images)}
        <button class="button" type="submit">Save draft revision</button></form></section>"""
    public_link = f'<a href="{escape(content_url(item))}">View public revision</a>' if item["published"] else ""
    if item["kind"] == "page":
        from packages.content.page_content import template
        blocks = json.loads(item["blocks"])
        preview = ''.join(f'<p><strong>{escape(slot["label"])}</strong><br>{escape(blocks.get(slot["key"], slot["text"]))}</p>' for slot in template(item["slug"])[1])
    else:
        preview = media(item, staff=True) + '<p><strong>' + escape(item["summary"]) + '</strong></p>' + paragraphs(item["body"])
    preview_link = f'<a href="{path}/preview" target="_blank" rel="noopener">Preview working revision in layout</a>'
    restore = ''
    if user['role'] == 'editor' and item['state'] in {'draft', 'published', 'archived'} and len(revisions) > 1:
        options = choices({str(r['number']): f'Revision {r["number"]}: {r["title"]}' for r in revisions}, '')
        restore = f'''<section class="editor-section editor-panel"><h2>Restore a previous revision</h2>
        <p>This creates a new draft for review. It does not change the public revision.</p>
        <form method="post" action="{path}">{hidden('csrf', user['csrf'])}{hidden('version', item['version'])}{hidden('action', 'restore')}
        <label for="revision">Source revision</label><select id="revision" name="revision">{options}</select><button class="button" type="submit">Restore as draft</button></form></section>'''
    body = f"""<section class="editor-heading"><p class="eyebrow gold">{ARMS[item["arm"]]} · {KINDS[item["kind"]]}</p>
      <h1>{escape(item["title"])}</h1>
      <p>{STATE[item["state"]]} · Working revision {item["working"]} · {publication(item)}</p><div class="editor-chips">{public_link}{preview_link}</div>
      {message(error)}</section>
      <section class="editor-section editor-panel platform-prose">
      <h2>Working preview</h2><p class="eyebrow">{escape(status(item))}</p>{preview}</section>
      {edit}{action_forms(user, item, path)}{restore}
      <section class="editor-section"><h2>Revision history</h2>{revisions_list(revisions, item["published"])}</section>
      <section class="editor-section"><h2>Audit history</h2>{audit_rows(events)}</section>"""
    return layout(item["title"], body, user)


def audit_page(user, events):
    return layout("System audit", '<section class="editor-heading"><p class="eyebrow gold">Administration</p>'
                  '<h1>System audit</h1><p>Most recent 200 events.</p></section>' + audit_rows(events), user)


def error_page(title, detail, user=None):
    return layout(title, f"""<section class="editor-heading"><h1>{escape(title)}</h1>
                  <p>{escape(detail)}</p><a href="/editor">Back to the workspace</a></section>""", user)
