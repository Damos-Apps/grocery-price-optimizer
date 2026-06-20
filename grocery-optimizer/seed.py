import sqlite3
from typing import Optional


def calc_unit_price_per_100(price: float, package_size: float) -> float:
    """Calculate the price per 100 units (g or ml) for fair comparison."""
    if package_size <= 0:
        raise ValueError(f"package_size must be > 0, got {package_size}")
    return round((price / package_size) * 100, 4)


def insert_master_product(
    cur: sqlite3.Cursor,
    name: str,
    category: str,
    is_staple: bool,
) -> int:
    cur.execute(
        "INSERT INTO master_products (name, category, is_staple) VALUES (?, ?, ?)",
        (name, category, int(is_staple)),
    )
    return cur.lastrowid


def insert_store_product(
    cur: sqlite3.Cursor,
    master_product_id: int,
    store_name: str,
    product_name: str,
    brand_tier: str,
    price: float,
    is_on_special: bool,
    package_size: float,
    unit_type: str,
    deep_link_url: Optional[str] = None,
) -> int:
    unit_price_per_100 = calc_unit_price_per_100(price, package_size)
    cur.execute(
        """
        INSERT INTO store_products (
            master_product_id, store_name, product_name, brand_tier,
            price, is_on_special, package_size, unit_type,
            unit_price_per_100, deep_link_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            master_product_id,
            store_name,
            product_name,
            brand_tier,
            price,
            int(is_on_special),
            package_size,
            unit_type,
            unit_price_per_100,
            deep_link_url,
        ),
    )
    return cur.lastrowid


def insert_shopping_list_item(
    cur: sqlite3.Cursor,
    master_product_id: int,
    preference_tier: Optional[str],
    quantity: int,
    assigned_store: Optional[str],
) -> int:
    cur.execute(
        """
        INSERT INTO shopping_list (master_product_id, preference_tier, quantity, assigned_store)
        VALUES (?, ?, ?, ?)
        """,
        (master_product_id, preference_tier, quantity, assigned_store),
    )
    return cur.lastrowid


def run_seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # 1. MASTER PRODUCTS
    # ------------------------------------------------------------------
    mp_jam_id = insert_master_product(cur, "Strawberry Jam", "Condiments & Spreads", is_staple=False)
    mp_milk_id = insert_master_product(cur, "Full Cream Milk 2L", "Dairy & Eggs", is_staple=True)
    mp_coffee_id = insert_master_product(cur, "Instant Coffee", "Coffee & Tea", is_staple=False)

    # ------------------------------------------------------------------
    # 2. STORE PRODUCTS — Strawberry Jam
    # ------------------------------------------------------------------
    # Coles: IXL 250g
    insert_store_product(
        cur,
        master_product_id=mp_jam_id,
        store_name="Coles",
        product_name="IXL Strawberry Jam 250g",
        brand_tier="standard",
        price=3.20,
        is_on_special=False,
        package_size=250,
        unit_type="g",
        deep_link_url="https://www.coles.com.au/search?q=IXL+strawberry+jam+250g",
    )

    # Woolworths: Bonne Maman 500g
    insert_store_product(
        cur,
        master_product_id=mp_jam_id,
        store_name="Woolworths",
        product_name="Bonne Maman Strawberry Jam 500g",
        brand_tier="premium",
        price=7.50,
        is_on_special=False,
        package_size=500,
        unit_type="g",
        deep_link_url="https://www.woolworths.com.au/shop/search/products?searchTerm=bonne+maman+strawberry+jam+500g",
    )

    # Aldi: Grandessa 500g
    insert_store_product(
        cur,
        master_product_id=mp_jam_id,
        store_name="Aldi",
        product_name="Grandessa Strawberry Jam 500g",
        brand_tier="budget",
        price=2.49,
        is_on_special=False,
        package_size=500,
        unit_type="g",
        deep_link_url="https://www.aldi.com.au/en/grocery-specialbuys/search/?query=grandessa+strawberry+jam",
    )

    # ------------------------------------------------------------------
    # 3. STORE PRODUCTS — Full Cream Milk 2L (2000 ml for unit comparison)
    # ------------------------------------------------------------------
    insert_store_product(
        cur,
        master_product_id=mp_milk_id,
        store_name="Coles",
        product_name="Coles Full Cream Milk 2L",
        brand_tier="budget",
        price=2.85,
        is_on_special=False,
        package_size=2000,
        unit_type="ml",
        deep_link_url="https://www.coles.com.au/search?q=coles+full+cream+milk+2l",
    )

    insert_store_product(
        cur,
        master_product_id=mp_milk_id,
        store_name="Woolworths",
        product_name="Woolworths Full Cream Milk 2L",
        brand_tier="budget",
        price=2.90,
        is_on_special=False,
        package_size=2000,
        unit_type="ml",
        deep_link_url="https://www.woolworths.com.au/shop/search/products?searchTerm=woolworths+full+cream+milk+2l",
    )

    insert_store_product(
        cur,
        master_product_id=mp_milk_id,
        store_name="Aldi",
        product_name="Farmdale Full Cream Milk 2L",
        brand_tier="budget",
        price=2.49,
        is_on_special=False,
        package_size=2000,
        unit_type="ml",
        deep_link_url="https://www.aldi.com.au/en/grocery-specialbuys/search/?query=farmdale+full+cream+milk+2l",
    )

    # ------------------------------------------------------------------
    # 4. STORE PRODUCTS — Moccona Coffee 200g (Coles 50% off special)
    # ------------------------------------------------------------------
    # Regular price $18.00, 50% off = $9.00
    regular_price = 18.00
    special_price = round(regular_price * 0.50, 2)

    insert_store_product(
        cur,
        master_product_id=mp_coffee_id,
        store_name="Coles",
        product_name="Moccona Classic Dark Roast Instant Coffee 200g",
        brand_tier="premium",
        price=special_price,
        is_on_special=True,
        package_size=200,
        unit_type="g",
        deep_link_url="https://www.coles.com.au/search?q=moccona+coffee+200g",
    )

    # ------------------------------------------------------------------
    # 5. SHOPPING LIST — add one entry per master product
    # ------------------------------------------------------------------
    # Jam: no strong preference, let the optimizer decide
    insert_shopping_list_item(cur, master_product_id=mp_jam_id, preference_tier=None, quantity=1, assigned_store=None)

    # Milk: budget tier, not yet assigned to a store
    insert_shopping_list_item(cur, master_product_id=mp_milk_id, preference_tier="budget", quantity=1, assigned_store=None)

    # Coffee: premium tier, already on special at Coles
    insert_shopping_list_item(cur, master_product_id=mp_coffee_id, preference_tier="premium", quantity=1, assigned_store="Coles")

    conn.commit()
    print("Seed data inserted successfully.")
