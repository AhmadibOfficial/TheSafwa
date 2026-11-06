#!/usr/bin/env python3
"""Safwa SQLite CMS: initialize, provision staff, serve, check, migrate, back up and restore."""
import argparse
from contextlib import closing
from getpass import getpass
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.parent.server import ReviewServer
from apps.parent.wsgi import Application
from packages.config.review import DATABASE, PORT
from packages.content import migrations, store
from packages.content.contracts import ARMS, Invalid, Missing
from packages.security import auth, vault


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path(os.environ.get('SAFWA_DATABASE', DATABASE)))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='create a private database with the approved public pages')
    sub.add_parser('check', help='verify schema, data integrity and encryption key')
    local = sub.add_parser('local', help='start the loopback review server')
    local.add_argument('--port', type=int, default=PORT)
    remote_setup = sub.add_parser('remote-setup', help='privately configure an email-restricted local review endpoint')
    remote_setup.add_argument('--port', type=int, default=PORT)
    sub.add_parser('remote', help='start an owner-controlled remote review session; ngrok must be installed')
    serve = sub.add_parser('serve', help='serve the application with Waitress')
    serve.add_argument('--origin', default=os.environ.get('SAFWA_ORIGIN'))
    serve.add_argument('--host', default='127.0.0.1')
    serve.add_argument('--port', type=int, default=int(os.environ.get('PORT', PORT)))
    account = sub.add_parser('create-user', help='provision staff from an interactive terminal')
    account.add_argument('name')
    account.add_argument('--role', required=True, choices=auth.ROLES)
    account.add_argument('--arm', choices=ARMS)
    revoke = sub.add_parser('revoke-user', help='disable a staff account and all its sessions')
    revoke.add_argument('name')
    reset = sub.add_parser('reset-access', help='recover a staff account using private local operator access')
    reset.add_argument('name')
    backup = sub.add_parser('backup', help='create a consistent backup without live sessions')
    backup.add_argument('destination', type=Path)
    restore = sub.add_parser('restore', help='restore a verified backup to a new database file')
    restore.add_argument('source', type=Path)
    migrate = sub.add_parser('migrate', help='offline migration from review schema v1; service must be stopped')
    migrate.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args)
    except (Invalid, Missing, OSError, sqlite3.Error) as error:
        parser.exit(1, f'Safwa CMS: {error}\n')


def check(path):
    with store.transaction(path) as db:
        store.check_identity(db)
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise Invalid('Database integrity checks failed.')
        if db.vault is None:
            raise Invalid('The CMS encryption key is missing.')
        for row in db.execute('SELECT otp_key FROM users'):
            vault.decrypt(db, row[0])
    print('Schema, relationships, database integrity and encryption key verified.')


def enrollment(uri):
    print('Import this enrollment URI into an authenticator. It is shown once; keep it private.\n' + uri)


def run(args):
    if args.command == 'remote-setup':
        from packages.security import remote_access
        remote_access.configure(args.port)
        return
    if args.command == 'backup':
        store.copy_database(args.database, args.destination)
        print('Database and image backup verified. Keep cms.key in a separate protected backup.')
        return
    if args.command == 'restore':
        store.copy_database(args.source, args.database, restore=True)
        print('Verified restore created. Restore the matching cms.key separately before serving. All sessions were removed.')
        return
    if args.command == 'migrate':
        migrations.migrate(args.database, args.backup)
        check(args.database)
        print('Version 2 migration complete. Original version 1 database preserved in the specified backup.')
        return
    if args.command == 'check':
        check(args.database)
        return
    if args.command == 'init':
        store.initialize(args.database)
        check(args.database)
        return
    if not args.database.is_file():
        raise Missing('Initialize the CMS first: python3 scripts/cms.py init')
    check(args.database)
    if args.command == 'local':
        with ReviewServer(args.port, args.database) as server:
            print(f'Safwa CMS: http://127.0.0.1:{server.server_port}/editor', flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    elif args.command == 'remote':
        from packages.security import remote_access
        remote_access.launch(args.database)
    elif args.command == 'serve':
        if not args.origin:
            raise Invalid('Set --origin or SAFWA_ORIGIN to the exact public origin.')
        from waitress import serve
        app = Application(args.database, args.origin)
        serve(app, host=args.host, port=args.port, threads=8, max_request_body_size=4*1024*1024+8192,
              max_request_header_size=16384, channel_timeout=30, expose_tracebacks=False,
              clear_untrusted_proxy_headers=True, ident='Safwa')
    elif args.command in {'create-user', 'reset-access'}:
        if not sys.stdin.isatty():
            raise Invalid('Provision staff from an interactive terminal so passphrases never appear in shell history.')
        password = getpass('Staff passphrase: ')
        if password != getpass('Confirm passphrase: '):
            raise Invalid('The passphrases do not match.')
        with store.transaction(args.database, write=True) as db:
            if args.command == 'create-user':
                uri = auth.create_user(db, args.name, args.role, args.arm, password)
            else:
                uri = auth.reset_access(db, args.name, password)
        enrollment(uri)
    elif args.command == 'revoke-user':
        with store.transaction(args.database, write=True) as db:
            auth.revoke_user(db, args.name)
        print('Account disabled and sessions ended.')


if __name__ == '__main__':
    main()
