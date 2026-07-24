"""
sheets.py — Google Sheets integration for the grocery price optimizer.

Reads a shopping list from a Google Sheet, matches the item names to the
master products in the local SQLite database, and replaces the active
shopping list with the matched items.
"""

import os
import re
import sqlite3
from difflib import get_close_matches
from typing import List, Optional, Tuple

import requests

ALL_STORES = ["Coles", "Woolworths", "Aldi"]

CONNECTORS_HOSTNAME = os.environ.get("REPLIT_CONNECTORS_HOSTNAME", "connectors.replit.com")
BASE_URL = f"https://{CONNECTORS_HOSTNAME}/api/v2/proxy"
REPLIT_IDENTITY = os.environ.get("REPL_IDENTITY")


def _connector_headers() -> dict:
    if not REPLIT_IDENTITY:
        raise RuntimeError("REPL_IDENTITY is not set; cannot call the Google Sheets connector.")
    return {
        "X-Replit-Token": f"repl {REPLIT_IDENTITY}",
        "Connector-Name": "google-sheet",
        "Accept": "application/json",
    }


def _connector_json(method: str, path: str, body: Optional[dict] = None) -> dict:
    url = f"{BASE_URL}{path}"
    headers = _connector_headers()
    response = requests.request(method, url, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    return response.json()


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


def _normalise(name: str) -> str:
    """Lowercase, strip, and collapse whitespace for fuzzy comparison."""
    return re.sub(r"\s+", " ", name.strip().lower())


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
      - No header row (first column assumed to be items)
      - Empty / whitespace rows
    """
    if not rows:
        return []

    # Detect header row: first non-empty row that contains a string resembling
    # the item column name (or any sensible text). If the first row is all text,
    # treat it as a header.
    first_row = rows[0]
    first_nonempty = [c for c in first_row if c.strip()]
    looks_like_header = False
    if first_nonempty:
        preferred_norm = _normalise(item_column)
        header_norms = [_normalise(c) for c in first_nonempty]
        if any(preferred_norm in h or h in preferred_norm for h in header_norms):
            looks_like_header = True
        elif all(any(c.isalpha() for c in cell) for cell in first_nonempty):
            # Looks like a text header rather than a single product name
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
    sheet_name: str = "Shopping List",
    item_column: str = "Item",
) -> List[Tuple[str, int, Optional[str]]]:
    """
    Fetch the shopping list from a Google Sheet.

    Returns a list of (item_name, quantity, assigned_store) tuples.
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        raise ValueError("Could not extract a valid Google Sheets spreadsheet ID from the URL.")

    # Use A:Z to read all columns for the first 1000 rows.
    range_ref = f"{sheet_name}!A:Z"
    path = f"/v4/spreadsheets/{spreadsheet_id}/values/{range_ref}"
    payload = _connector_json("GET", path)

    rows = payload.get("values", [])
    if not rows:
        return []

    return _parse_sheet_rows(rows, item_column=item_column)


def _match_items_to_master(
    conn: sqlite3.Connection,
    sheet_items: List[Tuple[str, int, Optional[str]]],
) -> Tuple[List[Tuple[int, str, int, Optional[str]]], List[str]]:
    """
    Match sheet item names to master_product ids.

    Returns:
      - matched: list of (master_product_id, item_name, quantity, assigned_store)
      - unmatched: list of sheet item names that could not be matched
    """
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM master_products ORDER BY id")
    masters = {row[0]: row[1] for row in cur.fetchall()}
    normalised_masters = {mid: _normalise(name) for mid, name in masters.items()}

    matched: List[Tuple[int, str, int, Optional[str]]] = []
    unmatched: List[str] = []

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
        # 3. Fuzzy match (built-in difflib)
        if match_id is None:
            close = get_close_matches(norm, normalised_masters.values(), n=1, cutoff=0.6)
            if close:
                matched_name = close[0]
                match_id = next(
                    mid for mid, name_norm in normalised_masters.items() if name_norm == matched_name
                )

        if match_id is None:
            unmatched.append(item_name)
        else:
            matched.append((match_id, item_name, quantity, assigned_store))

    return matched, unmatched


def sync_shopping_list_from_sheet(
    conn: sqlite3.Connection,
    spreadsheet_url: str,
    sheet_name: str = "Shopping List",
    item_column: str = "Item",
) -> Tuple[List[Tuple[int, str, int, Optional[str]]], List[str]]:
    """
    Replace the current shopping_list with items fetched from the Google Sheet.

    Returns (matched, unmatched) for display to the user.
    """
    sheet_items = fetch_sheet_items(spreadsheet_url, sheet_name=sheet_name, item_column=item_column)
    matched, unmatched = _match_items_to_master(conn, sheet_items)

    cur = conn.cursor()
    cur.execute("DELETE FROM shopping_list")
    for master_id, _, quantity, assigned_store in matched:
        cur.execute(
            """
            INSERT INTO shopping_list (master_product_id, preference_tier, quantity, assigned_store)
            VALUES (?, ?, ?, ?)
            """,
            (master_id, None, quantity, assigned_store),
        )
    conn.commit()
    return matched, unmatched
