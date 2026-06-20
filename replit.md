# Australian Grocery Price Optimizer

A Python + SQLite tool that compares grocery prices across Coles, Woolworths, and Aldi — normalising everything to a per-100-unit price so you can always find the cheapest real value.

## Run & Operate

- `python3 grocery-optimizer/init_db.py` — wipe and re-initialise the database with seed data
- `python3 grocery-optimizer/optimizer.py` — run the split-list optimizer in the terminal
- `streamlit run grocery-optimizer/app.py --server.port 5000` — launch the interactive web UI
- `pnpm run typecheck` — full typecheck across all Node packages
- `pnpm run build` — typecheck + build all Node packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9 (existing API server scaffold)
- **Grocery optimiser: Python 3.11, SQLite 3 (stdlib only — no extra pip deps needed)**
- API: Express 5 (scaffold, not yet used by the optimiser)

## Where things live

- `grocery-optimizer/grocery.db` — SQLite database (auto-created by init script)
- `grocery-optimizer/init_db.py` — entry point: drops + recreates DB, runs schema + seed
- `grocery-optimizer/schema.py` — `CREATE TABLE` statements for all three tables
- `grocery-optimizer/seed.py` — mock data insertion; `calc_unit_price_per_100()` auto-calculates the unit price before every insert
- `grocery-optimizer/optimizer.py` — split-list optimizer with raw and advanced (Inconvenience Tax) modes

## Architecture decisions

- `unit_price_per_100` is always computed in Python before insert (`price / package_size * 100`) — never stored raw and recalculated in queries, so comparisons are instant and consistent.
- Package sizes are stored as plain numerics (e.g. `250`, `2000`) with a separate `unit_type` column (`g`, `ml`, etc.) so the normalisation formula stays unit-agnostic.
- `is_on_special` and `is_staple` are stored as `INTEGER` (0/1) — SQLite has no native BOOLEAN, and this keeps queries straightforward.
- `shopping_list.assigned_store` and `preference_tier` are nullable — `NULL` means "let the optimizer decide."
- The optimizer re-evaluates each item after a store consolidation, respecting `preference_tier` and `assigned_store` constraints.

## Product

- Compare the per-100-unit price of any grocery item across Coles, Woolworths, and Aldi.
- Track specials (`is_on_special`) and flag staple items (`is_staple`).
- Manage a weekly shopping list with per-item store assignments and brand-tier preferences.
- Run the optimizer to split your shopping list into store-specific lists.
- Toggle the Inconvenience Tax to consolidate tiny savings into one trip.
- Filter stores with `--stores` — simulate only shopping at Coles and Aldi, for example.

## User preferences

_Populate as you build — explicit user instructions worth remembering across sessions._

## Gotchas

- Always run `init_db.py` from the repo root or the `grocery-optimizer/` folder — it uses `os.path.dirname(__file__)` to locate `grocery.db` relative to the script.
- SQLite foreign keys are **off by default**; `init_db.py` enables them with `PRAGMA foreign_keys = ON` at connection time. Any new connection that skips this pragma will silently ignore FK violations.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
