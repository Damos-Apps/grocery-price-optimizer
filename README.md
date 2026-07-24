# Australian Grocery Price Optimizer

A Python + Streamlit app that compares grocery prices across Coles, Woolworths, and Aldi — normalising everything to a per-100-unit price so you can always find the cheapest real value.

## Features

- **Store toggles** — choose which stores to include in your optimisation.
- **Inconvenience Tax slider** — control the threshold for consolidating small trips into one.
- **Split shopping lists** — see raw (cheapest per item) and advanced (consolidated) shopping lists.
- **Weekly Specials Alert** — highlights items on special and shows exactly how much you save.
- **Smart Savings Recommendations** — suggests cheaper brand-tier alternatives and lets you swap instantly.
- **Quick Price Check** — search and compare any product across all stores.

## Deploy on Streamlit Community Cloud

1. Fork or clone this repository to your GitHub account.
2. Visit [Streamlit Community Cloud](https://streamlit.io/cloud) and sign in with GitHub.
3. Click **New app** and select this repository.
4. Set the **Main file path** to `grocery-optimizer/app.py`.
5. Click **Deploy**.

Streamlit Community Cloud will read the `requirements.txt` file and install the required dependencies automatically.

## Run locally

```bash
# Initialize the database with seed data
python3 grocery-optimizer/init_db.py

# Run the Streamlit dashboard
streamlit run grocery-optimizer/app.py --server.port 5000
```

## Project structure

- `grocery-optimizer/app.py` — Streamlit dashboard
- `grocery-optimizer/init_db.py` — database setup
- `grocery-optimizer/schema.py` — SQLite schema
- `grocery-optimizer/seed.py` — seed data
- `grocery-optimizer/optimizer.py` — split-list optimisation logic
- `requirements.txt` — Python dependencies

## License

MIT
