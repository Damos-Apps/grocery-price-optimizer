import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS master_products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            category    TEXT    NOT NULL,
            is_staple   INTEGER NOT NULL DEFAULT 0  -- 1 = staple, 0 = non-staple
        );

        CREATE TABLE IF NOT EXISTS store_products (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            master_product_id     INTEGER NOT NULL REFERENCES master_products(id),
            store_name            TEXT    NOT NULL,
            product_name          TEXT    NOT NULL,
            brand_tier            TEXT    NOT NULL, -- 'budget', 'standard', 'premium'
            price                 REAL    NOT NULL,
            is_on_special         INTEGER NOT NULL DEFAULT 0, -- 1 = on special, 0 = regular
            package_size          REAL    NOT NULL, -- numeric size (e.g. 250, 2000)
            unit_type             TEXT    NOT NULL, -- 'g', 'ml', 'kg', 'L', etc.
            unit_price_per_100    REAL    NOT NULL, -- auto-calculated: (price / package_size) * 100
            deep_link_url         TEXT
        );

        CREATE TABLE IF NOT EXISTS shopping_list (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            master_product_id INTEGER NOT NULL REFERENCES master_products(id),
            preference_tier   TEXT,               -- 'budget', 'standard', 'premium', or NULL for any
            quantity          INTEGER NOT NULL DEFAULT 1,
            assigned_store    TEXT                -- 'Coles', 'Woolworths', 'Aldi', or NULL
        );
    """)

    conn.commit()
    print("Tables created successfully.")
