"""
optimizer.py - Split-list shopping optimizer with raw and advanced modes.

Reads the active shopping list from the database and assigns each item to the
optimal store(s), then prints two scenarios:

1. Raw mode: cheapest per-unit price at any store (no threshold).
2. Advanced mode: applies an Inconvenience Tax so that tiny savings at a
   "singleton" store are consolidated to avoid an extra trip.

Usage:
    python3 grocery-optimizer/optimizer.py
    python3 grocery-optimizer/optimizer.py --stores Coles Aldi
    python3 grocery-optimizer/optimizer.py --threshold 2.50
"""

import sqlite3
import os
import argparse
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "grocery.db")

ALL_STORES = ["Coles", "Woolworths", "Aldi"]


@dataclass
class ShoppingListItem:
    id: int
    master_product_id: int
    name: str
    category: str
    is_staple: bool
    preference_tier: Optional[str]
    quantity: int
    assigned_store: Optional[str]


@dataclass
class StoreProduct:
    id: int
    store_name: str
    product_name: str
    brand_tier: str
    price: float
    is_on_special: bool
    package_size: float
    unit_type: str
    unit_price_per_100: float
    deep_link_url: Optional[str]


@dataclass
class OptimizedItem:
    master_product_id: int
    name: str
    category: str
    is_staple: bool
    preference_tier: Optional[str]
    quantity: int
    assigned_store: Optional[str]
    chosen_store: str
    store_product: StoreProduct
    # Dollar savings vs next best store (positive = we saved money)
    savings_vs_next: float
    # The store and product we'd move to if consolidated
    next_best_store: Optional[str]
    next_best_product: Optional[StoreProduct]


def load_shopping_list(conn: sqlite3.Connection) -> List[ShoppingListItem]:
    cur = conn.cursor()
    cur.execute("""
        SELECT sl.id,
               sl.master_product_id,
               mp.name,
               mp.category,
               mp.is_staple,
               sl.preference_tier,
               sl.quantity,
               sl.assigned_store
        FROM shopping_list sl
        JOIN master_products mp ON mp.id = sl.master_product_id
        ORDER BY mp.is_staple DESC, mp.name
    """)
    rows = cur.fetchall()
    items: List[ShoppingListItem] = []
    for r in rows:
        items.append(ShoppingListItem(
            id=r[0],
            master_product_id=r[1],
            name=r[2],
            category=r[3],
            is_staple=bool(r[4]),
            preference_tier=r[5],
            quantity=r[6],
            assigned_store=r[7],
        ))
    return items


def load_store_products(
    conn: sqlite3.Connection,
    master_product_id: int,
    allowed_stores: List[str],
) -> List[StoreProduct]:
    cur = conn.cursor()
    placeholders = ", ".join("?" for _ in allowed_stores)
    cur.execute(f"""
        SELECT id,
               store_name,
               product_name,
               brand_tier,
               price,
               is_on_special,
               package_size,
               unit_type,
               unit_price_per_100,
               deep_link_url
        FROM store_products
        WHERE master_product_id = ? AND store_name IN ({placeholders})
        ORDER BY unit_price_per_100 ASC
    """, [master_product_id] + allowed_stores)
    products: List[StoreProduct] = []
    for r in cur.fetchall():
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


def filter_by_tier(
    products: List[StoreProduct],
    preference_tier: Optional[str],
) -> List[StoreProduct]:
    """If a tier preference is set, keep only products in that tier.
       Otherwise return all products unchanged."""
    if preference_tier is None:
        return products
    return [p for p in products if p.brand_tier == preference_tier]


def resolve_hard_assigned(
    item: ShoppingListItem,
    products: List[StoreProduct],
) -> Optional[StoreProduct]:
    """If the shopping list entry has an explicit store assignment, find that product."""
    if item.assigned_store is None:
        return None
    for p in products:
        if p.store_name == item.assigned_store:
            return p
    return None


def optimize_raw(
    shopping_list: List[ShoppingListItem],
    store_products_map: Dict[int, List[StoreProduct]],
) -> List[OptimizedItem]:
    """Pure cheapest-store-per-item optimization."""
    optimized: List[OptimizedItem] = []
    for item in shopping_list:
        products = store_products_map[item.master_product_id]
        if not products:
            continue

        # Hard-assigned store takes priority
        assigned = resolve_hard_assigned(item, products)
        if assigned:
            chosen = assigned
        else:
            # Filter by preference tier then pick cheapest
            candidates = filter_by_tier(products, item.preference_tier)
            if not candidates:
                candidates = products
            chosen = candidates[0]

        # Next best alternative (second cheapest)
        next_best = None
        for p in products:
            if p.store_name != chosen.store_name:
                next_best = p
                break

        # Dollar savings: how much we saved by picking chosen over next_best
        # Positive = chosen is cheaper (we saved money)
        savings = round(next_best.price - chosen.price, 4) if next_best else 0.0

        optimized.append(OptimizedItem(
            master_product_id=item.master_product_id,
            name=item.name,
            category=item.category,
            is_staple=item.is_staple,
            preference_tier=item.preference_tier,
            quantity=item.quantity,
            assigned_store=item.assigned_store,
            chosen_store=chosen.store_name,
            store_product=chosen,
            savings_vs_next=savings,
            next_best_store=next_best.store_name if next_best else None,
            next_best_product=next_best,
        ))
    return optimized


def optimize_advanced(
    raw_optimized: List[OptimizedItem],
    store_products_map: Dict[int, List[StoreProduct]],
    inconvenience_threshold: float = 3.00,
    allowed_stores: List[str] = None,
) -> List[OptimizedItem]:
    """
    Apply an Inconvenience Tax.

    After raw optimization assigns items to cheapest stores, we look at each
    store that ends up with only a few items. If the total dollar savings from
    shopping at that store (vs the next best alternative) is less than the
    threshold, we consolidate those items to avoid an extra trip.
    """
    if allowed_stores is None:
        allowed_stores = ALL_STORES

    # Start with raw assignments
    optimized = list(raw_optimized)
    changed = True
    max_iterations = 10
    iteration = 0

    while changed and iteration < max_iterations:
        changed = False
        iteration += 1

        # Group items by their chosen store
        current_store_items: Dict[str, List[OptimizedItem]] = {}
        for oi in optimized:
            current_store_items.setdefault(oi.chosen_store, []).append(oi)

        if len(current_store_items) <= 1:
            break

        # Find the store with the fewest items (candidate for consolidation)
        min_store = min(current_store_items.keys(), key=lambda s: len(current_store_items[s]))
        min_items = current_store_items[min_store]

        # Total dollar savings if we keep these items at min_store
        total_savings = sum(oi.savings_vs_next for oi in min_items)
        total_savings = round(total_savings, 2)

        # Check if all items have an alternative store
        can_consolidate = all(
            oi.next_best_store is not None for oi in min_items
        )

        # If savings < threshold, consolidate to next best stores
        if can_consolidate and total_savings < inconvenience_threshold:
            new_optimized: List[OptimizedItem] = []
            for oi in optimized:
                if oi.chosen_store == min_store:
                    # Re-optimize this item excluding the consolidated store
                    remaining_stores = [s for s in allowed_stores if s != min_store]
                    products = store_products_map[oi.master_product_id]
                    candidates = [p for p in products if p.store_name in remaining_stores]
                    if not candidates:
                        # Fallback: keep original
                        new_optimized.append(oi)
                        continue

                    # Apply preference tier filter
                    if oi.preference_tier:
                        tier_candidates = [p for p in candidates if p.brand_tier == oi.preference_tier]
                        if tier_candidates:
                            candidates = tier_candidates

                    new_chosen = candidates[0]
                    new_next = None
                    for p in candidates:
                        if p.store_name != new_chosen.store_name:
                            new_next = p
                            break

                    new_savings = round(new_next.price - new_chosen.price, 4) if new_next else 0.0

                    new_optimized.append(OptimizedItem(
                        master_product_id=oi.master_product_id,
                        name=oi.name,
                        category=oi.category,
                        is_staple=oi.is_staple,
                        preference_tier=oi.preference_tier,
                        quantity=oi.quantity,
                        assigned_store=oi.assigned_store,
                        chosen_store=new_chosen.store_name,
                        store_product=new_chosen,
                        savings_vs_next=new_savings,
                        next_best_store=new_next.store_name if new_next else None,
                        next_best_product=new_next,
                    ))
                else:
                    new_optimized.append(oi)
            optimized = new_optimized
            changed = True

    return optimized


def format_store_lists(optimized: List[OptimizedItem]) -> Dict[str, List[OptimizedItem]]:
    store_lists: Dict[str, List[OptimizedItem]] = {}
    for oi in optimized:
        store_lists.setdefault(oi.chosen_store, []).append(oi)
    # Sort stores by total value descending
    return dict(
        sorted(store_lists.items(), key=lambda x: sum(oi.store_product.price for oi in x[1]), reverse=True)
    )


def print_split(title: str, store_lists: Dict[str, List[OptimizedItem]], show_savings: bool = True) -> None:
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")

    grand_total = 0.0
    for store_name, items in store_lists.items():
        store_total = sum(oi.store_product.price for oi in items)
        grand_total += store_total

        print(f"\n  {store_name} ({len(items)} items) - Total: ${store_total:.2f}")
        print(f"  {'-'*66}")

        for oi in items:
            sp = oi.store_product
            unit_price_str = f"${sp.unit_price_per_100:.4f}/{sp.unit_type}"
            calc_str = f"({sp.price}/{sp.package_size}{sp.unit_type})*100"
            special_flag = " 🟡" if sp.is_on_special else ""
            print(f"    {sp.product_name:<40}{special_flag}")
            print(f"    {'Price:':>10} ${sp.price:.2f}    {'Unit:':>10} {unit_price_str}    {'Calc:':>8} {calc_str}")
            if show_savings and oi.savings_vs_next > 0:
                print(f"    {'Saved:':>10} ${oi.savings_vs_next:.2f} vs {oi.next_best_store}")
            if oi.assigned_store:
                print(f"    {'Assigned:':>10} {oi.assigned_store}")
            print(f"    {'Link:':>10} {sp.deep_link_url}")
            print()

    print(f"\n  {'GRAND TOTAL':<40} ${grand_total:.2f}")
    print(f"  {'Stores to visit':<40} {len(store_lists)}")
    print(f"{'='*70}")


def run_optimizer(allowed_stores: List[str], inconvenience_threshold: float = 3.00) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        shopping_list = load_shopping_list(conn)
        if not shopping_list:
            print("No active items in shopping list.")
            return

        # Load all store products for each shopping list item
        store_products_map: Dict[int, List[StoreProduct]] = {}
        for item in shopping_list:
            store_products_map[item.master_product_id] = load_store_products(
                conn, item.master_product_id, allowed_stores
            )

        # Filter out items with no available products
        available_items = []
        unavailable_items = []
        for item in shopping_list:
            products = store_products_map[item.master_product_id]
            if not products:
                unavailable_items.append(item)
            else:
                available_items.append(item)

        if unavailable_items:
            print(f"\nWarning: {len(unavailable_items)} item(s) not available at any allowed store:")
            for item in unavailable_items:
                print(f"  - {item.name}")

        # Raw optimization
        raw_optimized = optimize_raw(available_items, store_products_map)
        raw_store_lists = format_store_lists(raw_optimized)

        print(f"\n{'='*70}")
        print(f"  SHOPPING LIST OPTIMIZER")
        print(f"  Allowed stores: {', '.join(allowed_stores)}")
        print(f"  Inconvenience threshold: ${inconvenience_threshold:.2f}")
        print(f"{'='*70}")

        print_split("RAW OPTIMIZATION (cheapest store per item)", raw_store_lists, show_savings=True)

        # Advanced optimization
        advanced_optimized = optimize_advanced(
            raw_optimized, store_products_map, inconvenience_threshold, allowed_stores
        )
        advanced_store_lists = format_store_lists(advanced_optimized)

        print_split("ADVANCED OPTIMIZATION (with Inconvenience Tax)", advanced_store_lists, show_savings=True)

        # Compare raw vs advanced
        print(f"\n{'='*70}")
        print(f"  COMPARISON")
        print(f"{'='*70}")
        raw_stores = len(raw_store_lists)
        adv_stores = len(advanced_store_lists)
        raw_total = sum(sum(oi.store_product.price for oi in items) for items in raw_store_lists.values())
        adv_total = sum(sum(oi.store_product.price for oi in items) for items in advanced_store_lists.values())
        print(f"  Raw:     {raw_stores} stores, ${raw_total:.2f}")
        print(f"  Advanced: {adv_stores} stores, ${adv_total:.2f}")
        if adv_stores < raw_stores:
            diff = adv_total - raw_total
            if diff > 0:
                print(f"  Saved {raw_stores - adv_stores} store trip(s) for extra ${diff:.2f}")
            elif diff < 0:
                print(f"  Saved {raw_stores - adv_stores} store trip(s) and saved ${abs(diff):.2f}")
            else:
                print(f"  Saved {raw_stores - adv_stores} store trip(s) at no extra cost")
        elif adv_stores > raw_stores:
            print(f"  Note: advanced optimization resulted in more stores (check data)")
        else:
            print(f"  No store trips saved (savings at all stores above threshold)")
        print(f"{'='*70}")

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Australian Grocery Price Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--stores",
        nargs="+",
        choices=ALL_STORES,
        default=ALL_STORES,
        help="Which stores to consider (default: all three)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=3.00,
        help="Inconvenience tax threshold in dollars (default: 3.00)",
    )
    args = parser.parse_args()

    if not args.stores:
        args.stores = ALL_STORES

    run_optimizer(allowed_stores=args.stores, inconvenience_threshold=args.threshold)


if __name__ == "__main__":
    main()
