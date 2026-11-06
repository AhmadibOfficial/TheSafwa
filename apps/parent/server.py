"""Shared CMS routing and the loopback-only development HTTP adapter."""
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, urlencode, urlsplit

from apps.admin import views as admin
from apps.admin import management
from apps.parent import views
from packages.config.review import ASSETS, SESSION_SECONDS
from packages.config.site import PUBLIC_ORIGIN
from packages.content import store
from packages.content import media as images, page_content
from packages.content.contracts import ALLOWED_ARMS, Conflict, Forbidden, Invalid, Missing
from packages.security import auth
from packages.ui.pages import content_url, detail, heading, shell

ALIASES = {
    "/index.html": "/", "/institute.html": "/institute", "/studios.html": "/studios",
    "/quran.html": "/studios/quran", "/quran": "/studios/quran",
    "/work/safwa-quran": "/studios/quran",
    "/connect.html": "/contact", "/connect": "/contact",
    "/work": "/portfolio",
}
ALIASES.update({p['path'] + '.html': p['path'] for p in page_content.PAGES if p['path'] != '/'})
COLLECTIONS = {"/work": "project", "/journal": "article", "/opportunities": "opportunity"}
DETAIL = re.compile(r"/(work|journal|opportunities|institute/learning)/([a-z0-9-]{1,80})")
ENTRY = re.compile(r"/editor/entries/([1-9][0-9]{0,17})")
PREVIEW = re.compile(r"/editor/entries/([1-9][0-9]{0,17})/preview")
MEDIA_PATH = re.compile(r"/(editor/)?media/([0-9a-f]{32})")
INTERESTS = {"general", "learning", "admissions", "community", "studios", "quran"}
SESSION = "safwa_review_session"
LOGIN = "safwa_review_login"
CSP = ("default-src 'self'; img-src 'self'; font-src 'self'; script-src 'self'; "
       "style-src 'self'; object-src 'none'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'self'")
ASSET_PATHS = {
    "/app.js", "/experience.css", "/platform.css",
    "/assets/the-safwa-logo-hd.jpg", "/assets/institute-logo-hd.jpg",
    "/assets/institute-atmosphere-hd.jpg", "/assets/studios-brand-hd.jpg",
    "/assets/white-horse-hd.jpg",
    "/assets/fonts/dm-sans.woff", "/assets/fonts/cormorant-garamond.woff",
    "/assets/fonts/cormorant-garamond-italic.woff",
    "/assets/licenses/dm-sans-OFL.txt", "/assets/licenses/cormorant-garamond-OFL.txt",
}


@dataclass
class Response:
    body: str | bytes = ""
    status: int = 200
    content_type: str = "text/html; charset=utf-8"
    headers: tuple = ()


def redirect(path, *headers):
    return Response(status=303, headers=(("Location", path), *headers))


def cookie(name, value, max_age, *, secure=False):
    return ("Set-Cookie", f"{name}={value}; Path=/editor; Max-Age={max_age}; HttpOnly; SameSite=Strict" + ('; Secure' if secure else ''))


def error_page(code, reason, *, editorial=False):
    title = HTTPStatus(code).phrase
    body = (admin.error_page(title, reason) if editorial
            else shell(title, heading(title, reason, "The Safwa")))
    return Response(body, code)


def public_page(db, path):
    if path in page_content.BY_PATH:
        return views.page(db, path)
    match = DETAIL.fullmatch(path)
    if match:
        section, slug = match.groups()
        kind = COLLECTIONS.get("/" + section, "activity")
        rows = store.published_entries(db, kind=kind, slug=slug)
        if rows:
            return detail(rows[0])
    raise Missing("This page or publication is unavailable.")


def show_entry(db, user, entry_id, **kwargs):
    item = store.work_item(db, user, entry_id)
    return admin.entry(user, item, store.item_history(db, entry_id),
                       store.audit_log(db, user, entry_id), images=images.options(db, user), **kwargs)


def require_editor(user, kind):
    if kind == 'page' or user["role"] != "editor" or user["arm"] not in ALLOWED_ARMS.get(kind, ()):
        raise Forbidden("Choose a content type you can edit in your assigned institutional area.")


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, database, *, public_preview=False):
        # The managed proxy requires a network listener. It serves a fresh public seed only.
        host = "0.0.0.0" if public_preview else "127.0.0.1"
        super().__init__((host, port), ReviewHandler)
        self.database = database
        self.public_preview = public_preview
        self.secure = False
        port = self.server_port
        self.hosts = {f"localhost:{port}", f"127.0.0.1:{port}", f"terminal.local:{port}"}
        if port == 80:
            self.hosts.update({"localhost", "127.0.0.1", "terminal.local"})
        self.origins = {'http://' + host for host in self.hosts}


class Routes:
    server_version = "SafwaReview"
    sys_version = ""
    timeout = 10

    def log_message(self, format, *args):
        # Request paths and form data are deliberately excluded from the console.
        pass

    def dispatch(self):
        editorial = False
        try:
            if len(self.headers.get_all("Host", [])) != 1 or self.headers["Host"].lower() not in self.server.hosts:
                raise Invalid("Open the CMS using its configured address.")
            if (len(self.path) > 2048 or not self.path.startswith("/") or self.path.startswith("//")):
                raise Invalid("The requested address is invalid.")
            target = urlsplit(self.path)
            path = target.path.rstrip("/") or "/"
            editorial = path == "/editor" or path.startswith("/editor/")
            if editorial and self.server.public_preview:
                raise Missing("Editorial access is available on the local review server.")
            query = parse_qs(target.query, max_num_fields=20)
            if any(len(values) != 1 for values in query.values()):
                raise Invalid('The address contains duplicate query fields.')
            if self.command == "POST":
                response = self.post(path) if editorial else Response(status=405, headers=(("Allow", "GET, HEAD"),))
            else:
                response = self.get(path, query, editorial)
        except (Forbidden, Missing, Conflict, ValueError) as error:
            code = 403 if isinstance(error, Forbidden) else 404 if isinstance(error, Missing) else 409 if isinstance(error, Conflict) else 400
            reason = str(error) if isinstance(error, (Invalid, Forbidden, Missing, Conflict)) else "The request contains an invalid value."
            response = error_page(code, reason, editorial=editorial)
        except sqlite3.DatabaseError:
            response = error_page(503, "The CMS database is unavailable. Try again shortly.", editorial=editorial)
        return response, editorial

    def response_headers(self, response, *, editorial):
        policy = CSP if editorial else CSP.replace("form-action 'self'", "form-action 'none'")
        body = response.body.encode("utf-8") if isinstance(response.body, str) else response.body
        headers = [
                ("Content-Type", response.content_type), ("Content-Length", str(len(body))),
                ("Content-Security-Policy", policy), ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "DENY"),
                ("X-Robots-Tag", "noindex, nofollow" if editorial or self.server.public_preview else "index, follow"), ("Cache-Control", "no-store"),
                ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
                *response.headers,
            ]
        if self.server.secure:
            headers.append(('Strict-Transport-Security', 'max-age=31536000'))
        return headers, body

    def cookie(self, name, value, max_age):
        return cookie(name, value, max_age, secure=self.server.secure)

    def read_cookie(self, name):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return ""
        return cookies[name].value if name in cookies else ""

    def login_form(self, status=200, error="", headers=()):
        token = secrets.token_urlsafe(32)
        return Response(admin.login(token, error), status, headers=(self.cookie(LOGIN, token, 600), *headers))

    def get(self, path, query, editorial):
        if path in ALIASES:
            destination = ALIASES[path]
            interest = query.get("interest", [""])[0]
            if destination == "/contact" and interest in INTERESTS:
                destination += "?" + urlencode({"interest": interest})
            return redirect(destination)
        if path == "/robots.txt":
            body = "User-agent: *\nDisallow: /\n" if self.server.public_preview else "User-agent: *\nDisallow: /editor\nSitemap: " + PUBLIC_ORIGIN.get() + "/sitemap.xml\n"
            return Response(body, content_type="text/plain; charset=utf-8")
        if path == '/sitemap.xml':
            from xml.sax.saxutils import escape
            with store.transaction(self.server.database) as db:
                urls = [page['path'] for page in page_content.PAGES]
                urls += [content_url(row) for row in db.execute("SELECT * FROM public_content WHERE kind <> 'page'")]
            body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            body += ''.join('<url><loc>' + escape(PUBLIC_ORIGIN.get() + path) + '</loc></url>' for path in dict.fromkeys(urls))
            return Response(body + '</urlset>', content_type='application/xml; charset=utf-8')
        if path == "/healthz":
            with store.transaction(self.server.database) as db:
                store.check_identity(db)
                db.execute("SELECT count(*) FROM public_content").fetchone()
            return Response("ok\n", content_type="text/plain; charset=utf-8")
        if path in ASSET_PATHS:
            asset = ASSETS / path.lstrip("/")
            if not asset.is_file():
                raise Missing("This asset is unavailable.")
            return Response(asset.read_bytes(), content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
        with store.transaction(self.server.database) as db:
            match = MEDIA_PATH.fullmatch(path)
            if match:
                staff = auth.session(db, self.read_cookie(SESSION)) if match[1] else None
                if match[1] and (not staff or staff['must_change']):
                    raise Forbidden('Sign in to view the image library.')
                image = images.get(db, match[2], user=staff)
                return Response(image['data'], content_type=image['mime'])
            if not editorial:
                return Response(public_page(db, path))
            user = auth.session(db, self.read_cookie(SESSION))
            if path == "/editor/sign-in":
                return redirect("/editor") if user else self.login_form()
            if not user:
                return redirect("/editor/sign-in")
            if user['must_change'] and path != '/editor/account':
                return redirect('/editor/account')
            return Response(self.editorial_page(db, user, path, query))

    def editorial_page(self, db, user, path, query):
        if path == "/editor":
            state = query.get("state", [""])[0]
            state = state if state in admin.STATE else ''
            kind, search = query.get('kind', [''])[0], query.get('q', [''])[0][:100]
            page = self.page_number(query)
            entries = store.work_list(db, user, state=state, kind=kind, search=search, offset=(page-1)*50, limit=51)
            counts = {r[0]: r[1] for r in db.execute('SELECT state, count(*) FROM entries WHERE (? IS NULL OR arm = ?) GROUP BY state', (user['arm'], user['arm']))}
            counts['page'] = db.execute("SELECT count(*) FROM entries WHERE kind = 'page' AND (? IS NULL OR arm = ?)", (user['arm'], user['arm'])).fetchone()[0]
            return admin.dashboard(user, entries[:50], state, kind=kind, search=search, page=page, more=len(entries)>50, counts=counts)
        if path == "/editor/new":
            kind = query.get("kind", [""])[0]
            require_editor(user, kind)
            return admin.new_entry(user, kind, images=images.options(db, user))
        if path == '/editor/media':
            page = self.page_number(query)
            rows = images.library(db, user, limit=25, offset=(page-1)*24)
            return management.image_library(user, rows[:24], page=page, more=len(rows)>24)
        if path == '/editor/account':
            return management.account(user)
        if path == '/editor/staff':
            self.require_admin(user)
            return management.staff(user, self.staff_rows(db))
        if path == "/editor/audit":
            return admin.audit_page(user, store.audit_log(db, user))
        match = ENTRY.fullmatch(path)
        if match:
            return show_entry(db, user, int(match[1]))
        match = PREVIEW.fullmatch(path)
        if match:
            item = store.work_item(db, user, int(match[1]))
            result = views.page(db, page_content.BY_KEY[item['slug']]['path'], preview=item) if item['kind']=='page' else detail(item)
            # Working images are served only through the authenticated image route.
            result = result.replace('src="/media/', 'src="/editor/media/')
            result = result.replace('<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex,nofollow">')
            return result.replace('<main id="main" tabindex="-1">', '<main id="main" tabindex="-1"><aside class="editor-preview-banner">Private working revision. <a href="/editor/entries/' + str(item['id']) + '">Return to record</a></aside>')
        raise Missing("This workspace page is unavailable.")

    def form(self):
        host = self.headers["Host"].lower()
        origin = self.headers.get("Origin")
        if (origin and origin.lower() not in self.server.origins) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise Forbidden("This form must be submitted from the CMS.")
        multipart = self.headers.get_content_type() == 'multipart/form-data'
        if (self.headers.get_content_type() != "application/x-www-form-urlencoded" and not multipart) or self.headers.get("Transfer-Encoding"):
            raise Invalid("This form uses an unsupported format.")
        length = int(self.headers.get("Content-Length", "0"))
        if not 1 <= length <= (images.MAX_UPLOAD + 8192 if multipart else 262144):
            raise Invalid("The form is empty or too large.")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise Invalid('The request body was incomplete.')
        if multipart:
            if not self.path.split('?')[0].rstrip('/') == '/editor/media':
                raise Invalid('File uploads are accepted only in the image library.')
            return self.multipart(raw)
        values = parse_qs(raw.decode("utf-8"), keep_blank_values=True,
                          strict_parsing=True, errors="strict", max_num_fields=128)
        if any(len(items) != 1 for items in values.values()):
            raise Invalid("The form contains duplicate fields.")
        return {key: items[0] for key, items in values.items()}

    def post(self, path):
        form = self.form()
        token = form.get("csrf", "")
        if path == "/editor/sign-in":
            if not auth.matches_token(self.read_cookie(LOGIN), token):
                raise Forbidden("Open a new sign-in form and try again.")
            return self.login_post(form)
        with store.transaction(self.server.database, write=True) as db:
            user = auth.session(db, self.read_cookie(SESSION))
            if not user:
                raise Forbidden("Your session expired. Sign in and reopen the form.")
            if not auth.matches_token(user["csrf"], token):
                raise Forbidden("Refresh the form and try again.")
            if user['must_change'] and path not in {'/editor/account', '/editor/sign-out'}:
                raise Forbidden('Change your temporary passphrase before using the workspace.')
            return self.editorial_post(db, user, path, form)

    def login_post(self, form):
        name = form.get("username", "").strip().lower()
        password = form.get("password", "")
        code = form.get("code", "")
        if not auth.valid_name(name) or not 1 <= len(password) <= 256 or len(code) > 16:
            return self.login_form(401, "Check your user name, passphrase and authenticator code.")
        with store.transaction(self.server.database, write=True) as db:
            session, limited = auth.sign_in(db, name, password, code)
        if limited:
            return self.login_form(429, "Too many attempts. Wait ten minutes and try again.",
                                   (("Retry-After", "600"),))
        if not session:
            return self.login_form(401, "Check your user name, passphrase and authenticator code.")
        return redirect("/editor", self.cookie(SESSION, session, SESSION_SECONDS), self.cookie(LOGIN, "", 0))

    def editorial_post(self, db, user, path, form):
        if path == "/editor/sign-out":
            auth.sign_out(db, user)
            return redirect("/editor/sign-in", self.cookie(SESSION, "", 0))
        if path == '/editor/media':
            try:
                images.upload(db, user, form.get('image', b''), form.get('alt', ''))
            except Invalid as error:
                return Response(management.image_library(user, images.library(db, user), error=str(error)), 422)
            return redirect('/editor/media')
        if path == '/editor/account':
            try:
                if form.get('action') == 'password':
                    if form.get('new') != form.get('confirm'):
                        raise Invalid('The new passphrases do not match.')
                    auth.change_password(db, user, form.get('current', ''), form.get('new', ''))
                    return redirect('/editor/sign-in', self.cookie(SESSION, '', 0))
                if form.get('action') != 'recovery' or user['must_change']:
                    raise Invalid('Change your temporary passphrase first.')
                row = db.execute('SELECT salt, password_hash FROM users WHERE name = ?', (user['name'],)).fetchone()
                import hmac
                if not hmac.compare_digest(auth.password_hash(form.get('current', ''), row['salt']), row['password_hash']):
                    raise Invalid('The current passphrase is incorrect.')
                codes = auth.recovery_codes(db, user['name'], actor=user['name'])
                return Response(management.account(user, codes=codes))
            except Invalid as error:
                return Response(management.account(user, error=str(error)), 422)
        if path == '/editor/staff':
            self.require_admin(user)
            try:
                if form.get('action') == 'create':
                    uri = auth.create_user(db, form.get('name', ''), form.get('role', ''), form.get('arm') or None,
                                           form.get('temporary', ''), actor=user['name'], must_change=True)
                    return Response(management.enrollment(user, form['name'], uri))
                if form.get('action') != 'permissions' or form.get('active') not in {'0', '1'}:
                    raise Invalid('Choose a staff permission action.')
                auth.update_staff(db, user, form.get('name', ''), form.get('role', ''), form.get('arm') or None, form['active']=='1')
            except Invalid as error:
                return Response(management.staff(user, self.staff_rows(db), error=str(error)), 422)
            return redirect('/editor/staff')
        if path == "/editor/new":
            kind = form.get("kind", "")
            require_editor(user, kind)
            try:
                entry_id = store.create(db, user, form)
            except Invalid as error:
                return Response(admin.new_entry(user, kind, form, str(error), images=images.options(db, user)), 422)
            return redirect(f"/editor/entries/{entry_id}")
        match = ENTRY.fullmatch(path)
        if match:
            entry_id = int(match[1])
            try:
                store.change(db, user, entry_id, form)
            except Invalid as error:
                values = form if form.get("action") == "save" else None
                return Response(show_entry(db, user, entry_id, error=str(error), values=values), 422)
            return redirect(path)
        raise Missing("This workspace action is unavailable.")

    @staticmethod
    def require_admin(user):
        if user['role'] != 'admin':
            raise Forbidden('Only an administrator can manage staff accounts.')

    @staticmethod
    def staff_rows(db):
        return db.execute('SELECT name, role, arm, active FROM users ORDER BY name').fetchall()

    @staticmethod
    def page_number(query):
        value = int(query.get('page', ['1'])[0])
        if not 1 <= value <= 10000:
            raise Invalid('Choose a valid page number.')
        return value

    def multipart(self, raw):
        header = self.headers['Content-Type']
        if '\r' in header or '\n' in header or len(header) > 200:
            raise Invalid('The upload format is invalid.')
        parsed = BytesParser(policy=email_policy).parsebytes(('Content-Type: ' + header + '\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii') + raw)
        if not parsed.is_multipart() or parsed.defects:
            raise Invalid('The upload could not be read.')
        fields = {}
        for part in parsed.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if part.is_multipart() or part.defects or part.get_content_disposition() != 'form-data' or name not in {'csrf', 'image', 'alt'} or name in fields:
                raise Invalid('The upload contains an unsupported or duplicate field.')
            value = part.get_payload(decode=True)
            if value is None:
                raise Invalid('The upload is incomplete.')
            if name != 'image' and len(value)>1000:
                raise Invalid('The upload text is too long.')
            fields[name] = value if name == 'image' else value.decode('utf-8')
        if set(fields) != {'csrf', 'image', 'alt'}:
            raise Invalid('Choose an image and complete its description.')
        return fields


class ReviewHandler(Routes, BaseHTTPRequestHandler):
    """Loopback-only development adapter. Production uses the WSGI application."""
    def do_GET(self):
        response, editorial = self.dispatch()
        headers, body = self.response_headers(response, editorial=editorial)
        try:
            self.send_response(response.status)
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_HEAD = do_GET
    do_POST = do_GET
