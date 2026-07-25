---
name: Weekly specials override strategy
description: How weekly-special prices are applied without permanently rewriting the baseline database.
---

# Weekly specials override strategy

Weekly-special prices are loaded from an uploaded CSV or a Google Sheet tab and stored in `st.session_state["weekly_specials"]`.

Before the optimizer runs, the helper `_match_weekly_specials_to_products()` maps each special to a `(master_product_id, store_name)` pair, and `_apply_weekly_special_overrides()` clones the store products so the override price (and recomputed `unit_price_per_100`) is used only for that session run.

**Why:** Users want to experiment with catalogue prices each week without the risk of corrupting the baseline SQLite database. In-memory overrides keep the seed data stable and make the feature safe to deploy on Streamlit Cloud where filesystem writes are not guaranteed.

**How to apply:** Any new dynamic-price feature should follow this pattern — read from external sources, store in session state, and transform the optimizer input data rather than writing to the database. Clear the cache when the override list changes so `st.cache_data` does not serve stale results.
