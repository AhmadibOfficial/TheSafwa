"""CMS acceptance and security checks using synthetic records and ephemeral databases."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import secrets
import sqlite3
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from PIL import Image, PngImagePlugin

from apps.parent.server import ReviewServer, SESSION
from apps.parent.wsgi import Application
from packages.content import media, migrations, page_content, store
from packages.content.contracts import Conflict, Forbidden, Invalid
from packages.security import auth, vault
from test_review_system import Client


class SQLiteCMSTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.database = self.directory / 'cms.sqlite3'
        store.initialize(self.database)
        self.server = ReviewServer(0, self.database)
        self.addCleanup(self.server.server_close)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def client(self):
        return Client(self.server.server_port)

    def user(self, name, role='editor', arm='parent'):
        password = secrets.token_urlsafe(24)
        with store.transaction(self.database, write=True) as db:
            uri = auth.create_user(db, name, role, arm, password)
        key = parse_qs(urlsplit(uri).query)['secret'][0]
        import base64
        raw = base64.b32decode(key)
        client = self.client()
        self.assertEqual(client.login(name, password, auth.totp(raw, int(time.time())//30))[0], 303)
        return client, password, raw

    @staticmethod
    def fields(**extra):
        return dict(kind='article', slug='synthetic-article', title='Synthetic article',
                    summary='Synthetic summary.', body='Synthetic body.', status='note', media='', **extra)

    def act(self, client, path, action, **fields):
        with store.transaction(self.database) as db:
            version = db.execute('SELECT version FROM entries WHERE id = ?', (path.rsplit('/',1)[1],)).fetchone()[0]
        return client.request(path, dict(csrf=client.token(path), version=version, action=action, **fields))

    def test_all_approved_page_bodies_are_preserved(self):
        client = self.client()
        with store.transaction(self.database) as db:
            self.assertEqual(len(store.published_entries(db, kind='page')), 9)
        for path, key in page_content.BY_PATH.items():
            code, _, html = client.request(path)
            self.assertEqual(code, 200)
            # Internal links are normalized by the already-approved public builder.
            from scripts.build import clean_link
            expected = re.sub(r'href="([^"]+)"', clean_link, page_content.template(key)[0])
            self.assertIn(expected, html)
            self.assertNotRegex(html, '[←→↗↘↓↑]')

    def test_page_drafts_review_publish_restore_and_scope(self):
        editor, _, _ = self.user('page-editor')
        reviewer, _, _ = self.user('page-reviewer', 'reviewer')
        publisher, _, _ = self.user('page-publisher', 'publisher')
        outsider, _, _ = self.user('page-outsider', 'editor', 'institute')
        with store.transaction(self.database) as db:
            item = dict(db.execute("SELECT * FROM entries WHERE kind = 'page' AND slug = 'home'").fetchone())
        path = f'/editor/entries/{item["id"]}'
        blocks = page_content.defaults('home')
        key = next(s['key'] for s in page_content.template('home')[1] if s['text'] == 'Building institutions')
        blocks[key] = 'Synthetic <script>page revision</script>'
        form = dict(title='Synthetic page title', summary='Synthetic page description', **blocks)
        self.assertEqual(outsider.request(path)[0], 403)
        self.assertEqual(self.act(editor, path, 'save', **form)[0], 303)
        public = self.client()
        self.assertNotIn('Synthetic page title', public.request('/')[2])
        self.assertEqual(public.request(path+'/preview')[0], 303)
        preview = editor.request(path+'/preview')[2]
        self.assertIn('Synthetic &lt;script&gt;page revision&lt;/script&gt;', preview)
        self.assertNotIn('<script>page revision</script>', preview)
        self.assertEqual(self.act(editor, path, 'submit')[0], 303)
        self.assertEqual(self.act(publisher, path, 'publish')[0], 403)
        self.assertEqual(self.act(reviewer, path, 'approve')[0], 303)
        self.assertEqual(self.act(publisher, path, 'publish')[0], 303)
        self.assertIn('Synthetic page title', public.request('/')[2])
        self.assertEqual(self.act(publisher, path, 'archive', note='Synthetic reason')[0], 422)
        self.assertEqual(self.act(editor, path, 'restore', revision='1')[0], 303)
        self.assertIn('Synthetic page title', public.request('/')[2])
        self.assertIn('Building institutions', editor.request(path+'/preview')[2])
        with store.transaction(self.database) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM revisions WHERE entry_id = ?', (item['id'],)).fetchone()[0], 3)

    def test_media_upload_publication_private_access_and_backup(self):
        editor, _, _ = self.user('media-editor')
        reviewer, _, _ = self.user('media-reviewer', 'reviewer')
        publisher, _, _ = self.user('media-publisher', 'publisher')
        other, _, _ = self.user('media-outsider', 'editor', 'institute')
        image = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Comment', 'Synthetic metadata must be removed')
        Image.new('RGB', (80, 60), 'green').save(image, 'PNG', pnginfo=metadata)
        csrf = editor.token('/editor/media')
        boundary = 'synthetic-upload-boundary'
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="csrf"\r\n\r\n{csrf}\r\n'
                   f'--{boundary}\r\nContent-Disposition: form-data; name="alt"\r\n\r\nSynthetic green image\r\n'
                   f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="ignored.png"\r\nContent-Type: image/png\r\n\r\n').encode() + image.getvalue() + f'\r\n--{boundary}--\r\n'.encode()
        headers = {'Content-Type': 'multipart/form-data; boundary='+boundary}
        self.assertEqual(editor.request('/editor/media', payload, headers=headers)[0], 303)
        with store.transaction(self.database) as db:
            row = dict(db.execute('SELECT * FROM media').fetchone())
        self.assertNotIn(b'Synthetic metadata', row['data'])
        public = self.client()
        url = '/media/'+row['id']
        self.assertEqual(public.request(url)[0], 404)
        self.assertEqual(other.request('/editor'+url)[0], 403)
        self.assertEqual(editor.request('/editor'+url, method='HEAD')[0], 200)
        form = self.fields()
        form['media'] = 'upload:'+row['id']
        code, head, _ = editor.request('/editor/new', dict(form, csrf=editor.token('/editor/new?kind=article')))
        self.assertEqual(code, 303)
        record = head['Location']
        self.assertIn('Synthetic green image', editor.request(record+'/preview')[2])
        self.assertIn('src="/editor/media/', editor.request(record+'/preview')[2])
        for person, action in ((editor, 'submit'), (reviewer, 'approve'), (publisher, 'publish')):
            self.assertEqual(self.act(person, record, action)[0], 303)
        self.assertEqual(public.request(url, method='HEAD')[0], 200)
        self.assertIn('Synthetic green image', public.request('/journal/synthetic-article')[2])
        backup = self.directory/'media-backup.sqlite3'
        restored = self.directory/'media-restored.sqlite3'
        store.copy_database(self.database, backup)
        store.copy_database(backup, restored, restore=True)
        with store.transaction(restored) as db:
            self.assertEqual(media.get(db, row['id'])['data'], row['data'])
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0], 0)
            self.assertEqual(len(vault.decrypt(db, db.execute('SELECT otp_key FROM users LIMIT 1').fetchone()[0])), 20)
        self.assertEqual(self.act(publisher, record, 'archive', note='Synthetic withdrawal')[0], 303)
        self.assertEqual(public.request(url)[0], 404)

    def test_invalid_images_and_cross_arm_references_are_rejected(self):
        editor, _, _ = self.user('invalid-image-editor')
        with store.transaction(self.database, write=True) as db:
            user = dict(db.execute('SELECT * FROM users WHERE name = ?', ('invalid-image-editor',)).fetchone())
            for raw in (b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'<script>synthetic</script>', b'\x89PNG\r\n', b'x'*(media.MAX_UPLOAD+1)):
                with self.assertRaises(Invalid):
                    media.upload(db, user, raw, 'Synthetic image')
            stream = BytesIO()
            Image.new('RGB',(10,10),'red').save(stream,'JPEG')
            identifier = media.upload(db, user, stream.getvalue(), 'Synthetic description')
            other = dict(user, name='other-fixture', arm='institute')
            fields = self.fields()
            fields['media'] = 'upload:'+identifier
            with self.assertRaises(Invalid):
                store.create(db, other, fields)
        self.assertEqual(editor.request('/editor/media', b'bad upload', headers={'Content-Type':'multipart/form-data; boundary=bad'})[0],400)

    def test_quran_project_uses_the_published_project_revision(self):
        editor, _, _ = self.user('quran-editor', arm='studios')
        reviewer, _, _ = self.user('quran-reviewer', 'reviewer', 'studios')
        publisher, _, _ = self.user('quran-publisher', 'publisher', 'studios')
        with store.transaction(self.database) as db:
            item = db.execute("SELECT id FROM entries WHERE kind='project' AND slug='safwa-quran'").fetchone()
        record = f'/editor/entries/{item[0]}'
        fields = dict(title='Safwa Quran',summary='Synthetic project update',body='Synthetic project body.',status='development',media='')
        self.assertEqual(self.act(editor,record,'save',**fields)[0],303)
        public = self.client()
        self.assertNotIn('Synthetic project body.',public.request('/studios/quran')[2])
        for person,action in ((editor,'submit'),(reviewer,'approve'),(publisher,'publish')):
            self.assertEqual(self.act(person,record,action)[0],303)
        self.assertIn('Synthetic project body.',public.request('/studios/quran')[2])
        self.assertEqual(public.request('/work/safwa-quran')[1]['Location'],'/studios/quran')

    def test_staff_creation_passphrase_change_and_permission_revocation(self):
        operator, _, _ = self.user('staff-admin', 'admin', None)
        editor, _, _ = self.user('staff-editor')
        self.assertEqual(editor.request('/editor/staff')[0], 403)
        temporary = secrets.token_urlsafe(24)
        code, _, html = operator.request('/editor/staff', dict(csrf=operator.token('/editor/staff'), action='create', name='new-staff', role='editor', arm='parent', temporary=temporary))
        self.assertEqual(code, 200)
        secret = re.search(r'class="editor-secret">([A-Z2-7]+)</code>',html)[1]
        import base64
        key = base64.b32decode(secret)
        newcomer = self.client()
        self.assertEqual(newcomer.login('new-staff',temporary,auth.totp(key,int(time.time())//30))[0],303)
        self.assertEqual(newcomer.request('/editor')[1]['Location'],'/editor/account')
        self.assertEqual(newcomer.request('/editor/new',dict(self.fields(),csrf=newcomer.token('/editor/account')))[0],403)
        new = secrets.token_urlsafe(24)
        self.assertEqual(newcomer.request('/editor/account',dict(csrf=newcomer.token('/editor/account'),action='password',current=temporary,new=new,confirm=new))[0],303)
        later = int(time.time())+31
        with patch('packages.security.auth.time.time',return_value=later):
            self.assertEqual(newcomer.login('new-staff',new,auth.totp(key,later//30))[0],303)
        self.assertEqual(newcomer.request('/editor')[0],200)
        self.assertNotIn(secret,operator.request('/editor/staff')[2])
        self.assertEqual(operator.request('/editor/staff',dict(csrf=operator.token('/editor/staff'),action='permissions',name='new-staff',role='reviewer',arm='institute',active='0'))[0],303)
        self.assertEqual(newcomer.request('/editor')[1]['Location'],'/editor/sign-in')
        self.assertEqual(operator.request('/editor/staff',dict(csrf=operator.token('/editor/staff'),action='permissions',name='staff-admin',role='editor',arm='parent',active='0'))[0],422)

    def test_recovery_codes_are_one_use_and_key_is_encrypted(self):
        client, password, rawkey = self.user('recovery-user')
        code, _, html = client.request('/editor/account',dict(csrf=client.token('/editor/account'),action='recovery',current=password))
        self.assertEqual(code,200)
        codes = re.findall(r'<li><code>([A-F0-9]{16})</code></li>',html)
        self.assertEqual(len(codes),8)
        with store.transaction(self.database, write=True) as db:
            encrypted = db.execute('SELECT otp_key FROM users WHERE name=?',('recovery-user',)).fetchone()[0]
            self.assertNotEqual(encrypted,rawkey)
            token, limited = auth.sign_in(db,'recovery-user',password,codes[0])
            self.assertIsNotNone(token)
            self.assertFalse(limited)
            self.assertEqual(auth.sign_in(db,'recovery-user',password,codes[0]),(None,False))
            stored = db.execute('SELECT code_hash FROM recovery_codes').fetchone()[0]
            self.assertNotEqual(stored,codes[1].encode())
        with self.assertRaises(Invalid):
            with store.transaction(self.database, write=True) as db:
                auth.change_password(db, {'name':'recovery-user'}, 'incorrect', secrets.token_urlsafe(24))

    def test_simultaneous_writes_produce_one_revision_and_one_conflict(self):
        self.user('concurrent-editor')
        with store.transaction(self.database,write=True) as db:
            user = dict(db.execute("SELECT * FROM users WHERE name='concurrent-editor'").fetchone())
            identifier = store.create(db,user,self.fields())
        def save(_):
            try:
                with store.transaction(self.database,write=True) as db:
                    store.change(db,user,identifier,dict(self.fields(),title='Concurrent synthetic update',action='save',version='1'))
                return 'saved'
            except Conflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertCountEqual(workers.map(save,range(2)),['saved','conflict'])
        with store.transaction(self.database) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM revisions WHERE entry_id=?',(identifier,)).fetchone()[0],2)

    def test_https_wsgi_origin_secure_cookie_and_csrf(self):
        app = Application(self.database,'https://cms.example.test')
        def request(path='/', *, host='cms.example.test', method='GET', data=None, headers=None):
            raw = urlencode(data or {}).encode()
            env = {'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','HTTP_HOST':host,
                   'wsgi.input':BytesIO(raw),'wsgi.errors':StringIO(),'CONTENT_LENGTH':str(len(raw)),
                   'CONTENT_TYPE':'application/x-www-form-urlencoded',**(headers or {})}
            result={}
            body=b''.join(app(env,lambda status,values:result.update(status=int(status.split()[0]),headers=values)))
            return result,body.decode()
        result,html=request('/editor/sign-in')
        self.assertEqual(result['status'],200)
        cookie=next(v for k,v in result['headers'] if k=='Set-Cookie')
        self.assertIn('; Secure',cookie)
        self.assertIn('https://cms.example.test/', request('/')[1])
        csrf=re.search(r'name="csrf" value="([^"]+)"',html)[1]
        response,_=request('/editor/sign-in',method='POST',data={'csrf':csrf,'username':'synthetic','password':'incorrect','code':'000000'},
                           headers={'HTTP_COOKIE':cookie.split(';')[0],'HTTP_ORIGIN':'https://cms.example.test'})
        self.assertEqual(response['status'],401)
        response,_=request('/editor/sign-in',method='POST',data={'csrf':csrf},headers={'HTTP_ORIGIN':'https://outside.invalid'})
        self.assertEqual(response['status'],403)
        self.assertEqual(request(host='outside.invalid')[0]['status'],400)
        self.assertEqual(request(method='PUT')[0]['status'],405)
        with self.assertRaises(Invalid):
            Application(self.database,'http://public.example.test')


class MigrationTests(TestCase):
    def test_v1_migration_preserves_history_and_backup_and_encrypts_seeds(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            path,backup=root/'legacy.sqlite3',root/'before-v2.sqlite3'
            rawkey=secrets.token_bytes(20)
            password=secrets.token_urlsafe(24)
            salt=secrets.token_bytes(16)
            schema=(Path(__file__).parent/'fixtures/schema_v1.sql').read_text()
            with closing(sqlite3.connect(path)) as db:
                db.executescript(schema)
                db.execute(f'PRAGMA application_id={store.APPLICATION_ID}')
                db.execute('PRAGMA user_version=1')
                db.execute('INSERT INTO users(name,role,arm,password_hash,salt,otp_key) VALUES(?,?,?,?,?,?)',
                           ('legacy-editor','editor','parent',auth.password_hash(password,salt),salt,rawkey))
                db.execute("INSERT INTO entries VALUES(1,'parent','article','legacy-note','published',1,1,1)")
                db.execute("INSERT INTO revisions(entry_id,number,title,summary,body,status,media,author) VALUES(1,1,'Legacy note','Legacy summary','Legacy body','note','','legacy-editor')")
                db.execute("INSERT INTO audit(entry_id,revision,actor,action,note) VALUES(1,1,'legacy-editor','publish','Original decision')")
                db.commit()
            migrations.migrate(path,backup)
            with store.transaction(path,write=True) as db:
                store.check_identity(db)
                self.assertEqual(store.published_entries(db,kind='article')[0]['body'],'Legacy body')
                self.assertEqual(len(store.published_entries(db,kind='page')),9)
                encrypted=db.execute('SELECT otp_key FROM users').fetchone()[0]
                self.assertNotEqual(encrypted,rawkey)
                self.assertEqual(vault.decrypt(db,encrypted),rawkey)
                token,limited=auth.sign_in(db,'legacy-editor',password,auth.totp(rawkey,int(time.time())//30))
                self.assertIsNotNone(token)
                self.assertFalse(limited)
                self.assertFalse(db.execute('PRAGMA foreign_key_check').fetchall())
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT otp_key FROM users').fetchone()[0],rawkey)
            with self.assertRaises(Invalid):
                migrations.migrate(path,root/'unneeded.sqlite3')


class ProductionRuntimeTests(TestCase):
    def test_waitress_launches_the_actual_cli_and_serves_the_cms(self):
        with TemporaryDirectory() as directory:
            database=Path(directory)/'runtime.sqlite3'
            store.initialize(database)
            with socket.socket() as reserved:
                reserved.bind(('127.0.0.1',0))
                port=reserved.getsockname()[1]
            root=Path(__file__).resolve().parents[1]
            process=subprocess.Popen([sys.executable,str(root/'scripts/cms.py'),'--database',str(database),
                                      'serve','--host','127.0.0.1','--port',str(port),
                                      '--origin',f'http://127.0.0.1:{port}'],
                                     cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                client=Client(port)
                deadline=time.monotonic()+8
                while True:
                    try:
                        result=client.request('/healthz')
                        break
                    except OSError:
                        if process.poll() is not None or time.monotonic()>deadline:
                            self.fail('The production WSGI service did not start.')
                        time.sleep(0.05)
                self.assertEqual(result[0],200)
                self.assertEqual(client.request('/editor/sign-in')[0],200)
                self.assertIn(f'http://127.0.0.1:{port}/',client.request('/')[2])
                self.assertEqual(client.request('/private/cms.key')[0],404)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
