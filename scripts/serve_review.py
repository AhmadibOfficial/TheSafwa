#!/usr/bin/env python3
"""Run and administer the standalone review build with synthetic data only."""
import argparse
from getpass import getpass
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.parent.server import ReviewServer
from packages.config.review import DATABASE, PORT
from packages.content import store
from packages.content.contracts import ARMS, Invalid, Missing
from packages.security import auth


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DATABASE)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the local system")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", PORT)))
    sub.add_parser("init", help="initialize a review database with institutional seed content")
    user = sub.add_parser("create-user", help="provision an individual review account")
    user.add_argument("name")
    user.add_argument("--role", required=True, choices=auth.ROLES)
    user.add_argument("--arm", choices=ARMS)
    revoke = sub.add_parser("revoke-user", help="disable an account and invalidate its sessions")
    revoke.add_argument("name")
    backup = sub.add_parser("backup", help="create a consistent copy of the current database")
    backup.add_argument("destination", type=Path)
    restore = sub.add_parser("restore", help="verify a backup and restore it into a new file")
    restore.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        run(args)
    except (Invalid, Missing, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Safwa review: {error}\n")


def run(args):
    if args.command == "backup":
        store.copy_database(args.database, args.destination)
        print("Backup verified and written.")
        return
    if args.command == "restore":
        store.copy_database(args.source, args.database, restore=True)
        print("Restore verified and written to the new database.")
        return

    store.initialize(args.database)
    if args.command == "serve":
        with ReviewServer(args.port, args.database) as server:
            print(f"Safwa review listening at http://127.0.0.1:{server.server_port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                return
    elif args.command == "create-user":
        if not sys.stdin.isatty():
            raise Invalid("Create accounts from an interactive terminal.")
        password = getpass("Review passphrase: ")
        if password != getpass("Confirm passphrase: "):
            raise Invalid("The passphrases do not match.")
        with store.transaction(args.database, write=True) as db:
            uri = auth.create_user(db, args.name, args.role, args.arm, password)
        print("Import this one-time enrollment URI into your authenticator. Keep it private.\n" + uri)
    elif args.command == "revoke-user":
        with store.transaction(args.database, write=True) as db:
            auth.revoke_user(db, args.name)
        print("Account and sessions revoked.")
    else:
        print("Review database initialized.")


if __name__ == "__main__":
    main()
