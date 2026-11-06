"""Owner-started remote CMS sessions through an email-restricted ngrok endpoint."""
from contextlib import contextmanager
import fcntl
from getpass import getpass
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
import time

from packages.config.review import PRIVATE, ROOT
from packages.content.contracts import Invalid, Missing

DIRECTORY = PRIVATE / 'remote'
SETTINGS = DIRECTORY / 'access.json'
DOMAIN = re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.ngrok-free\.(?:app|dev)/?', re.ASCII)
EMAIL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._%+-]{0,63}@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+', re.ASCII)


def validate(settings):
    if not isinstance(settings, dict) or set(settings) != {'version', 'origin', 'emails', 'port'}:
        raise Invalid('Remote settings must contain only version, origin, emails and port.')
    origin, emails, port = settings['origin'], settings['emails'], settings['port']
    if type(settings['version']) is not int or settings['version'] != 1:
        raise Invalid('Unsupported remote settings version.')
    if not isinstance(origin, str) or not DOMAIN.fullmatch(origin):
        raise Invalid('Use the exact HTTPS dev domain assigned in your ngrok dashboard, without a path or port.')
    if not isinstance(emails, list) or not 1 <= len(emails) <= 3:
        raise Invalid('Enter one to three approved Google sign-in email addresses, including your own.')
    if any(not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email) for email in emails):
        raise Invalid('Each permitted identity must be a complete email address. Wildcards are not accepted.')
    if len({email.lower() for email in emails}) != len(emails):
        raise Invalid('List each permitted email address once.')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise Invalid('Use a local port between 1024 and 65535.')
    return dict(version=1, origin=origin.rstrip('/'), emails=list(emails), port=port)


def private_directory(directory):
    """Never follow a substituted private directory or make a shared one writable."""
    for path in (directory.parent, directory):
        path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise Invalid('Remote configuration requires owner-only directories. Check private/ and private/remote/.')


def read_settings(path=SETTINGS):
    private_directory(path.parent)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise Missing('Run bash safwa remote-setup on the host computer first.') from None
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise Invalid('Remote settings must be an owner-only regular file (mode 600).')
        if info.st_size > 16384:
            raise Invalid('Remote settings exceed the permitted size.')
        try:
            settings = json.loads(stream.read(16385))
        except (json.JSONDecodeError, UnicodeError):
            raise Invalid('Remote settings are invalid. Run bash safwa remote-setup again.') from None
        return validate(settings)


@contextmanager
def session_lock(directory):
    private_directory(directory)
    descriptor = os.open(directory / 'session.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise Invalid('Remote session lock must be an owner-only regular file.')
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Invalid('A remote session is already running. Stop it before changing access or starting another.') from None
        yield


def save_settings(settings, path=SETTINGS):
    settings = validate(settings)
    with session_lock(path.parent):
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), 0o600)
                json.dump(settings, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def interactive():
    if not sys.stdin.isatty():
        raise Invalid('Run remote setup and sessions in an interactive terminal on your own computer.')


def configure(port):
    interactive()
    print('Use your assigned HTTPS dev domain from https://dashboard.ngrok.com/domains .')
    origin = input('Assigned HTTPS address: ').strip()
    print('Enter the exact Google sign-in addresses, separated by commas. Include your own; maximum three.')
    emails = [email.strip() for email in input('Approved email addresses: ').split(',')]
    save_settings(dict(version=1, origin=origin, emails=emails, port=port))
    print('Access settings saved privately. No tunnel has been started. Run: bash safwa remote')


def agent_config(settings):
    settings = validate(settings)
    allowed = json.dumps(settings['emails'], ensure_ascii=True)
    return {
        'version': '3',
        'agent': {'web_addr': 'false', 'console_ui': 'false', 'inspect_db_size': -1,
                  'remote_management': False, 'log': 'false'},
        'endpoints': [{
            'name': 'safwa-cms', 'url': settings['origin'],
            'upstream': {'url': f'http://127.0.0.1:{settings["port"]}'},
            'traffic_policy': {'on_http_request': [
                {'actions': [{'type': 'oauth', 'config': {'provider': 'google'}}]},
                {'expressions': [f'!(actions.ngrok.oauth.identity.email in {allowed})'],
                 'actions': [{'type': 'deny', 'config': {'status_code': 403}}]},
            ]},
        }],
    }


def wait_for_cms(process, port, host):
    deadline = time.monotonic() + 10
    while process.poll() is None and time.monotonic() < deadline:
        connection = HTTPConnection('127.0.0.1', port, timeout=0.5)
        try:
            connection.request('GET', '/healthz', headers={'Host': host})
            response = connection.getresponse()
            if response.status == 200 and response.read(128) == b'ok\n':
                return
        except OSError:
            pass
        finally:
            connection.close()
        time.sleep(0.1)
    raise Invalid('The CMS did not become ready; no tunnel was started. Check the database and local port.')


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def interrupted(_signum, _frame):
    raise KeyboardInterrupt


def launch(database, *, path=SETTINGS):
    interactive()
    ngrok = shutil.which('ngrok')
    if ngrok is None:
        raise Missing('Install the official ngrok agent first: https://ngrok.com/downloads/linux . No tunnel was started.')
    with session_lock(path.parent):
        settings = read_settings(path)
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', settings['port']))
            except OSError:
                raise Invalid('The local port is occupied. Stop bash safwa local or the existing session first.') from None
        token = getpass('Ngrok authtoken (hidden; used only for this session): ')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', token, re.ASCII):
            raise Invalid('Enter the ngrok agent authtoken from your private dashboard.')
        environment = {key: value for key, value in os.environ.items() if not key.startswith('NGROK_')}
        environment['NGROK_AUTHTOKEN'] = token
        cms = tunnel = None
        previous_handlers = {number: signal.signal(number, interrupted) for number in (signal.SIGTERM, signal.SIGHUP)}
        try:
            with TemporaryDirectory(prefix='session-', dir=path.parent) as directory:
                config = Path(directory) / 'agent.yml'
                # JSON is valid YAML. The token is passed only in the child environment, never this file.
                with config.open('x', encoding='utf-8') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    json.dump(agent_config(settings), stream)
                result = subprocess.run([ngrok, 'config', 'check', '--config', str(config)], env=environment,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                if result.returncode:
                    raise Invalid('The installed ngrok agent rejected its configuration. Use the current official v3 agent. No tunnel was started.')
                cms = subprocess.Popen([sys.executable, str(ROOT/'scripts/cms.py'), '--database', str(database),
                                        'serve', '--host', '127.0.0.1', '--port', str(settings['port']),
                                        '--origin', settings['origin']], cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                wait_for_cms(cms, settings['port'], settings['origin'].removeprefix('https://'))
                with NamedTemporaryFile(dir=directory) as errors:
                    tunnel = subprocess.Popen([ngrok, 'start', 'safwa-cms', '--config', str(config)],
                                              env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                              stderr=errors, start_new_session=True)
                    print(f'Tunnel process started for {settings["origin"]}/editor .', flush=True)
                    print('Before sharing, verify that an approved email can sign in and an unlisted email is denied.', flush=True)
                    print('Keep this terminal and computer running. Press Ctrl+C to close remote access.', flush=True)
                    while cms.poll() is None and tunnel.poll() is None:
                        time.sleep(0.25)
                    if tunnel.poll() is not None:
                        errors.seek(0)
                        codes = sorted(set(re.findall(rb'ERR_NGROK_[0-9]+', errors.read(65536))))
                        detail = ' (' + ', '.join(code.decode('ascii') for code in codes) + ')' if codes else ''
                        raise Invalid('The tunnel stopped' + detail + '. Check your ngrok account, assigned domain, token and usage limits.')
                    raise Invalid('The CMS stopped. Closing the remote tunnel.')
        except KeyboardInterrupt:
            pass
        except subprocess.TimeoutExpired:
            raise Invalid('The ngrok configuration check timed out. No tunnel was started.') from None
        finally:
            stop(tunnel)
            stop(cms)
            for number, handler in previous_handlers.items():
                signal.signal(number, handler)
            environment.pop('NGROK_AUTHTOKEN', None)
            print('Remote session stopped.', flush=True)
