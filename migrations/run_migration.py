#!/usr/bin/env python3
"""
Run ClickHouse migration: buat semua tabel di database hbshengma.
Jalankan sekali sebelum mulai scraping ke ClickHouse.

Usage:
    python migrations/run_migration.py
"""
import os
import sys
from pathlib import Path

# Allow import from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import clickhouse_connect

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_SECURE = os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true"

SQL_FILE = Path(__file__).parent / "001_create_tables.sql"


def main() -> None:
    if not CLICKHOUSE_HOST:
        print("ERROR: CLICKHOUSE_HOST not set in .env")
        sys.exit(1)

    print(f"Connecting to ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    client = clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        secure=CLICKHOUSE_SECURE,
        connect_timeout=10,
    )

    sql = SQL_FILE.read_text(encoding="utf-8")

    # Split on ";" and run each statement separately
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    print(f"Running {len(statements)} SQL statements...")
    for i, stmt in enumerate(statements, 1):
        first_line = stmt.splitlines()[0][:80]
        print(f"  [{i}/{len(statements)}] {first_line}")
        client.command(stmt)

    print("\nMigration completed successfully.")
    print("Tables created in database: hbshengma")

    # Verify tables exist
    result = client.query("SHOW TABLES FROM hbshengma")
    tables = [row[0] for row in result.result_rows]
    print(f"Tables: {', '.join(sorted(tables))}")

    client.close()


if __name__ == "__main__":
    main()
