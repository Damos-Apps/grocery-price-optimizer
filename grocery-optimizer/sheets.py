"""
sheets.py — Google Sheets integration for the grocery price optimizer.

Reads a shopping list from a public Google Sheet using the standard gviz CSV
export endpoint (`/gviz/tq?tqx=out:csv`), matches the item names to the
master products in the local SQLite database, and replaces the active shopping
list with the matched items.

This avoids Replit connectors and `st.connection` so it works anywhere,
including Streamlit Cloud.
"""

import re
import sqlite3
from difflib import get_close_matches
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import pandas as pd

ALL_STORES = ["Coles", "Woolworths", "Aldi"]


def extract_spreadsheet_id(url: str) -> Optional[str]:
    """Extract a Google Sheets spreadsheet ID from a URL or raw ID string."""
    if not url or not url.strip():
        return None
    url = url.strip()
    # If it's already a 44-character ID, return it.
    if re.match(r"^[a-zA-Z0-9_-]{44}$", url):
        return url
    # Standard URL formats
    patterns = [
        r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
        r"^[a-zA-Z0-9_-]+\.docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)",
        r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_gid(url: str) -> Optional[str]:
    """Extract the sheet gid parameter from a Google Sheets URL if present."""
    if not url:
        return None
    parsed = urlparse(url)
    query = parse_qs(parsed.fragment or parsed.query)
    # gid is usually in the fragment (#gid=0) or query string
    for key in ("gid",):
        if key in query:
            return query[key][0]
    # Fallback: look for gid= anywhere in the URL string
    match = re.search(r"[?#&]gid=(\d+)", url)
    if match:
        return match.group(1)
    return None


def _build_export_url(spreadsheet_id: str, sheet_name: str, gid: Optional[str]) -> str:
    """Build the public gviz CSV export URL for a Google Sheet."""
    base = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq"
    params = "tqx=out:csv"
    if gid:
        params += f"&gid={gid}"
    elif sheet_name:
        # URL-encode the sheet name to handle spaces and special characters.
        from urllib.parse import quote
        params += f"&sheet={quote(sheet_name)}"
    return f"{base}?{params}"


def _normalise(name: str) -> str:
    """Lowercase, strip, and collapse whitespace for fuzzy comparison."""
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _find_column_index(header: List[str], preferred_name: str) -> Optional[int]:
    """Find the best matching column index in the header row."""
    preferred = _normalise(preferred_name)
    headers = [_normalise(h) for h in header]

    # Exact match
    if preferred in headers:
        return headers.index(preferred)

    # Common aliases
    aliases = {
        "item": ["item", "product", "name", "food", "ingredient"],
        "quantity": ["qty", "quantity", "amount"],
        "store": ["store", "shop", "assigned store"],
    }
    for alias in aliases.get(preferred, [preferred]):
        for i, h in enumerate(headers):
            if alias in h or h in alias:
                return i
    return None


def _parse_sheet_rows(
    rows: List[List[str]], item_column: str = "Item"
) -> List[Tuple[str, int, Optional[str]]]:
    """
    Parse raw sheet rows into a list of (item_name, quantity, assigned_store).

    Handles:
      - A header row with column names (Item, Quantity, Store, etc.)
      - A title/header cell such as 'shopping' in a single-column list
      - No header row (first column assumed to be items)
      - Empty / whitespace rows
    """
    if not rows:
        return []

    # Common single-column header/title words that are not actual items.
    skip_words = {"shopping", "list", "items", "groceries", "shop", "buy"}

    # Detect header row: first non-empty row that contains a string resembling
    # the item column name (or any sensible text). If the first row is all text,
    # treat it as a header.
    first_row = rows[0]
    first_nonempty = [c for c in first_row if str(c).strip()]
    looks_like_header = False
    if first_nonempty:
        preferred_norm = _normalise(item_column)
        header_norms = [_normalise(c) for c in first_nonempty]
        if any(preferred_norm in h or h in preferred_norm for h in header_norms):
            looks_like_header = True
        elif all(any(c.isalpha() for c in str(cell)) for cell in first_nonempty):
            # Looks like a text header rather than a single product name
            looks_like_header = True
        elif len(first_nonempty) == 1 and header_norms[0] in skip_words:
            # Single-column sheets often have a title like "shopping"
            looks_like_header = True

    if looks_like_header:
        header = first_row
        data_rows = rows[1:]
        item_col = _find_column_index(header, item_column)
        if item_col is None:
            item_col = 0
        qty_col = _find_column_index(header, "Quantity")
        store_col = _find_column_index(header, "Store")
    else:
        data_rows = rows
        item_col = 0
        qty_col = None
        store_col = None

    items: List[Tuple[str, int, Optional[str]]] = []
    for row in data_rows:
        if not row or item_col >= len(row):
            continue
        item_name = str(row[item_col]).strip()
        if not item_name:
            continue

        quantity = 1
        if qty_col is not None and qty_col < len(row):
            try:
                quantity = int(float(row[qty_col]))
                if quantity < 1:
                    quantity = 1
            except (ValueError, TypeError):
                pass

        assigned_store = None
        if store_col is not None and store_col < len(row):
            store = str(row[store_col]).strip()
            if store in ALL_STORES:
                assigned_store = store

        items.append((item_name, quantity, assigned_store))

    return items


def fetch_sheet_items(
    spreadsheet_url: str,
    sheet_name: str = "Sheet1",
    item_column: str = "Item",
) -> List[Tuple[str, int, Optional[str]]]:
    """
    Fetch the shopping list from a public Google Sheet using the gviz CSV export.

    Returns a list of (item_name, quantity, assigned_store) tuples.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ValueError("Could not extract a valid Google Sheets spreadsheet ID from the URL.")

    gid = extract_gid(spreadsheet_url)
    export_url = _build_export_url(spreadsheet_id, sheet_name, gid)

    try:
        df = pd.read_csv(export_url, dtype=str, keep_default_na=False)
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch the Google Sheet CSV export. "
            f"Make sure the sheet is public (Share → Anyone with the link can view). Error: {e}"
        ) from e

    # Convert DataFrame to list of rows including the header row.
    rows = [df.columns.tolist()] + df.values.tolist()
    return _parse_sheet_rows(rows, item_column=item_column)


def _get_or_create_master_product(
    cur: sqlite3.Cursor, name: str, category: str = "Groceries", is_staple: bool = True
) -> int:
    """Get an existing master product by name or create a new one."""
    norm = _normalise(name)
    cur.execute("SELECT id, name FROM master_products")
    for mid, mname in cur.fetchall():
        if _normalise(mname) == norm:
            return mid
    cur.execute(
        "INSERT INTO master_products (name, category, is_staple) VALUES (?, ?, ?)",
        (name, category, int(is_staple)),
    )
    return cur.lastrowid


def _ensure_fallback_store_products(cur: sqlite3.Cursor, master_product_id: int) -> None:
    """
    Create placeholder store products for a fallback item so it still appears
    in the optimised shopping list. Existing products for this master product
    are left untouched.
    """
    cur.execute(
        "SELECT store_name FROM store_products WHERE master_product_id = ?",
        (master_product_id,),
    )
    existing_stores = {row[0] for row in cur.fetchall()}

    for store in ALL_STORES:
        if store in existing_stores:
            continue
        # Use a small placeholder price so the item is included in totals.
        price = 0.00
        package_size = 1.0
        unit_type = "each"
        unit_price_per_100 = 0.0
        product_name = f"{store} - {cur.execute('SELECT name FROM master_products WHERE id = ?', (master_product_id,)).fetchone()[0]} (price needed)"
        query = cur.execute(
            "SELECT name FROM master_products WHERE id = ?", (master_product_id,)
        ).fetchone()[0]
        from urllib.parse import quote
        deep_link_url = f"https://www.google.com/search?q={quote(query + ' ' + store)}"
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
                store,
                product_name,
                "standard",
                price,
                0,
                package_size,
                unit_type,
                unit_price_per_100,
                deep_link_url,
            ),
        )


def _match_items_to_master(
    conn: sqlite3.Connection,
    sheet_items: List[Tuple[str, int, Optional[str]]],
) -> Tuple[List[Tuple[int, str, int, Optional[str]]], List[Tuple[int, str, int, Optional[str]]]]:
    """
    Match sheet item names to master_product ids.

    Returns:
      - matched: list of (master_product_id, item_name, quantity, assigned_store)
      - fallback: list of (master_product_id, item_name, quantity, assigned_store)
                 for items that did not match an existing product and were
                 created as new fallback master products.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM master_products ORDER BY id")
    masters = {row[0]: row[1] for row in cur.fetchall()}
    normalised_masters = {mid: _normalise(name) for mid, name in masters.items()}

    matched: List[Tuple[int, str, int, Optional[str]]] = []
    fallback: List[Tuple[int, str, int, Optional[str]]] = []

    for item_name, quantity, assigned_store in sheet_items:
        norm = _normalise(item_name)
        # 1. Exact normalised match
        match_id = next(
            (mid for mid, name_norm in normalised_masters.items() if name_norm == norm),
            None,
        )
        # 2. Substring match in either direction
        if match_id is None:
            for mid, name_norm in normalised_masters.items():
                if norm in name_norm or name_norm in norm:
                    match_id = mid
                    break
        # 3. Fuzzy match (built-in difflib) - use a slightly lower cutoff to be more forgiving
        if match_id is None:
            close = get_close_matches(norm, normalised_masters.values(), n=1, cutoff=0.5)
            if close:
                matched_name = close[0]
                match_id = next(
                    mid for mid, name_norm in normalised_masters.items() if name_norm == matched_name
                )

        if match_id is None:
            # Create a fallback master product so the item is never excluded.
            master_id = _get_or_create_master_product(cur, item_name, category="Groceries", is_staple=False)
            _ensure_fallback_store_products(cur, master_id)
            conn.commit()
            # Update local lookup so the same item in the sheet doesn't duplicate.
            masters[master_id] = item_name
            normalised_masters[master_id] = norm
            fallback.append((master_id, item_name, quantity, assigned_store))
        else:
            matched.append((match_id, item_name, quantity, assigned_store))

    return matched, fallback


def sync_shopping_list_from_sheet(
    conn: sqlite3.Connection,
    spreadsheet_url: str,
    sheet_name: str = "Sheet1",
    item_column: str = "Item",
) -> Tuple[List[Tuple[int, str, int, Optional[str]]], List[Tuple[int, str, int, Optional[str]]]]:
    """
    Replace the current shopping_list with items fetched from the Google Sheet.

    Returns (matched, fallback) for display to the user. Every sheet row is
    included in the shopping list; rows that could not be matched to an existing
    product become new fallback products with placeholder prices.
    """
    sheet_items = fetch_sheet_items(spreadsheet_url, sheet_name=sheet_name, item_column=item_column)
    matched, fallback = _match_items_to_master(conn, sheet_items)

    cur = conn.cursor()
    cur.execute("DELETE FROM shopping_list")
    for master_id, _, quantity, assigned_store in matched + fallback:
        cur.execute(
            """
            INSERT INTO shopping_list (master_product_id, preference_tier, quantity, assigned_store)
            VALUES (?, ?, ?, ?)
            """,
            (master_id, None, quantity, assigned_store),
        )
    conn.commit()
    return matched, fallback
