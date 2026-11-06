"""Remote-launcher checks; no ngrok account or external connection is used."""
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest import TestCase
from unittest.mock import patch

from packages.content import store
from packages.content.contracts import Invalid
from packages.security import remote_access as remote


AGENT_STAND_IN = '''#!/usr/bin/env python3
import json, os, pathlib, sys, time
config = json.loads(pathlib.Path(sys.argv[sys.argv.index('--config') + 1]).read_text())
assert 'authtoken' not in config['agent']
assert os.environ.get('NGROK_AUTHTOKEN')
assert not any(key.startswith('NGROK_') and key != 'NGROK_AUTHTOKEN' for key in os.environ)
if sys.argv[1:3] == ['config', 'check']:
    sys.exit(1 if os.environ.get('SYNTHETIC_AGENT_FAIL_CHECK') else 0)
assert sys.argv[1:3] == ['start', 'safwa-cms']
pathlib.Path(os.environ['SYNTHETIC_AGENT_EVENT']).write_text(json.dumps(dict(pid=os.getpid(), config=config)))
if os.environ.get('SYNTHETIC_AGENT_FAIL_START'):
    print('ERR_NGROK_12345 ' + os.environ['NGROK_AUTHTOKEN'], file=sys.stderr)
    sys.exit(1)
while True:
    time.sleep(0.05)
'''


class RemoteConfigurationTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'private/remote/access.json'
        self.settings = dict(version=1, origin='https://synthetic-review.ngrok-free.dev',
                             emails=['owner@example.test', 'editor@example.test'], port=4173)

    def test_unsafe_origins_and_non_explicit_identity_grants_are_rejected(self):
        for origin in ('http://synthetic.ngrok-free.dev', 'https://localhost',
                       'https://synthetic.ngrok-free.dev.evil.test', 'https://user@synthetic.ngrok-free.dev',
                       'https://synthetic.ngrok-free.dev/editor', 'https://synthetic.ngrok-free.dev:443',
                       'https://synthetic.ngrok-free.dev?x=1', 'https://synthetic.ngrok-free.dev#x'):
            with self.subTest(origin=origin), self.assertRaises(Invalid):
                remote.validate(dict(self.settings, origin=origin))
        for emails in ([], ['*'], ['*@example.test'], ['example.test'], ['a@example.test\n'],
                       ['a@example.test', 'A@example.test'], ['a\"@example.test'],
                       [f'user{i}@example.test' for i in range(4)]):
            with self.subTest(emails=emails), self.assertRaises(Invalid):
                remote.validate(dict(self.settings, emails=emails))
        for port in (True, 22, 0, 65536, '4173'):
            with self.subTest(port=port), self.assertRaises(Invalid):
                remote.validate(dict(self.settings, port=port))
        with self.assertRaises(Invalid):
            remote.validate(dict(self.settings, traffic_policy={}))

    def test_settings_are_private_and_symlink_or_shared_settings_cannot_be_loaded(self):
        remote.save_settings(self.settings, self.path)
        self.assertEqual(remote.read_settings(self.path), self.settings)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        self.path.chmod(0o644)
        with self.assertRaises(Invalid):
            remote.read_settings(self.path)
        self.path.chmod(0o600)
        original = self.path.with_name('original.json')
        self.path.rename(original)
        self.path.symlink_to(original)
        with self.assertRaises(OSError):
            remote.read_settings(self.path)
        self.path.unlink()
        self.path.parent.chmod(0o755)
        with self.assertRaises(Invalid):
            remote.read_settings(self.path)

    def test_active_session_prevents_configuration_replacement(self):
        remote.save_settings(self.settings, self.path)
        with remote.session_lock(self.path.parent):
            with self.assertRaises(Invalid):
                remote.save_settings(dict(self.settings, emails=['replacement@example.test']), self.path)
        self.assertEqual(remote.read_settings(self.path), self.settings)

    def test_missing_or_non_interactive_setup_does_not_start_any_process(self):
        with patch.object(sys.stdin, 'isatty', return_value=False), patch.object(remote.subprocess, 'Popen') as start:
            with self.assertRaises(Invalid):
                remote.configure(4173)
            start.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_occupied_port_is_refused_before_asking_for_a_token(self):
        with socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0))
            remote.save_settings(dict(self.settings, port=occupied.getsockname()[1]), self.path)
            with patch.object(remote, 'interactive'), patch.object(remote.shutil, 'which', return_value='/synthetic/ngrok'), \
                 patch.object(remote, 'getpass') as prompt, patch.object(remote.subprocess, 'Popen') as start:
                with self.assertRaises(Invalid):
                    remote.launch(self.root/'unused.sqlite3', path=self.path)
                prompt.assert_not_called()
                start.assert_not_called()


class RemoteRuntimeTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'private/remote/access.json'
        self.database = self.root / 'synthetic.sqlite3'
        store.initialize(self.database)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        remote.save_settings(dict(version=1, origin='https://synthetic-review.ngrok-free.dev',
                                  emails=['owner@example.test'], port=self.port), self.path)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        agent = self.bin / 'ngrok'
        agent.write_text(AGENT_STAND_IN)
        agent.chmod(0o700)
        self.event = self.root / 'synthetic-agent-event.json'
        self.environment = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
                                SYNTHETIC_AGENT_EVENT=str(self.event), NGROK_URL='https://unapproved.invalid')

    def start(self, **extra):
        driver = '''
from pathlib import Path
import sys
from unittest.mock import patch
from packages.security import remote_access
from packages.content.contracts import Invalid
with patch.object(remote_access, 'interactive'), patch.object(remote_access, 'getpass', return_value='test-only-agent-token-0123456789'):
    try:
        remote_access.launch(Path(sys.argv[1]), path=Path(sys.argv[2]))
    except Invalid as error:
        print(str(error))
        sys.exit(1)
'''
        log_path = self.root / 'driver.log'
        self.log = log_path.open('w+')
        self.addCleanup(self.log.close)
        process = subprocess.Popen([sys.executable, '-c', driver, str(self.database), str(self.path)],
                                   cwd=remote.ROOT, env=dict(self.environment, **extra),
                                   stdout=self.log, stderr=self.log)
        self.addCleanup(remote.stop, process)
        return process

    def await_event(self, process):
        deadline = time.monotonic() + 10
        while not self.event.exists():
            if process.poll() is not None or time.monotonic() >= deadline:
                self.log.seek(0)
                self.fail('Local agent stand-in did not start: '+self.log.read())
            time.sleep(0.05)
        return json.loads(self.event.read_text())

    def assert_port_closed(self):
        with socket.socket() as probe:
            probe.settimeout(1)
            self.assertNotEqual(probe.connect_ex(('127.0.0.1', self.port)), 0)

    def test_real_wsgi_remote_boundary_and_owner_stop_cleanup(self):
        process = self.start()
        event = self.await_event(process)
        endpoint = event['config']['endpoints'][0]
        policy = endpoint['traffic_policy']['on_http_request']
        self.assertEqual(policy[0]['actions'][0]['type'], 'oauth')
        self.assertIn('!(actions.ngrok.oauth.identity.email in ["owner@example.test"])', policy[1]['expressions'])
        self.assertEqual(policy[1]['actions'][0]['type'], 'deny')
        self.assertEqual(endpoint['upstream']['url'], f'http://127.0.0.1:{self.port}')
        self.assertEqual(event['config']['agent']['inspect_db_size'], -1)
        self.assertEqual(event['config']['agent']['web_addr'], 'false')
        connection = HTTPConnection('127.0.0.1', self.port, timeout=2)
        try:
            connection.request('GET', '/editor/sign-in', headers={'Host':'synthetic-review.ngrok-free.dev'})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn('; Secure', response.getheader('Set-Cookie'))
            response.read()
            connection.request('GET', '/editor/sign-in')
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            connection.close()
        process.send_signal(signal.SIGINT)
        self.assertEqual(process.wait(timeout=10), 0)
        self.assert_port_closed()
        with self.assertRaises(ProcessLookupError):
            os.kill(event['pid'], 0)
        self.assertEqual(list(self.path.parent.glob('session-*')), [])
        self.assertNotIn('test-only-agent-token', self.path.read_text())

    def test_agent_failure_closes_cms_and_redacts_diagnostic_output(self):
        process = self.start(SYNTHETIC_AGENT_FAIL_START='1')
        self.assertEqual(process.wait(timeout=10), 1)
        self.assertTrue(self.event.exists())
        self.assert_port_closed()
        self.log.seek(0)
        output = self.log.read()
        self.assertIn('ERR_NGROK_12345', output)
        self.assertNotIn('test-only-agent-token', output)
        self.assertEqual(list(self.path.parent.glob('session-*')), [])

    def test_terminal_hangup_stops_both_child_processes(self):
        process = self.start()
        event = self.await_event(process)
        process.send_signal(signal.SIGHUP)
        self.assertEqual(process.wait(timeout=10), 0)
        self.assert_port_closed()
        with self.assertRaises(ProcessLookupError):
            os.kill(event['pid'], 0)

    def test_rejected_agent_config_never_starts_cms_or_endpoint(self):
        process = self.start(SYNTHETIC_AGENT_FAIL_CHECK='1')
        self.assertEqual(process.wait(timeout=10), 1)
        self.assertFalse(self.event.exists())
        self.assert_port_closed()
