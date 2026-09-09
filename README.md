# Retail Performance & Customer Analytics

An end-to-end analytics project: a Python/SQL ETL pipeline that integrates transactional retail data with an external exchange-rate API into a PostgreSQL data warehouse, feeding an interactive Power BI dashboard.

![Dashboard screenshot](screenshots/dashboard_full.png)

## Overview

This project simulates a common consulting/analytics scenario: a retailer's raw transactional data needs to be cleaned, integrated with an external data source, modelled into a proper analytical schema, and turned into a dashboard that supports real business decisions not just charts for their own sake.

**Business question:** Where is revenue coming from, how is it trending, and where should the business focus attention?

## Data sources

1. **Online Retail II** (UCI Machine Learning Repository)  ~1.07M real transaction-level records from a UK-based online retailer, Dec 2009–Dec 2011. Includes invoices, products, quantities, prices, customer IDs and countries.
2. **Frankfurter API** (frankfurter.app)  historical GBP/USD exchange rates, fetched live and joined into the model by date.

## Architecture

```
Excel (2 sheets)  ─┐
                    ├─▶  Python (pandas)  ─▶  clean & transform  ─▶  PostgreSQL  ─▶  Power BI
Exchange rate API ─┘
```

**Data model:** a star schema in PostgreSQL 
- `fact_transactions` (invoice line items)
- `dim_customers`, `dim_products`, `dim_dates`, `dim_exchange_rates`

See [`sql/schema.sql`](sql/schema.sql) for the full DDL.

## What the pipeline does

- Loads and concatenates both raw source sheets (~1.07M rows)
- Flags cancelled orders (invoice numbers prefixed `C`) *before* any filtering, preserving them as a queryable attribute rather than discarding them
- Drops rows with no customer ID (unattributable revenue) and exact duplicates  **~270K rows removed**, ~798K clean rows retained
- Builds a full calendar dimension spanning the true data range and left-joins in exchange rates, forward-filling non-trading days
- Loads all tables into PostgreSQL in dependency order to respect foreign keys

Run it yourself: see [`etl_pipeline.py`](etl_pipeline.py) (requires `pandas`, `sqlalchemy`, `psycopg2-binary`, `requests`, `openpyxl`  a local PostgreSQL instance with a `retail_analytics` database created from `sql/schema.sql`).

## Dashboard

Built in Power BI Desktop, connected directly to PostgreSQL. Includes:
- Headline KPIs: net revenue, cancellation rate
- Monthly revenue trend
- Revenue by country and top-selling products (Top 15, with non-product bookkeeping entries like "Manual" and "Postage" explicitly excluded)
- Interactive country and date-range slicers

`.pbix` file: [`dashboard/retail_dashboard.pbix`](dashboard/retail_dashboard.pbix)

## Key findings

Net revenue across the analysed period totalled **£17.37M**, with a **2.30%** cancellation rate. Revenue shows a clear seasonal pattern  relatively flat January–August, climbing sharply from September and peaking in November, consistent with pre-Christmas retail demand. (The apparent December dip is most likely a data-coverage artefact: the dataset's final year is truncated to the first nine days of December, not a genuine seasonal decline.)

Revenue is heavily concentrated in the **United Kingdom**, with Ireland, the Netherlands and Germany as distant secondary markets. This concentration suggests an opportunity to test targeted expansion in these adjacent markets ahead of the Q4 peak, while also representing a market-concentration risk worth monitoring.

## Notes on data quality decisions

- Cancelled orders were kept (not dropped) so cancellation rate could be measured as its own metric, rather than silently excluded
- Rows with missing customer IDs were excluded, since revenue can't be meaningfully attributed to an unknown customer
- Non-product line items ("Manual" price adjustments, "Postage" charges) were identified and excluded from the top-products analysis, since including them would misrepresent actual product performance

## Tools

Python (pandas, SQLAlchemy) · PostgreSQL · Power BI · Frankfurter API

## Author

Ash  built as an independent project, 2026.
