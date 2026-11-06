"""Exercise the standalone public and editorial system over its real HTTP boundary."""
from http.client import HTTPConnection
from http.cookies import SimpleCookie
from pathlib import Path
import re
import secrets
from tempfile import TemporaryDirectory
from threading import Thread
import time
from unittest import TestCase
from urllib.parse import urlencode

from apps.parent.server import ReviewServer
from packages.content import store
from packages.content.contracts import Invalid
from packages.security import auth
from packages.security.vault import decrypt


class Client:
    def __init__(self, port):
        self.port = port
        self.cookies = SimpleCookie()

    def request(self, path, data=None, *, headers=None, method=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        # Only cookie names and values belong in a request.
        supplied = {"Cookie": "; ".join(f"{key}={item.value}" for key, item in self.cookies.items())}
        body = None
        if data is not None:
            body = data if isinstance(data, bytes) else urlencode(data)
            if not isinstance(data, bytes):
                supplied["Content-Type"] = "application/x-www-form-urlencoded"
        supplied.update(headers or {})
        try:
            connection.request(method or ("GET" if data is None else "POST"), path, body, supplied)
            response = connection.getresponse()
            for header, value in response.getheaders():
                if header.lower() == "set-cookie":
                    self.cookies.load(value)
            return response.status, response.headers, response.read().decode("utf-8", errors="replace")
        finally:
            connection.close()

    def token(self, path):
        status, _, html = self.request(path)
        if status != 200:
            raise AssertionError(f"Expected a form at {path}, got {status}")
        return re.search(r'name="csrf" value="([^"]+)"', html)[1]

    def login(self, name, password, code):
        return self.request("/editor/sign-in", {
            "username": name, "password": password, "code": code,
            "csrf": self.token("/editor/sign-in"),
        })


class ReviewSystemTests(TestCase):
    @classmethod
    def setUpClass(cls):
        temp = TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.directory = Path(temp.name)
        cls.database = cls.directory / "review.sqlite3"
        store.initialize(cls.database)
        cls.server = ReviewServer(0, cls.database)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5)
        cls.addClassCleanup(cls.server.shutdown)

    def client(self):
        return Client(self.server.server_port)

    def staff(self, name, role, arm):
        password = secrets.token_urlsafe(24)
        with store.transaction(self.database, write=True) as db:
            auth.create_user(db, name, role, arm, password)
            key = decrypt(db, db.execute("SELECT otp_key FROM users WHERE name = ?", (name,)).fetchone()[0])
        code = auth.totp(key, int(time.time()) // 30)
        client = self.client()
        status, headers, _ = client.login(name, password, code)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/editor")
        session_header = next(value for value in headers.get_all("Set-Cookie") if "session=" in value)
        self.assertIn("HttpOnly", session_header)
        self.assertIn("SameSite=Strict", session_header)
        return client, password, code

    def test_public_route_tree_and_assets(self):
        client = self.client()
        routes = {
            "/": "Building institutions", "/about": "Khadija Sabiu", "/institute": "Arabic Club",
            "/studios": "Safwa OS", "/studios/quran": "IN DEVELOPMENT",
            "/journal": "From Safwa", "/opportunities": "No openings",
            "/contact": "Prepare your enquiry", "/portfolio": "Two divisions",
        }
        for path, text in routes.items():
            with self.subTest(path=path):
                status, headers, body = client.request(path)
                self.assertEqual(status, 200)
                self.assertIn(text.casefold(), body.casefold())
                self.assertNotRegex(body, r"[←→↗↘↓↑]")
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertIn("form-action 'none'", headers["Content-Security-Policy"])
        for path in (
            "/institute/learning/arabic-club", "/work/documentaries",
            "/journal/one-institution-several-purposes", "/opportunities/collaborate",
        ):
            self.assertEqual(client.request(path)[0], 404)
        for path, destination in (
            ("/index.html", "/"), ("/quran.html", "/studios/quran"),
            ("/work", "/portfolio"),
            ("/connect.html?interest=quran", "/contact?interest=quran"),
            ("/connect.html?interest=//elsewhere", "/contact"),
        ):
            status, headers, _ = client.request(path)
            self.assertEqual((status, headers["Location"]), (303, destination))
        self.assertEqual(client.request("/healthz")[2], "ok\n")
        for path in ("/app.js", "/platform.css", "/assets/white-horse-hd.jpg"):
            status, headers, body = client.request(path, method="HEAD")
            self.assertEqual(status, 200)
            self.assertGreater(int(headers["Content-Length"]), 0)
            self.assertFalse(body)
        for path in ("/private/review.sqlite3", "/packages/content/schema.sql", "/assets/../index.html"):
            self.assertEqual(client.request(path)[0], 404)
        self.assertEqual(client.request("/contact", {"message": "Synthetic enquiry"})[0], 405)

    def test_institutional_seed_requires_a_publishing_decision(self):
        client = self.client()
        for path in ("/", "/journal", "/opportunities"):
            body = client.request(path)[2]
            self.assertNotIn("How the parts of Safwa work together", body)
            self.assertNotIn('class="platform-card"', body)
        self.assertIn("Research", client.request("/institute")[2])
        self.assertIn("Publishing", client.request("/studios")[2])
        self.assertIn("Safwa OS", client.request("/portfolio")[2])
        self.assertIn('data-enquiry-delivery="email"', client.request("/contact")[2])

    def test_edit_review_publish_supersede_and_archive(self):
        public = self.client()
        editor, _, _ = self.staff("workflow-editor", "editor", "institute")
        reviewer, _, _ = self.staff("workflow-reviewer", "reviewer", "institute")
        publisher, _, _ = self.staff("workflow-publisher", "publisher", "institute")
        outsider, _, _ = self.staff("workflow-outsider", "reviewer", "studios")
        operator, _, _ = self.staff("workflow-admin", "admin", None)
        self.assertEqual(public.request("/editor")[1]["Location"], "/editor/sign-in")
        self.assertNotIn("Safwa Quran", editor.request("/editor")[2])
        self.assertIn("Safwa Quran", operator.request("/editor")[2])
        self.assertEqual(editor.request("/editor/audit")[0], 403)
        self.assertEqual(editor.request("/editor/new?kind=project")[0], 403)
        new_path = "/editor/new?kind=activity"
        form = {
            "kind": "activity", "slug": "synthetic-session",
            "title": "Synthetic session", "summary": "A review fixture",
            "body": "<script>Review fixture</script>\n\nA second paragraph.",
            "status": "planned", "media": "",
        }
        csrf = editor.token(new_path)
        rejected, _, echoed = editor.request("/editor/new", dict(form, csrf=csrf, media="../../outside"))
        self.assertEqual(rejected, 422)
        self.assertIn("Synthetic session", echoed)
        result, headers, _ = editor.request("/editor/new", dict(form, csrf=csrf))
        self.assertEqual(result, 303)
        entry = headers["Location"]
        url = "/institute/learning/synthetic-session"
        self.assertEqual(public.request(url)[0], 404)
        self.assertNotIn("Synthetic session", public.request("/institute")[2])
        self.assertEqual(outsider.request(entry)[0], 403)

        def act(client, version, action, **fields):
            payload = {"csrf": client.token(entry), "version": version, "action": action, **fields}
            return client.request(entry, payload)[0]

        self.assertEqual(act(editor, 1, "publish"), 403)
        self.assertEqual(act(operator, 1, "approve"), 403)
        self.assertEqual(act(editor, 1, "submit"), 303)
        self.assertEqual(outsider.request(entry, {"csrf": outsider.token("/editor"),
                                                  "version": 2, "action": "approve"})[0], 403)
        self.assertEqual(act(reviewer, 2, "return"), 422)
        self.assertEqual(act(reviewer, 2, "return", note="Clarify the example."), 303)
        self.assertEqual(act(editor, 3, "submit"), 303)
        self.assertEqual(act(reviewer, 4, "approve"), 303)
        self.assertEqual(public.request(url)[0], 404)
        self.assertEqual(act(publisher, 5, "publish"), 303)
        code, _, body = public.request(url)
        self.assertEqual(code, 200)
        self.assertIn("&lt;script&gt;Review fixture&lt;/script&gt;", body)
        self.assertNotIn("<script>Review fixture</script>", body)
        self.assertIn("Synthetic session", public.request("/institute")[2])

        update = dict(form, title="Synthetic revision two")
        self.assertEqual(act(editor, 6, "save", **update), 303)
        self.assertEqual(act(editor, 6, "save", **update), 409)
        self.assertNotIn("Synthetic revision two", public.request(url)[2])
        working_page = editor.request(entry)[2]
        self.assertIn("Working revision 2 · Public revision 1", working_page)
        self.assertEqual(act(editor, 7, "submit"), 303)
        self.assertEqual(act(reviewer, 8, "approve"), 303)
        self.assertEqual(act(publisher, 9, "publish"), 303)
        self.assertIn("Synthetic revision two", public.request(url)[2])

        self.assertEqual(act(editor, 10, "save", **dict(form, title="Synthetic private revision three")), 303)
        self.assertEqual(act(publisher, 11, "archive", note="End test publication."), 303)
        self.assertEqual(public.request(url)[0], 404)
        self.assertNotIn("Synthetic private revision three", public.request("/institute")[2])
        self.assertIn("End test publication.", operator.request("/editor/audit")[2])
        self.assertIn("Synthetic private revision three", operator.request(entry)[2])

    def test_authentication_replay_origin_and_revocation(self):
        editor, password, code = self.staff("auth-fixture", "editor", "parent")
        self.assertEqual(self.client().login("auth-fixture", password, code)[0], 401)
        self.assertEqual(editor.request("/editor/sign-out", {"csrf": "bad"})[0], 403)
        payload = {"csrf": editor.token("/editor")}
        self.assertEqual(editor.request("/editor/sign-out", payload, headers={"Origin": "https://elsewhere.invalid"})[0], 403)
        self.assertEqual(editor.request("/editor/sign-out", payload, headers={"Host": "elsewhere.invalid"})[0], 400)
        self.assertEqual(editor.request("/editor")[0], 200)
        with store.transaction(self.database, write=True) as db:
            auth.revoke_user(db, "auth-fixture")
        self.assertEqual(editor.request("/editor")[0], 303)

    def test_rate_limit_and_session_expiry(self):
        name = "ratelimit-fixture"
        password = secrets.token_urlsafe(24)
        start = 1_750_000_020
        with store.transaction(self.database, write=True) as db:
            auth.create_user(db, name, "editor", "parent", password)
            key = decrypt(db, db.execute("SELECT otp_key FROM users WHERE name = ?", (name,)).fetchone()[0])
            for _ in range(auth.MAX_FAILURES_PER_ACCOUNT):
                self.assertEqual(auth.sign_in(db, name, "incorrect", "000000", now=start), (None, False))
            self.assertEqual(auth.sign_in(db, name, password, auth.totp(key, start // 30), now=start), (None, True))
            later = start + auth.LOGIN_WINDOW
            token, limited = auth.sign_in(db, name, password, auth.totp(key, later // 30), now=later)
            self.assertFalse(limited)
            self.assertIsNotNone(auth.session(db, token, now=later))
            self.assertIsNone(auth.session(db, token, now=later + auth.SESSION_SECONDS))

    def test_backup_and_restore(self):
        editor, _, _ = self.staff("backup-editor", "editor", "parent")
        token = editor.token("/editor/new?kind=article")
        status, _, _ = editor.request("/editor/new", {
            "csrf": token, "kind": "article", "slug": "backup-fixture", "title": "Backup fixture",
            "summary": "A private note for the restore exercise.", "body": "Synthetic text.",
            "status": "note", "media": "",
        })
        self.assertEqual(status, 303)
        backup = self.directory / "backup.sqlite3"
        restored = self.directory / "restored.sqlite3"
        store.copy_database(self.database, backup)
        store.copy_database(backup, restored, restore=True)
        with store.transaction(self.database) as live, store.transaction(restored) as copy:
            for table in ("entries", "revisions", "public_content"):
                self.assertEqual(live.execute(f"SELECT * FROM {table}").fetchall(),
                                 copy.execute(f"SELECT * FROM {table}").fetchall())
            self.assertGreater(live.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
            self.assertEqual(copy.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
            self.assertFalse(store.published_entries(copy, kind="article", slug="backup-fixture"))
            self.assertEqual(copy.execute("SELECT state FROM entries WHERE slug = ?", ("backup-fixture",)).fetchone()[0], "draft")
            self.assertEqual(copy.execute("SELECT action FROM audit ORDER BY id DESC LIMIT 1").fetchone()[0], "restore")
        self.assertEqual(restored.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(Invalid):
            store.copy_database(backup, restored, restore=True)

    def test_totp_standard_vectors(self):
        # RFC 6238 Appendix B test vectors for the interoperable SHA-1 profile.
        key = b"12345678901234567890"
        self.assertEqual(auth.totp(key, 59 // 30, digits=8), "94287082")
        self.assertEqual(auth.totp(key, 20000000000 // 30, digits=8), "65353130")
