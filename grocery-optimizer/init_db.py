"""
init_db.py — Initialise the grocery price optimizer database.

Run:
    python grocery-optimizer/init_db.py

Creates (or resets) grocery.db in the grocery-optimizer/ directory,
applies the schema, and inserts seed data.
"""

import sqlite3
import os

from schema import create_tables
from seed import run_seed

DB_PATH = os.path.join(os.path.dirname(__file__), "grocery.db")


def print_summary(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    # Master products
    cur.execute("SELECT id, name, category, is_staple FROM master_products ORDER BY id")
    rows = cur.fetchall()
    print(f"\n master_products ({len(rows)} rows)")
    print(f"  {'ID':<4} {'Name':<30} {'Category':<25} {'Staple'}")
    print(f"  {'-'*4} {'-'*30} {'-'*25} {'-'*6}")
    for r in rows:
        print(f"  {r[0]:<4} {r[1]:<30} {r[2]:<25} {'Yes' if r[3] else 'No'}")

    # Store products with unit price comparison
    cur.execute("""
        SELECT sp.id, mp.name, sp.store_name, sp.product_name,
               sp.brand_tier, sp.price, sp.is_on_special,
               sp.package_size, sp.unit_type, sp.unit_price_per_100
        FROM store_products sp
        JOIN master_products mp ON mp.id = sp.master_product_id
        ORDER BY mp.id, sp.unit_price_per_100
    """)
    rows = cur.fetchall()
    print(f"\n store_products ({len(rows)} rows, sorted by unit price per 100 within each product)")
    print(f"  {'ID':<4} {'Master Product':<22} {'Store':<13} {'Product':<42} {'Tier':<10} {'Price':>6} {'Special':<8} {'Size':<8} {'¢/100'}")
    print(f"  {'-'*4} {'-'*22} {'-'*13} {'-'*42} {'-'*10} {'-'*6} {'-'*8} {'-'*8} {'-'*7}")
    for r in rows:
        special_flag = "🟡 YES" if r[6] else "No"
        size_str = f"{r[7]:.0f}{r[8]}"
        print(f"  {r[0]:<4} {r[1]:<22} {r[2]:<13} {r[3]:<42} {r[4]:<10} ${r[5]:<5.2f} {special_flag:<8} {size_str:<8} ${r[9]:.4f}")

    # Shopping list
    cur.execute("""
        SELECT sl.id, mp.name, sl.preference_tier, sl.quantity, sl.assigned_store
        FROM shopping_list sl
        JOIN master_products mp ON mp.id = sl.master_product_id
        ORDER BY sl.id
    """)
    rows = cur.fetchall()
    print(f"\n shopping_list ({len(rows)} rows)")
    print(f"  {'ID':<4} {'Master Product':<30} {'Pref Tier':<12} {'Qty':<5} {'Assigned Store'}")
    print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*5} {'-'*15}")
    for r in rows:
        print(f"  {r[0]:<4} {r[1]:<30} {str(r[2] or 'any'):<12} {r[3]:<5} {r[4] or 'unassigned'}")

    print("\n" + "=" * 60)
    print(f"Database ready at: {DB_PATH}")
    print("=" * 60 + "\n")


def main() -> None:
    # Remove existing DB for a clean init
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        create_tables(conn)
        run_seed(conn)
        print_summary(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
