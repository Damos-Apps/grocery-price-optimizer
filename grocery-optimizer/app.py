import streamlit as st
import sqlite3
import os
import sys

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
)

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
# Custom CSS (Streamlit default styling, minimal additions)
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
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Database helpers
# ------------------------------------------------------------------
@st.cache_data(ttl=30)
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

# ------------------------------------------------------------------
# Main page
# ------------------------------------------------------------------
st.title("Australian Grocery Price Optimizer")
st.markdown("Compare prices across Coles, Woolworths and Aldi. Optimise your weekly shop with the Inconvenience Tax.")

# ------------------------------------------------------------------
# Run optimizer if stores are selected
# ------------------------------------------------------------------
if active_stores:
    conn = get_db_connection()

    # Load shopping list
    shopping_list = load_shopping_list(conn)
    store_products_map = {}
    for item in shopping_list:
        store_products_map[item.master_product_id] = load_store_products(
            conn, item.master_product_id, active_stores
        )

    # Filter available items
    available_items = [item for item in shopping_list if store_products_map[item.master_product_id]]
    unavailable = [item for item in shopping_list if not store_products_map[item.master_product_id]]

    # Run optimizations
    raw_opt = optimize_raw(available_items, store_products_map)
    raw_lists = format_store_lists(raw_opt)

    adv_opt = optimize_advanced(raw_opt, store_products_map, threshold, active_stores)
    adv_lists = format_store_lists(adv_opt)

    # Raw totals
    raw_total = sum(sum(oi.store_product.price for oi in items) for items in raw_lists.values())
    adv_total = sum(sum(oi.store_product.price for oi in items) for items in adv_lists.values())

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
    tab1, tab2 = st.tabs(["Split Shopping Lists", "Quick Price Check"])

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
                st.markdown(f"---")
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
                        if sp.deep_link_url:
                            st.markdown(
                                f'<a href="{sp.deep_link_url}" target="_blank" style="display:inline-block;padding:6px 14px;background:#0073e6;color:white;border-radius:6px;text-decoration:none;font-weight:600;">Add to Cart</a>',
                                unsafe_allow_html=True,
                            )

        st.markdown(f"---")
        st.markdown(f"### Grand Total: **${display_total:.2f}**  ·  {mode_label} mode")

    # ------------------------------------------------------------------
    # Tab 2: Quick Price Check
    # ------------------------------------------------------------------
    with tab2:
        st.markdown("### Quick Price Check")
        search_query = st.text_input("Search for a product (e.g. 'Strawberry Jam', 'Milk', 'Coffee')", placeholder="Type product name...")

        all_products = get_all_products(conn)

        if search_query:
            search_lower = search_query.lower()
            filtered = [
                p for p in all_products
                if search_lower in p[0].lower() or search_lower in p[2].lower()
            ]

            if not filtered:
                st.info("No matching products found.")
            else:
                # Group by master product name
                grouped = {}
                for p in filtered:
                    master = p[0]
                    grouped.setdefault(master, []).append(p)

                for master_name, products in grouped.items():
                    st.markdown(f"---")
                    st.markdown(f"#### {master_name}")

                    # Build comparison table
                    table_data = []
                    for p in products:
                        _, store, prod_name, price, is_special, size, unit, unit_price, link = p
                        table_data.append({
                            "Store": store,
                            "Product": prod_name,
                            "Price": f"${price:.2f}",
                            "Unit Price": f"${unit_price:.4f}/100{unit}",
                            "Size": f"{size:.0f}{unit}",
                            "Special": "Yes" if is_special else "No",
                            "Link": link,
                        })

                    st.dataframe(
                        table_data,
                        column_order=["Store", "Product", "Price", "Unit Price", "Size", "Special"],
                        use_container_width=True,
                        hide_index=True,
                    )

                    # Show cheapest
                    cheapest = min(products, key=lambda p: p[7])
                    st.markdown(f"Best value: **{cheapest[2]}** at **{cheapest[1]}** — ${cheapest[3]:.2f} (${cheapest[7]:.4f}/100{cheapest[6]})")
        else:
            st.info("Type a product name above to see price comparisons across all stores.")

    conn.close()
else:
    st.warning("Please select at least one store from the sidebar to see optimised results.")
