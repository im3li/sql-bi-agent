"""
CLI entrypoint: create and seed the demo SQLite database.

Usage:
    python init_db.py
"""
from __future__ import annotations

import sqlite3

from src.database import initialize_database


def main() -> None:
    path = initialize_database()
    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM customers")
        c = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM products")
        p = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders")
        o = cur.fetchone()[0]

    print(f"✅ Database created at {path}")
    print(f"   customers={c}  products={p}  orders={o}")


if __name__ == "__main__":
    main()
