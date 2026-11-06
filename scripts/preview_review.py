"""Serve a fresh set of public seed content through the managed preview launcher."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.parent.server import ReviewServer
from packages.content.store import initialize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=["0.0.0.0"], required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--strictPort", action="store_true")
    options = parser.parse_args()
    with TemporaryDirectory(prefix="safwa-public-preview-") as directory:
        database = Path(directory) / "review.sqlite3"
        initialize(database)
        with ReviewServer(options.port, database, public_preview=True) as server:
            server.serve_forever()


if __name__ == "__main__":
    main()
