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
    cur.execute("INSERT INTO master_products (name, category, is_staple) VALUES (?, ?, ?)", (name, category, int(is_staple)))
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
    cur.execute("""
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
    cur.execute("""
        INSERT INTO shopping_list (master_product_id, preference_tier, quantity, assigned_store)
        VALUES (?, ?, ?, ?)
    """,
        (master_product_id, preference_tier, quantity, assigned_store),
    )
    return cur.lastrowid


def run_seed(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # MASTER PRODUCTS AND STORE PRODUCTS — loaded from Grocery_List_Staples_w_Prices.xlsx
    # ------------------------------------------------------------------

    mp_1 = insert_master_product(cur, 'Milk 2L', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_1,
        store_name='Coles',
        product_name='Milk 2L at Coles',
        brand_tier='standard',
        price=4.40,
        is_on_special=False,
        package_size=2000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%202L%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_1,
        store_name='Woolworths',
        product_name='Milk 2L at Woolworths',
        brand_tier='standard',
        price=4.70,
        is_on_special=False,
        package_size=2000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%202L%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_1,
        store_name='Aldi',
        product_name='Milk 2L at Aldi',
        brand_tier='budget',
        price=3.55,
        is_on_special=False,
        package_size=2000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%202L%20Aldi',
    )

    mp_2 = insert_master_product(cur, 'Milk 3L', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_2,
        store_name='Coles',
        product_name='Milk 3L at Coles',
        brand_tier='standard',
        price=5.15,
        is_on_special=False,
        package_size=3000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%203L%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_2,
        store_name='Woolworths',
        product_name='Milk 3L at Woolworths',
        brand_tier='standard',
        price=5.15,
        is_on_special=False,
        package_size=3000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%203L%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_2,
        store_name='Aldi',
        product_name='Milk 3L at Aldi',
        brand_tier='budget',
        price=5.15,
        is_on_special=False,
        package_size=3000,
        unit_type='ml',
        deep_link_url='https://www.google.com/search?q=Milk%203L%20Aldi',
    )

    mp_3 = insert_master_product(cur, 'Bread - Wholemeal', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_3,
        store_name='Coles',
        product_name='Bread - Wholemeal at Coles',
        brand_tier='standard',
        price=4.70,
        is_on_special=False,
        package_size=700,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Bread%20-%20Wholemeal%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_3,
        store_name='Woolworths',
        product_name='Bread - Wholemeal at Woolworths',
        brand_tier='standard',
        price=4.70,
        is_on_special=False,
        package_size=700,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Bread%20-%20Wholemeal%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_3,
        store_name='Aldi',
        product_name='Bread - Wholemeal at Aldi',
        brand_tier='budget',
        price=3.69,
        is_on_special=False,
        package_size=700,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Bread%20-%20Wholemeal%20Aldi',
    )

    mp_4 = insert_master_product(cur, 'Eggs', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_4,
        store_name='Coles',
        product_name='Eggs at Coles',
        brand_tier='standard',
        price=6.20,
        is_on_special=False,
        package_size=12,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Eggs%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_4,
        store_name='Woolworths',
        product_name='Eggs at Woolworths',
        brand_tier='standard',
        price=6.20,
        is_on_special=False,
        package_size=12,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Eggs%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_4,
        store_name='Aldi',
        product_name='Eggs at Aldi',
        brand_tier='budget',
        price=5.99,
        is_on_special=False,
        package_size=12,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Eggs%20Aldi',
    )

    mp_5 = insert_master_product(cur, 'Mince 500g', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_5,
        store_name='Coles',
        product_name='Mince 500g at Coles',
        brand_tier='standard',
        price=9.00,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Mince%20500g%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_5,
        store_name='Woolworths',
        product_name='Mince 500g at Woolworths',
        brand_tier='standard',
        price=9.00,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Mince%20500g%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_5,
        store_name='Aldi',
        product_name='Mince 500g at Aldi',
        brand_tier='budget',
        price=7.99,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Mince%20500g%20Aldi',
    )

    mp_6 = insert_master_product(cur, 'Chicken Breast 500g', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_6,
        store_name='Coles',
        product_name='Chicken Breast 500g at Coles',
        brand_tier='standard',
        price=8.70,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Breast%20500g%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_6,
        store_name='Woolworths',
        product_name='Chicken Breast 500g at Woolworths',
        brand_tier='standard',
        price=8.70,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Breast%20500g%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_6,
        store_name='Aldi',
        product_name='Chicken Breast 500g at Aldi',
        brand_tier='budget',
        price=7.60,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Breast%20500g%20Aldi',
    )

    mp_7 = insert_master_product(cur, 'Butter', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_7,
        store_name='Coles',
        product_name='Butter at Coles',
        brand_tier='standard',
        price=6.80,
        is_on_special=False,
        package_size=250,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Butter%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_7,
        store_name='Woolworths',
        product_name='Butter at Woolworths',
        brand_tier='standard',
        price=6.80,
        is_on_special=False,
        package_size=250,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Butter%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_7,
        store_name='Aldi',
        product_name='Butter at Aldi',
        brand_tier='budget',
        price=7.99,
        is_on_special=False,
        package_size=250,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Butter%20Aldi',
    )

    mp_8 = insert_master_product(cur, 'Grapes', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_8,
        store_name='Coles',
        product_name='Grapes at Coles',
        brand_tier='standard',
        price=6.00,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Grapes%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_8,
        store_name='Woolworths',
        product_name='Grapes at Woolworths',
        brand_tier='standard',
        price=6.00,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Grapes%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_8,
        store_name='Aldi',
        product_name='Grapes at Aldi',
        brand_tier='budget',
        price=4.22,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Grapes%20Aldi',
    )

    mp_9 = insert_master_product(cur, 'Honey', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_9,
        store_name='Coles',
        product_name='Honey at Coles',
        brand_tier='standard',
        price=6.50,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Honey%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_9,
        store_name='Woolworths',
        product_name='Honey at Woolworths',
        brand_tier='standard',
        price=6.70,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Honey%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_9,
        store_name='Aldi',
        product_name='Honey at Aldi',
        brand_tier='budget',
        price=5.99,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Honey%20Aldi',
    )

    mp_10 = insert_master_product(cur, 'Flour', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_10,
        store_name='Coles',
        product_name='Flour at Coles',
        brand_tier='standard',
        price=2.40,
        is_on_special=False,
        package_size=1000,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Flour%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_10,
        store_name='Woolworths',
        product_name='Flour at Woolworths',
        brand_tier='standard',
        price=2.40,
        is_on_special=False,
        package_size=1000,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Flour%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_10,
        store_name='Aldi',
        product_name='Flour at Aldi',
        brand_tier='budget',
        price=2.39,
        is_on_special=False,
        package_size=1000,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Flour%20Aldi',
    )

    mp_11 = insert_master_product(cur, 'Pasta 500g', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_11,
        store_name='Coles',
        product_name='Pasta 500g at Coles',
        brand_tier='standard',
        price=0.90,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Pasta%20500g%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_11,
        store_name='Woolworths',
        product_name='Pasta 500g at Woolworths',
        brand_tier='standard',
        price=0.90,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Pasta%20500g%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_11,
        store_name='Aldi',
        product_name='Pasta 500g at Aldi',
        brand_tier='budget',
        price=0.89,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Pasta%20500g%20Aldi',
    )

    mp_12 = insert_master_product(cur, 'Spaghetti 500g', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_12,
        store_name='Coles',
        product_name='Spaghetti 500g at Coles',
        brand_tier='standard',
        price=0.90,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Spaghetti%20500g%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_12,
        store_name='Woolworths',
        product_name='Spaghetti 500g at Woolworths',
        brand_tier='standard',
        price=0.90,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Spaghetti%20500g%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_12,
        store_name='Aldi',
        product_name='Spaghetti 500g at Aldi',
        brand_tier='budget',
        price=0.89,
        is_on_special=False,
        package_size=500,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Spaghetti%20500g%20Aldi',
    )

    mp_13 = insert_master_product(cur, 'Bread Rolls', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_13,
        store_name='Coles',
        product_name='Bread Rolls at Coles',
        brand_tier='standard',
        price=3.00,
        is_on_special=False,
        package_size=6,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Bread%20Rolls%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_13,
        store_name='Woolworths',
        product_name='Bread Rolls at Woolworths',
        brand_tier='standard',
        price=3.00,
        is_on_special=False,
        package_size=6,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Bread%20Rolls%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_13,
        store_name='Aldi',
        product_name='Bread Rolls at Aldi',
        brand_tier='budget',
        price=2.69,
        is_on_special=False,
        package_size=6,
        unit_type='each',
        deep_link_url='https://www.google.com/search?q=Bread%20Rolls%20Aldi',
    )

    mp_14 = insert_master_product(cur, 'Chicken Schnitzels', 'Groceries', is_staple=True)
    insert_store_product(
        cur,
        master_product_id=mp_14,
        store_name='Coles',
        product_name='Chicken Schnitzels at Coles',
        brand_tier='standard',
        price=11.95,
        is_on_special=False,
        package_size=400,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Schnitzels%20Coles',
    )
    insert_store_product(
        cur,
        master_product_id=mp_14,
        store_name='Woolworths',
        product_name='Chicken Schnitzels at Woolworths',
        brand_tier='standard',
        price=12.00,
        is_on_special=False,
        package_size=400,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Schnitzels%20Woolworths',
    )
    insert_store_product(
        cur,
        master_product_id=mp_14,
        store_name='Aldi',
        product_name='Chicken Schnitzels at Aldi',
        brand_tier='budget',
        price=9.00,
        is_on_special=False,
        package_size=400,
        unit_type='g',
        deep_link_url='https://www.google.com/search?q=Chicken%20Schnitzels%20Aldi',
    )

    # ------------------------------------------------------------------
    # SHOPPING LIST — add all items
    # ------------------------------------------------------------------
    insert_shopping_list_item(cur, master_product_id=mp_1, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_2, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_3, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_4, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_5, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_6, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_7, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_8, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_9, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_10, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_11, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_12, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_13, preference_tier=None, quantity=1, assigned_store=None)
    insert_shopping_list_item(cur, master_product_id=mp_14, preference_tier=None, quantity=1, assigned_store=None)

    conn.commit()
    print("Seed data inserted successfully.")

