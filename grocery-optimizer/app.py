import streamlit as st
import sqlite3
import os
import sys
import urllib.parse

# ------------------------------------------------------------------
# Imports from the optimizer module
# ------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from optimizer import (
    DB_PATH,
    ALL_STORES,
    load_shopping_list,
    load_store_products,
    optimize_raw,
    optimize_advanced,
    format_store_lists,
    StoreProduct,
)
from sheets import sync_shopping_list_from_sheet

# ------------------------------------------------------------------
# Retailer "Add to Cart" search URLs
# ------------------------------------------------------------------
_RETAILER_SEARCH_URLS = {
    "Woolworths": "https://www.woolworths.com.au/shop/search/products?searchTerm={item}",
    "Coles": "https://www.coles.com.au/search?q={item}",
    # ALDI products route to DoorDash for home delivery.
    "Aldi": "https://www.doordash.com/p/aldi-australia",
}


def _build_add_to_cart_url(store_name: str, item_name: str) -> str:
    """Return a retailer search URL for the given item, with safe URL encoding."""
    encoded_item = urllib.parse.quote(item_name)
    template = _RETAILER_SEARCH_URLS.get(
        store_name, "https://www.google.com/search?q={item}"
    )
    if "{item}" in template:
        return template.format(item=encoded_item)
    return template


# ------------------------------------------------------------------
# Page configuration
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Australian Grocery Price Optimizer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------
# Custom CSS
# ------------------------------------------------------------------
st.markdown("""
    <style>
    .special-badge {
        background-color: #ffcc00;
        color: #333;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .staple-badge {
        background-color: #4CAF50;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .alert-banner {
        background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
        color: white;
        padding: 16px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid rgba(255,255,255,0.2);
    }
    .suggestion-card {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-left: 4px solid #28a745;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .suggestion-card .title {
        font-weight: 600;
        color: #212529;
        font-size: 15px;
        margin-bottom: 4px;
    }
    .suggestion-card .savings {
        color: #28a745;
        font-weight: 700;
        font-size: 16px;
    }
    .suggestion-card .tier-label {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
    }
    .tier-premium { background-color: #e9ecef; color: #495057; }
    .tier-standard { background-color: #dee2e6; color: #495057; }
    .tier-budget { background-color: #d4edda; color: #155724; }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Database helpers
# ------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_all_products(conn):
    """Return all store products for the Quick Price Check."""
    cur = conn.cursor()
    cur.execute("""
        SELECT mp.name, sp.store_name, sp.product_name, sp.price,
               sp.is_on_special, sp.package_size, sp.unit_type,
               sp.unit_price_per_100, sp.deep_link_url
        FROM store_products sp
        JOIN master_products mp ON mp.id = sp.master_product_id
        ORDER BY mp.name, sp.unit_price_per_100
    """)
    return cur.fetchall()


def get_store_products_for_master(conn, master_product_id):
    """Fetch all store products for a master product."""
    cur = conn.cursor()
    cur.execute("""
        SELECT sp.id, sp.store_name, sp.product_name, sp.brand_tier,
               sp.price, sp.is_on_special, sp.package_size, sp.unit_type,
               sp.unit_price_per_100, sp.deep_link_url
        FROM store_products sp
        WHERE sp.master_product_id = ?
        ORDER BY sp.unit_price_per_100
    """, (master_product_id,))
    rows = cur.fetchall()
    products = []
    for r in rows:
        products.append(StoreProduct(
            id=r[0],
            store_name=r[1],
            product_name=r[2],
            brand_tier=r[3],
            price=r[4],
            is_on_special=bool(r[5]),
            package_size=r[6],
            unit_type=r[7],
            unit_price_per_100=r[8],
            deep_link_url=r[9],
        ))
    return products


def add_weekly_sale_item(conn, product_name, store_name, special_price):
    """
    Create or update a master product and a store product for a temporary weekly
    sale item, ensure it is on the active shopping list, and return the
    master_product_id so the main page can re-run the optimisations.
    """
    cur = conn.cursor()

    # Normalise the product name for a clean master record.
    product_name = product_name.strip()

    # Reuse an existing master product if the name matches exactly.
    cur.execute("SELECT id FROM master_products WHERE name = ?", (product_name,))
    row = cur.fetchone()
    if row:
        master_id = row[0]
    else:
        cur.execute(
            "INSERT INTO master_products (name, category, is_staple) VALUES (?, ?, ?)",
            (product_name, "Weekly Specials", 0),
        )
        master_id = cur.lastrowid

    # Update or insert the store product for this special.
    cur.execute(
        "SELECT id FROM store_products WHERE master_product_id = ? AND store_name = ?",
        (master_id, store_name),
    )
    row = cur.fetchone()
    cart_url = _build_add_to_cart_url(store_name, product_name)
    if row:
        cur.execute(
            """
            UPDATE store_products
            SET price = ?, is_on_special = 1, unit_price_per_100 = ?,
                deep_link_url = ?, product_name = ?
            WHERE id = ?
            """,
            (
                special_price,
                special_price,
                cart_url,
                f"{product_name} at {store_name}",
                row[0],
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO store_products (
                master_product_id, store_name, product_name, brand_tier,
                price, is_on_special, package_size, unit_type, unit_price_per_100, deep_link_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                master_id,
                store_name,
                f"{product_name} at {store_name}",
                "standard",
                special_price,
                1,
                1.0,
                "each",
                special_price,
                cart_url,
            ),
        )

    # Add the item to the shopping list once if it is not already there.
    cur.execute(
        "SELECT id FROM shopping_list WHERE master_product_id = ?",
        (master_id,),
    )
    if not cur.fetchone():
        cur.execute(
            """
            INSERT INTO shopping_list (master_product_id, preference_tier, quantity, assigned_store)
            VALUES (?, ?, ?, ?)
            """,
            (master_id, None, 1, store_name),
        )

    conn.commit()
    return master_id


def get_current_list_item_details(conn):
    """
    Return a list of dicts: for each shopping list item, include the item
    plus the best store product available for that item.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sl.id, sl.master_product_id, sl.preference_tier, sl.quantity,
               sl.assigned_store, mp.name AS master_name
        FROM shopping_list sl
        JOIN master_products mp ON mp.id = sl.master_product_id
    """)
    rows = cur.fetchall()
    results = []
    for r in rows:
        sl_id, master_id, pref_tier, qty, assigned_store, master_name = r
        products = get_store_products_for_master(conn, master_id)
        # Filter to assigned_store preference if set
        if assigned_store:
            filtered = [p for p in products if p.store_name == assigned_store]
        else:
            filtered = products
        # If preference_tier set, filter by it
        if pref_tier:
            tiered = [p for p in filtered if p.brand_tier == pref_tier]
            if tiered:
                filtered = tiered
        best = filtered[0] if filtered else (products[0] if products else None)
        results.append({
            "sl_id": sl_id,
            "master_name": master_name,
            "preference_tier": pref_tier,
            "assigned_store": assigned_store,
            "best_product": best,
            "all_products": products,
            "quantity": qty,
        })
    return results


def get_specials_for_list(conn):
    """
    Find all items in the shopping list where the best available store product
    is on special, and calculate the savings compared to the next-best option.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sl.id, sl.master_product_id, sl.preference_tier, sl.assigned_store,
               mp.name AS master_name
        FROM shopping_list sl
        JOIN master_products mp ON mp.id = sl.master_product_id
    """)
    specials = []
    for r in cur.fetchall():
        sl_id, master_id, pref_tier, assigned_store, master_name = r
        products = get_store_products_for_master(conn, master_id)
        if not products:
            continue

        # Pick the best product based on current constraints
        if assigned_store:
            filtered = [p for p in products if p.store_name == assigned_store]
        else:
            filtered = products
        if pref_tier:
            tiered = [p for p in filtered if p.brand_tier == pref_tier]
            if tiered:
                filtered = tiered

        best = filtered[0] if filtered else products[0]
        if not best.is_on_special:
            continue

        # Find the next-best alternative (excluding the special one)
        rest = [p for p in products if p.id != best.id]
        next_best = rest[0] if rest else None

        savings = 0.0
        if next_best:
            savings = next_best.price - best.price

        specials.append({
            "sl_id": sl_id,
            "master_name": master_name,
            "product_name": best.product_name,
            "store_name": best.store_name,
            "price": best.price,
            "savings": savings,
            "next_best": next_best,
            "package_size": best.package_size,
            "unit_type": best.unit_type,
            "unit_price": best.unit_price_per_100,
        })
    return specials


def get_substitution_suggestions(conn):
    """
    For each shopping list item, check if a lower-tier or generic alternative
    has a significantly better unit_price_per_100.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sl.id, sl.master_product_id, sl.preference_tier, sl.assigned_store,
               mp.name AS master_name
        FROM shopping_list sl
        JOIN master_products mp ON mp.id = sl.master_product_id
    """)
    suggestions = []
    for r in cur.fetchall():
        sl_id, master_id, pref_tier, assigned_store, master_name = r
        products = get_store_products_for_master(conn, master_id)
        if not products:
            continue

        # Determine current product
        if assigned_store:
            filtered = [p for p in products if p.store_name == assigned_store]
        else:
            filtered = products
        if pref_tier:
            tiered = [p for p in filtered if p.brand_tier == pref_tier]
            if tiered:
                filtered = tiered

        current = filtered[0] if filtered else products[0]
        if not current:
            continue

        # Find cheaper alternatives (not the same store product)
        cheaper = [p for p in products if p.id != current.id and p.price < current.price]
        if not cheaper:
            continue

        # Pick the cheapest alternative
        alt = min(cheaper, key=lambda p: p.price)
        savings = current.price - alt.price
        unit_savings = current.unit_price_per_100 - alt.unit_price_per_100

        # Only suggest if savings are meaningful
        if savings < 0.10:
            continue

        suggestions.append({
            "sl_id": sl_id,
            "master_name": master_name,
            "current_product": current,
            "alt_product": alt,
            "savings": savings,
            "unit_savings": unit_savings,
        })
    return suggestions


def swap_shopping_list_item(sl_id, new_brand_tier, new_store_name):
    """Update the shopping list item to the new tier and store."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.execute("""
        UPDATE shopping_list
        SET preference_tier = ?, assigned_store = ?
        WHERE id = ?
    """, (new_brand_tier, new_store_name, sl_id))
    conn.commit()
    conn.close()
    # Clear cached data so next run picks up the change
    st.cache_data.clear()


# ------------------------------------------------------------------
# Sidebar controls
# ------------------------------------------------------------------
st.sidebar.title("Shop Settings")

st.sidebar.markdown("---")
st.sidebar.markdown("### Active Stores")
active_co = st.sidebar.checkbox("Coles", value=True)
active_wo = st.sidebar.checkbox("Woolworths", value=True)
active_al = st.sidebar.checkbox("Aldi", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### Inconvenience Tax")
threshold = st.sidebar.slider(
    "Convenience threshold ($)",
    min_value=0.00,
    max_value=10.00,
    value=3.00,
    step=0.50,
    help="If total savings at a store trip are below this value, consolidate to avoid an extra trip.",
)

st.sidebar.markdown("---")
active_stores = []
if active_co:
    active_stores.append("Coles")
if active_wo:
    active_stores.append("Woolworths")
if active_al:
    active_stores.append("Aldi")

if not active_stores:
    st.sidebar.error("Please select at least one store.")

st.sidebar.markdown("---")

# Open the database connection early so the sidebar sync button can use it.
conn = get_db_connection()

st.sidebar.markdown("### Google Sheet Sync")

DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1nxW1c1EotnDG-J1iLZ9RuMegcJrjPN-gs3eVyfRRlTA/edit?gid=0#gid=0"

google_sheet_url = st.sidebar.text_input(
    "Google Sheet URL",
    value=DEFAULT_SHEET_URL,
    placeholder="https://docs.google.com/spreadsheets/d/...",
    help="Paste a Google Sheet URL with a 'Shopping List' tab. The sheet will be read live when you click Sync.",
)

sheet_name = st.sidebar.text_input("Sheet name", value="Sheet1")
item_column = st.sidebar.text_input("Item column name", value="Item")

if st.sidebar.button("Sync Shopping List", use_container_width=True, type="secondary"):
    if not google_sheet_url.strip():
        st.sidebar.error("Please enter a Google Sheet URL first.")
    else:
        try:
            matched, fallback = sync_shopping_list_from_sheet(
                conn, google_sheet_url, sheet_name=sheet_name, item_column=item_column
            )
            total = len(matched) + len(fallback)
            st.sidebar.success(f"Synced {total} item(s) from Google Sheets.")
            if fallback:
                st.sidebar.warning(
                    f"{len(fallback)} item(s) added as fallbacks with placeholder prices: "
                    f"{', '.join(name for _, name, _, _ in fallback)}"
                )
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Sync failed: {e}")

st.sidebar.markdown("---")

# ------------------------------------------------------------------
# Main page
# ------------------------------------------------------------------
st.title("Australian Grocery Price Optimizer")
st.markdown("Compare prices across Coles, Woolworths and Aldi. Optimise your weekly shop with the Inconvenience Tax.")

if not active_stores:
    st.warning("Please select at least one store from the sidebar to see optimised results.")
    st.stop()

# ------------------------------------------------------------------
# Main content
# ------------------------------------------------------------------

# Load shopping list and optimizer data
shopping_list = load_shopping_list(conn)
store_products_map = {}
for item in shopping_list:
    store_products_map[item.master_product_id] = load_store_products(
        conn, item.master_product_id, active_stores
    )

available_items = [item for item in shopping_list if store_products_map[item.master_product_id]]
unavailable = [item for item in shopping_list if not store_products_map[item.master_product_id]]

# Run optimizations
raw_opt = optimize_raw(available_items, store_products_map)
raw_lists = format_store_lists(raw_opt)

adv_opt = optimize_advanced(raw_opt, store_products_map, threshold, active_stores)
adv_lists = format_store_lists(adv_opt)

raw_total = sum(sum(oi.store_product.price for oi in items) for items in raw_lists.values())
adv_total = sum(sum(oi.store_product.price for oi in items) for items in adv_lists.values())

# ------------------------------------------------------------------
# 1. Weekly Specials Alert
# ------------------------------------------------------------------
specials = get_specials_for_list(conn)
if specials:
    st.markdown("## Weekly Specials Alert")
    total_special_savings = sum(s["savings"] for s in specials)
    cols = st.columns(len(specials))
    for i, s in enumerate(specials):
        with cols[i]:
            st.markdown(f"""
                <div class="alert-banner">
                    <div style="font-size:20px; font-weight:800;">SPECIAL</div>
                    <div style="font-size:16px; margin-top:4px;">{s['product_name']}</div>
                    <div style="font-size:13px; margin-top:4px;">at {s['store_name']} — ${s['price']:.2f}</div>
                    <div style="font-size:14px; margin-top:8px; font-weight:600;">
                        Save ${s['savings']:.2f} vs {s['next_best'].product_name if s['next_best'] else 'next best'}
                    </div>
                </div>
            """, unsafe_allow_html=True)
    st.markdown(f"**Total special savings: ${total_special_savings:.2f}**")

# ------------------------------------------------------------------
# 2. Smart Savings Recommendations
# ------------------------------------------------------------------
suggestions = get_substitution_suggestions(conn)
if suggestions:
    st.markdown("---")
    st.markdown("## Smart Savings Recommendations")
    st.markdown("Swap to a better-value alternative to save money on your next shop.")

    for s in suggestions:
        cur = s["current_product"]
        alt = s["alt_product"]
        sl_id = s["sl_id"]
        tier_class = f"tier-{alt.brand_tier}"

        with st.container():
            st.markdown(f"""
                <div class="suggestion-card">
                    <div class="title">{s['master_name']}</div>
                    <div style="color:#6c757d; font-size:13px; margin-bottom:6px;">
                        Currently: {cur.product_name} ({cur.store_name}, {cur.brand_tier.title()})
                        — ${cur.price:.2f}
                    </div>
                    <div style="display:flex; align-items:center; margin-bottom:4px;">
                        <span class="tier-label {tier_class}">{alt.brand_tier.title()}</span>
                        <span style="font-size:14px; color:#212529;">
                            <strong>{alt.product_name}</strong> at {alt.store_name}
                            — ${alt.price:.2f}
                        </span>
                    </div>
                    <div class="savings">
                        Save ${s['savings']:.2f} (unit price: ${alt.unit_price_per_100:.4f}/100{alt.unit_type})
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # Use a button with a unique key based on sl_id
            if st.button(
                f"Swap to {alt.product_name} at {alt.store_name}",
                key=f"swap_{sl_id}_{alt.id}",
                use_container_width=True,
                type="primary",
            ):
                swap_shopping_list_item(sl_id, alt.brand_tier, alt.store_name)
                st.success(f"Swapped to {alt.product_name} at {alt.store_name}! Refreshing...")
                st.rerun()

# ------------------------------------------------------------------
# Top summary metrics
# ------------------------------------------------------------------
st.markdown("---")
cols = st.columns(4)
cols[0].metric("Active Stores", len(active_stores))
cols[1].metric("Shopping List Items", len(shopping_list))
cols[2].metric("Raw Mode Stores", len(raw_lists))
cols[3].metric("Advanced Mode Stores", len(adv_lists))

# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["Split Shopping Lists", "Quick Price Check", "Weekly Deals & Catalogues"])

# ------------------------------------------------------------------
# Tab 1: Split Shopping Lists
# ------------------------------------------------------------------
with tab1:
    st.markdown("### Optimised Shopping Lists")
    st.markdown("Toggle between **Raw** (cheapest per item) and **Advanced** (with Inconvenience Tax) views.")

    mode = st.radio("", ["Raw Optimisation", "Advanced Optimisation"], horizontal=True)

    if mode == "Raw Optimisation":
        display_lists = raw_lists
        display_total = raw_total
        mode_label = "Raw"
    else:
        display_lists = adv_lists
        display_total = adv_total
        mode_label = "Advanced"

    if unavailable:
        st.warning(f"{len(unavailable)} item(s) not available at any selected store.")

    for store_name, items in display_lists.items():
        store_total = sum(oi.store_product.price for oi in items)
        with st.container():
            st.markdown("---")
            st.markdown(f"#### {store_name} — {len(items)} item(s) — **${store_total:.2f}**")

            for oi in items:
                sp = oi.store_product
                col1, col2, col3 = st.columns([3, 3, 2])

                with col1:
                    name_line = sp.product_name
                    if sp.is_on_special:
                        name_line += ' <span class="special-badge">SPECIAL</span>'
                    st.markdown(name_line, unsafe_allow_html=True)

                with col2:
                    st.markdown(f"${sp.price:.2f} · {sp.unit_price_per_100:.4f}/100{sp.unit_type}")
                    if oi.savings_vs_next > 0 and mode == "Raw Optimisation":
                        st.markdown(f"<small>Saves ${oi.savings_vs_next:.2f} vs {oi.next_best_store}</small>", unsafe_allow_html=True)
                    if oi.assigned_store:
                        st.markdown(f"<small>Assigned: {oi.assigned_store}</small>", unsafe_allow_html=True)

                with col3:
                    cart_url = _build_add_to_cart_url(sp.store_name, oi.name)
                    target = {
                        "Coles": "_coles",
                        "Woolworths": "_woolies",
                        "Aldi": "_doordash",
                    }.get(sp.store_name, "_blank")
                    st.markdown(
                        f'<a href="{cart_url}" target="{target}" style="display:inline-block;padding:6px 14px;background:#0073e6;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Add to Cart</a>',
                        unsafe_allow_html=True,
                    )

    st.markdown("---")
    st.markdown(f"### Grand Total: **${display_total:.2f}**  ·  {mode_label} mode")

# ------------------------------------------------------------------
# Tab 2: Quick Price Check (Interactive Search Engine)
# ------------------------------------------------------------------
with tab2:
    st.markdown("### Quick Price Check")
    st.markdown("Search our internal price database first, or fall back to live retailer searches.")

    search_col, store_col = st.columns([3, 1])
    with search_col:
        search_query = st.text_input(
            "Search for a product (e.g. 'Strawberry Jam', 'Milk', 'Coffee')",
            placeholder="Type product name...",
            key="quick_search_query",
        )
    with store_col:
        store_filter = st.selectbox(
            "Store filter",
            ["All Stores", "Coles Only", "Woolworths Only", "ALDI Only"],
            key="quick_store_filter",
        )

    all_products = get_all_products(conn)

    if search_query:
        search_lower = search_query.lower().strip()

        # Map the store filter to the allowed store names.
        filter_map = {
            "All Stores": ALL_STORES,
            "Coles Only": ["Coles"],
            "Woolworths Only": ["Woolworths"],
            "ALDI Only": ["Aldi"],
        }
        allowed = filter_map.get(store_filter, ALL_STORES)

        filtered = [
            p for p in all_products
            if (search_lower in p[0].lower() or search_lower in p[2].lower())
            and p[1] in allowed
        ]

        if filtered:
            grouped = {}
            for p in filtered:
                master = p[0]
                grouped.setdefault(master, []).append(p)

            for master_name, products in grouped.items():
                st.markdown("---")
                st.markdown(f"#### {master_name}")

                cheapest = min(products, key=lambda p: p[7])
                table_data = []
                for p in products:
                    _, store, prod_name, price, is_special, size, unit, unit_price, link = p
                    is_cheapest = (p[1] == cheapest[1] and p[7] == cheapest[7])
                    table_data.append({
                        "Store": store,
                        "Product": prod_name,
                        "Price": f"${price:.2f}",
                        "Unit Price": f"${unit_price:.4f}/100{unit}",
                        "Size": f"{size:.0f}{unit}",
                        "Special": "✅" if is_special else "",
                        "Best Value": "🏆 Cheapest" if is_cheapest else "",
                        "Link": link,
                    })

                st.dataframe(
                    table_data,
                    column_order=["Store", "Product", "Price", "Unit Price", "Size", "Special", "Best Value"],
                    use_container_width=True,
                    hide_index=True,
                )

                st.markdown(
                    f"**Best value:** {cheapest[2]} at **{cheapest[1]}** — "
                    f"${cheapest[3]:.2f} (${cheapest[7]:.4f}/100{cheapest[6]})"
                )
        else:
            # Local database fallback: dynamic live search buttons.
            st.warning(f"'{search_query}' is not in our local database yet.")
            st.markdown("**Check live prices on:**")
            q_encoded = urllib.parse.quote(search_query)
            live_cols = st.columns(3)
            with live_cols[0]:
                st.markdown(
                    f'<a href="https://www.coles.com.au/search?q={q_encoded}" target="_coles" '
                    f'style="display:inline-block;padding:10px 16px;background:#e60028;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Coles</a>',
                    unsafe_allow_html=True,
                )
            with live_cols[1]:
                st.markdown(
                    f'<a href="https://www.woolworths.com.au/shop/search/products?searchTerm={q_encoded}" target="_woolies" '
                    f'style="display:inline-block;padding:10px 16px;background:#007dc5;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Woolworths</a>',
                    unsafe_allow_html=True,
                )
            with live_cols[2]:
                st.markdown(
                    f'<a href="https://www.doordash.com/p/aldi-australia" target="_doordash" '
                    f'style="display:inline-block;padding:10px 16px;background:#eb1700;color:white;border-radius:6px;text-decoration:none;font-weight:600;">DoorDash / ALDI</a>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Type a product name above and choose a store filter to see comparisons.")

# ------------------------------------------------------------------
# Tab 3: Weekly Deals & Catalogues
# ------------------------------------------------------------------
with tab3:
    st.markdown("### Weekly Deals & Catalogues")
    st.markdown("Quick links to this week’s catalogues and a form to add temporary sale items to your list.")

    link_cols = st.columns(3)
    with link_cols[0]:
        st.markdown(
            '<a href="https://www.coles.com.au/specials/half-price" target="_coles" '
            'style="display:inline-block;padding:12px 18px;background:#e60028;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Coles Half-Price Specials</a>',
            unsafe_allow_html=True,
        )
    with link_cols[1]:
        st.markdown(
            '<a href="https://www.woolworths.com.au/shop/catalogue" target="_woolies" '
            'style="display:inline-block;padding:12px 18px;background:#007dc5;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Woolworths Catalogue & Deals</a>',
            unsafe_allow_html=True,
        )
    with link_cols[2]:
        st.markdown(
            '<a href="https://www.aldi.com.au/en/special-buys/" target="_doordash" '
            'style="display:inline-block;padding:12px 18px;background:#eb1700;color:white;border-radius:6px;text-decoration:none;font-weight:600;">ALDI Special Buys</a>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("#### Add a temporary weekly sale item")
    with st.form("weekly_sale_form", clear_on_submit=True):
        sale_cols = st.columns([3, 2, 2, 1])
        with sale_cols[0]:
            sale_name = st.text_input("Product name", placeholder="e.g. Tim Tams 200g", key="sale_name")
        with sale_cols[1]:
            sale_store = st.selectbox("Store on sale at", ["Coles", "Woolworths", "Aldi"], key="sale_store")
        with sale_cols[2]:
            sale_price = st.number_input("Special price ($)", min_value=0.0, step=0.10, key="sale_price")
        with sale_cols[3]:
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("Add", use_container_width=True, type="primary")

        if submitted:
            if not sale_name.strip() or sale_price <= 0:
                st.error("Please enter a product name and a special price greater than 0.")
            else:
                add_weekly_sale_item(conn, sale_name.strip(), sale_store, float(sale_price))
                st.cache_data.clear()
                st.success(f"Added {sale_name.strip()} at {sale_store} for ${sale_price:.2f} to your shopping list.")
                st.rerun()

conn.close()
