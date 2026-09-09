"""
ETL pipeline: Online Retail II (Excel) + GBP/USD exchange rates -> PostgreSQL (retail_analytics)

Prereqs:
    pip install pandas psycopg2-binary sqlalchemy requests openpyxl

Update the CONFIG section below before running.
"""

import pandas as pd
import requests
from sqlalchemy import create_engine
from datetime import timedelta
import time

# ---------------- CONFIG ----------------
EXCEL_PATH = r"C:\Users\aarsh\retail-analytics-pipeline\online+retail+ii\online_retail_II.xlsx"

PG_USER = "postgres"
PG_PASSWORD = "Aasn$2026"
PG_HOST = "localhost"
PG_PORT = "5432"
PG_DB = "retail_analytics"
# -----------------------------------------

engine = create_engine(f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}")


def load_raw():
    print("Loading Excel sheets...")
    sheet_names = ["Year 2009-2010", "Year 2010-2011"]
    frames = []
    for sheet in sheet_names:
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet)
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    print(f"  Loaded {len(raw):,} raw rows")
    return raw


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    print("Cleaning...")
    df = raw.copy()

    # Standardise column names (UCI file uses 'Invoice', 'StockCode', 'Description',
    # 'Quantity', 'InvoiceDate', 'Price', 'Customer ID', 'Country')
    df = df.rename(columns={
        "Invoice": "invoice_no",
        "StockCode": "stock_code",
        "Description": "description",
        "Quantity": "quantity",
        "InvoiceDate": "invoice_date",
        "Price": "unit_price",
        "Customer ID": "customer_id",
        "Country": "country",
    })

    # Flag cancellations (invoice numbers starting with 'C') BEFORE dropping anything
    df["invoice_no"] = df["invoice_no"].astype(str).str.strip()
    df["is_cancelled"] = df["invoice_no"].str.startswith("C")

    # Drop rows with no customer_id (can't attribute the transaction to anyone)
    before = len(df)
    df = df.dropna(subset=["customer_id"])
    print(f"  Dropped {before - len(df):,} rows with missing customer_id")

    # Drop rows with no stock_code or unit_price <= 0 with no clear reason (data-quality noise)
    df = df.dropna(subset=["stock_code"])
    df = df[df["unit_price"].notna()]

    # Types
    df["customer_id"] = df["customer_id"].astype(int).astype(str)
    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["description"] = df["description"].astype(str).str.strip()
    df["country"] = df["country"].astype(str).str.strip()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["quantity"] = df["quantity"].astype(int)
    df["unit_price"] = df["unit_price"].astype(float)

    # Dedupe exact duplicate rows
    before = len(df)
    df = df.drop_duplicates()
    print(f"  Dropped {before - len(df):,} exact duplicate rows")

    print(f"  {len(df):,} rows remain after cleaning")
    return df


def build_dims(df: pd.DataFrame):
    print("Building dimension tables...")

    dim_customers = (
        df[["customer_id", "country"]]
        .drop_duplicates(subset="customer_id")
        .reset_index(drop=True)
    )

    dim_products = (
        df[["stock_code", "description"]]
        .drop_duplicates(subset="stock_code")
        .reset_index(drop=True)
    )

    min_date = df["invoice_date"].min().normalize()
    max_date = df["invoice_date"].max().normalize()
    all_dates = pd.date_range(min_date, max_date, freq="D")
    dim_dates = pd.DataFrame({"date": all_dates})
    dim_dates["year"] = dim_dates["date"].dt.year
    dim_dates["month"] = dim_dates["date"].dt.month
    dim_dates["day"] = dim_dates["date"].dt.day
    dim_dates["weekday"] = dim_dates["date"].dt.day_name().str[:10]

    print(f"  dim_customers: {len(dim_customers):,}")
    print(f"  dim_products:  {len(dim_products):,}")
    print(f"  dim_dates:     {len(dim_dates):,} ({min_date.date()} to {max_date.date()})")

    return dim_customers, dim_products, dim_dates


def fetch_exchange_rates(dim_dates: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch historical GBP->USD rates from the Frankfurter API (free, no key required)
    in monthly batches to keep request count low.
    """
    print("Fetching exchange rates from Frankfurter API...")
    start = dim_dates["date"].min().date()
    end = dim_dates["date"].max().date()

    url = f"https://api.frankfurter.app/{start}..{end}"
    resp = requests.get(url, params={"from": "GBP", "to": "USD"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()["rates"]  # {"2009-12-01": {"USD": 1.63}, ...}

    rates = pd.DataFrame(
        [{"date": pd.to_datetime(d), "gbp_usd_rate": v["USD"]} for d, v in data.items()]
    )

    # The API only returns rates for business days -> forward-fill onto every calendar day
    full = dim_dates[["date"]].merge(rates, on="date", how="left")
    full["gbp_usd_rate"] = full["gbp_usd_rate"].ffill().bfill()

    print(f"  Retrieved rates for {len(rates):,} business days, filled to {len(full):,} calendar days")
    return full


def build_fact(df: pd.DataFrame) -> pd.DataFrame:
    fact = df[[
        "invoice_no", "stock_code", "customer_id",
        "invoice_date", "quantity", "unit_price", "is_cancelled"
    ]].copy()
    fact["invoice_date"] = fact["invoice_date"].dt.normalize()
    return fact


def load_to_postgres(dim_customers, dim_products, dim_dates, dim_exchange_rates, fact):
    print("Loading to PostgreSQL...")

    # Order matters: dims before the fact table (foreign keys)
    dim_dates.to_sql("dim_dates", engine, if_exists="append", index=False)
    print("  dim_dates loaded")

    dim_customers.to_sql("dim_customers", engine, if_exists="append", index=False)
    print("  dim_customers loaded")

    dim_products.to_sql("dim_products", engine, if_exists="append", index=False)
    print("  dim_products loaded")

    dim_exchange_rates.to_sql("dim_exchange_rates", engine, if_exists="append", index=False)
    print("  dim_exchange_rates loaded")

    fact.to_sql("fact_transactions", engine, if_exists="append", index=False)
    print("  fact_transactions loaded")


def main():
    t0 = time.time()
    raw = load_raw()
    df = clean(raw)
    dim_customers, dim_products, dim_dates = build_dims(df)
    dim_exchange_rates = fetch_exchange_rates(dim_dates)
    fact = build_fact(df)
    load_to_postgres(dim_customers, dim_products, dim_dates, dim_exchange_rates, fact)
    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
