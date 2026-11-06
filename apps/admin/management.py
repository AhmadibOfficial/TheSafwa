"""Staff, image-library and personal security pages."""
from html import escape

from apps.admin.views import choices, hidden, layout, message
from packages.content.contracts import ARMS
from packages.security.auth import ROLES


def image_library(user, rows, *, page=1, more=False, error=""):
    upload = ''
    if user['role'] == 'editor':
        upload = f'''<section class="editor-panel editor-form"><h2>Add an image</h2>
        <p>JPEG or PNG, up to 4 MB and 12 million pixels. Images become public when a revision using them is published.</p>
        <form method="post" action="/editor/media" enctype="multipart/form-data">{hidden('csrf', user['csrf'])}
        <label for="image">Image file</label><input id="image" type="file" name="image" accept="image/jpeg,image/png" required>
        <label for="alt">Image description</label><input id="alt" name="alt" maxlength="240" required>
        <button type="submit" class="button">Add to library</button></form></section>'''
    cards = ''.join(f'''<article class="editor-panel"><img src="/editor/media/{row['id']}" alt="{escape(row['alt'])}" loading="lazy">
        <h2>{escape(row['alt'])}</h2><p>{ARMS[row['arm']]} · {row['width']} × {row['height']} · {round(row['size']/1024)} KB</p>
        <p>{escape(row['author'])} · {row['created_at']} UTC</p></article>''' for row in rows)
    links = (f'<a href="/editor/media?page={page-1}">Previous page</a>' if page > 1 else '')
    links += (f'<a href="/editor/media?page={page+1}">Next page</a>' if more else '')
    return layout('Image library', f'''<section class="editor-heading"><p class="eyebrow gold">Publishing assets</p>
        <h1>Image library</h1><p>Descriptions are saved with each image. Previous publications retain their original image and description.</p>{message(error)}</section>
        {upload}<div class="editor-media-grid">{cards or '<p>No images have been added in this area.</p>'}</div>
        <nav class="editor-chips" aria-label="Image library pages">{links}</nav>''', user)


def account(user, *, error="", codes=None):
    shown = ''
    if codes:
        shown = '<section class="editor-panel"><h2>Save these recovery codes now</h2><p>Each code works once with your passphrase. Previous recovery codes have been replaced. Keep these somewhere private, separate from your authenticator.</p><ul class="editor-codes">' + ''.join(f'<li><code>{escape(c)}</code></li>' for c in codes) + '</ul></section>'
    notice = 'Change the temporary passphrase before using the workspace.' if user['must_change'] else 'Changing your passphrase signs out all sessions, including this one.'
    return layout('Your account', f'''<section class="editor-heading"><p class="eyebrow gold">Personal security</p><h1>Your account</h1>
        <p>{escape(user['name'])} · {ROLES[user['role']]}</p>{message(error)}</section>{shown}
        <section class="editor-panel editor-form"><h2>Change passphrase</h2><p>{notice}</p>
        <form method="post" action="/editor/account">{hidden('csrf', user['csrf'])}{hidden('action', 'password')}
        <label for="current">Current passphrase</label><input id="current" name="current" type="password" autocomplete="current-password" maxlength="256" required>
        <label for="new">New passphrase</label><input id="new" name="new" type="password" autocomplete="new-password" minlength="14" maxlength="256" required>
        <label for="confirm">Confirm new passphrase</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" minlength="14" maxlength="256" required>
        <button type="submit" class="button">Change passphrase and sign out</button></form></section>
        <section class="editor-section editor-panel editor-form"><h2>Recovery codes</h2><p>Generate a new set if you have lost your saved codes. Your passphrase is required.</p>
        <form method="post" action="/editor/account">{hidden('csrf', user['csrf'])}{hidden('action', 'recovery')}
        <label for="recovery-current">Current passphrase</label><input id="recovery-current" name="current" type="password" autocomplete="current-password" maxlength="256" required>
        <button type="submit" class="button">Replace recovery codes</button></form></section>''', user)


def staff(user, rows, *, error=""):
    records = ''
    for row in rows:
        if row['name'] == user['name']:
            controls = '<p>Your current account. Another administrator must change its permissions.</p>'
        else:
            controls = f'''<form method="post" action="/editor/staff">{hidden('csrf', user['csrf'])}{hidden('action', 'permissions')}{hidden('name', row['name'])}
            <label for="role-{row['name']}">Role</label><select id="role-{row['name']}" name="role">{choices(ROLES, row['role'])}</select>
            <label for="arm-{row['name']}">Institutional area</label><select id="arm-{row['name']}" name="arm">{choices({'': 'All areas (administrator only)', **ARMS}, row['arm'] or '')}</select>
            <label for="active-{row['name']}">Account access</label><select id="active-{row['name']}" name="active">{choices({'1': 'Active', '0': 'Disabled'}, str(row['active']))}</select>
            <button type="submit" class="button">Update permissions and end sessions</button></form>'''
        records += f'''<article class="editor-panel"><h2>{escape(row['name'])}</h2><p>{ROLES[row['role']]} · {ARMS.get(row['arm'], 'All areas')} · {'Active' if row['active'] else 'Disabled'}</p>{controls}</article>'''
    return layout('Staff accounts', f'''<section class="editor-heading"><p class="eyebrow gold">Administration</p><h1>Staff accounts</h1>
        <p>Editors draft. Reviewers approve. Publishers release. Administrators manage access and inspect the audit trail.</p>{message(error)}</section>
        <section class="editor-panel editor-form"><h2>Create an individual account</h2><p>Provide the temporary passphrase and authenticator setup privately to the staff member. Their first sign-in requires a passphrase change.</p>
        <form method="post" action="/editor/staff">{hidden('csrf', user['csrf'])}{hidden('action', 'create')}
        <label for="name">User name</label><input id="name" name="name" pattern="[a-z][a-z0-9._-]{{2,31}}" maxlength="32" required autocomplete="off">
        <label for="role">Role</label><select id="role" name="role">{choices(ROLES, 'editor')}</select>
        <label for="arm">Institutional area</label><select id="arm" name="arm">{choices({'': 'All areas (administrator only)', **ARMS}, 'parent')}</select>
        <label for="temporary">Temporary passphrase</label><input id="temporary" name="temporary" type="password" minlength="14" maxlength="256" required autocomplete="new-password">
        <button type="submit" class="button">Create staff account</button></form></section>
        <div class="editor-media-grid">{records}</div>''', user)


def enrollment(user, name, uri):
    from urllib.parse import parse_qs, urlsplit
    secret = parse_qs(urlsplit(uri).query)['secret'][0]
    return layout('Authenticator setup', f'''<section class="editor-heading"><p class="eyebrow gold">Account created</p>
        <h1>Set up {escape(name)}</h1><p>This setup key is shown only now. Transfer it privately to the account holder and do not include it in email logs or screenshots.</p></section>
        <section class="editor-panel"><h2>Authenticator setup</h2><p>Add an account named The Safwa: {escape(name)} in an authenticator app using a time-based, six-digit code.</p>
        <p>Setup key: <code class="editor-secret">{escape(secret)}</code></p>
        <details><summary>Enrollment URI</summary><code class="editor-secret">{escape(uri)}</code></details>
        <p>The account holder signs in with the temporary passphrase and authenticator code, changes the passphrase, then generates recovery codes in Your account.</p>
        <a class="text-link" href="/editor/staff">Return to staff accounts</a></section>''', user)
