#!/usr/bin/env python3
"""Apply versioned DINKLY Postgres migrations without exposing credentials."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    if not migrations:
        raise SystemExit("No SQL migrations found")
    if args.dry_run:
        for migration in migrations:
            print(f"would apply {migration.relative_to(ROOT)}")
        return 0
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")
    psql = shutil.which("psql")
    if not psql:
        raise SystemExit("psql is required to apply migrations")
    environment = {**os.environ, "PGCONNECT_TIMEOUT": "15"}
    for migration in migrations:
        print(f"applying {migration.name}")
        subprocess.run(
            [psql, "--no-psqlrc", "--set", "ON_ERROR_STOP=1", "--dbname", args.database_url, "--file", str(migration)],
            check=True,
            env=environment,
        )
    print(f"applied {len(migrations)} migration(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
