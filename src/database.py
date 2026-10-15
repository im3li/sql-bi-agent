"""
Database layer: connection, schema introspection, query execution,
and one-shot initialization/seed for the demo SQLite database.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd

# ---------------------------------------------------------------------------
# Paths (project root = parent of `src/`)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
DB_PATH: Final[Path] = DATA_DIR / "sample_store.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
SCHEMA: Final[str] = """
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    signup_date   TEXT    NOT NULL
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    product_name  TEXT    NOT NULL,
    category      TEXT    NOT NULL,
    unit_price    REAL    NOT NULL
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    order_date    TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (product_id)  REFERENCES products(product_id)
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_product  ON orders(product_id);
CREATE INDEX idx_orders_date     ON orders(order_date);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
COUNTRIES = ["USA", "USA", "USA", "Germany", "France", "UK",
             "Canada", "Australia", "Japan", "Brazil"]
FIRST = ["Alice", "Bob", "Carlos", "Diana", "Ethan", "Fatima", "Grace",
         "Hiro", "Ivan", "Jia", "Kenji", "Lena", "Marco", "Nina", "Omar",
         "Priya", "Quinn", "Ravi", "Sofia", "Tom"]
LAST = ["Smith", "Johnson", "Garcia", "Chen", "Patel", "Kim",
        "Müller", "Rossi", "Dubois", "Tanaka"]

PRODUCTS = [
    ("Wireless Headphones", "Electronics",   129.99),
    ("Bluetooth Speaker",   "Electronics",    79.99),
    ("4K Monitor",          "Electronics",   399.00),
    ("Mechanical Keyboard", "Electronics",   149.50),
    ("Ergonomic Mouse",     "Electronics",    59.99),
    ("Yoga Mat",            "Sports",         29.99),
    ("Running Shoes",       "Sports",        119.99),
    ("Dumbbell Set",        "Sports",         89.00),
    ("Coffee Maker",        "Home",          159.00),
    ("Blender",             "Home",           69.99),
    ("Air Fryer",           "Home",          129.00),
    ("Desk Lamp",           "Home",           39.99),
    ("Notebook Set",        "Stationery",     14.99),
    ("Fountain Pen",        "Stationery",     49.50),
    ("Backpack",            "Accessories",    89.00),
    ("Sunglasses",          "Accessories",   109.00),
    ("Water Bottle",        "Accessories",    24.99),
    ("Smart Watch",         "Electronics",   249.00),
    ("Tablet Stand",        "Electronics",    34.99),
    ("Webcam HD",           "Electronics",    99.00),
]

STATUSES = ["completed", "completed", "completed", "shipped", "pending", "cancelled"]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def initialize_database(db_path: Path = DB_PATH, seed: int = 42) -> Path:
    """Create + seed the SQLite database. Idempotent (drops existing tables)."""
    random.seed(seed)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(SCHEMA)

        # customers
        start = datetime(2022, 1, 1)
        customers = [
            (
                i,
                f"{random.choice(FIRST)} {random.choice(LAST)}",
                f"user{i}@example.com",
                random.choice(COUNTRIES),
                (start + timedelta(days=random.randint(0, 900))).strftime("%Y-%m-%d"),
            )
            for i in range(1, 201)
        ]
        cur.executemany(
            "INSERT INTO customers (customer_id, name, email, country, signup_date) "
            "VALUES (?, ?, ?, ?, ?)", customers,
        )

        # products
        products = [
            (i + 1, name, cat, price)
            for i, (name, cat, price) in enumerate(PRODUCTS)
        ]
        cur.executemany(
            "INSERT INTO products (product_id, product_name, category, unit_price) "
            "VALUES (?, ?, ?, ?)", products,
        )

        # orders
        start = datetime(2023, 1, 1)
        orders = [
            (
                i,
                random.randint(1, 200),
                random.randint(1, len(PRODUCTS)),
                random.choices([1, 1, 1, 2, 2, 3, 5, 10], k=1)[0],
                (start + timedelta(days=random.randint(0, 730))).strftime("%Y-%m-%d"),
                random.choice(STATUSES),
            )
            for i in range(1, 3001)
        ]
        cur.executemany(
            "INSERT INTO orders (order_id, customer_id, product_id, quantity, "
            "order_date, status) VALUES (?, ?, ?, ?, ?, ?)", orders,
        )

        conn.commit()
    finally:
        conn.close()

    return db_path


# ---------------------------------------------------------------------------
# Introspection & querying
# ---------------------------------------------------------------------------
def get_schema(db_path: Path = DB_PATH) -> str:
    """Return a human/LLM-readable description of the SQLite schema."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in cur.fetchall()]
        chunks: list[str] = []
        for table in tables:
            cur.execute(f"PRAGMA table_info('{table}')")
            cols = cur.fetchall()
            chunks.append(f"Table: {table}")
            for _, col_name, col_type, *_ in cols:
                chunks.append(f"  - {col_name} ({col_type})")
            try:
                sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 3", conn)
                if not sample.empty:
                    chunks.append("  Sample rows:")
                    for _, row in sample.iterrows():
                        chunks.append(f"    {row.to_dict()}")
            except Exception:
                pass
            chunks.append("")
        return "\n".join(chunks)
    finally:
        conn.close()


def run_query(sql: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame."""
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()