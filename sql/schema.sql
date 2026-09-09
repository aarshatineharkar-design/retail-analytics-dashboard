CREATE TABLE dim_customers (
    customer_id     VARCHAR(20) PRIMARY KEY,
    country         VARCHAR(100)
);

CREATE TABLE dim_products (
    stock_code      VARCHAR(20) PRIMARY KEY,
    description     TEXT
);

CREATE TABLE dim_dates (
    date            DATE PRIMARY KEY,
    year            INT,
    month           INT,
    day             INT,
    weekday         VARCHAR(10)
);

CREATE TABLE dim_exchange_rates (
    date            DATE PRIMARY KEY REFERENCES dim_dates(date),
    gbp_usd_rate    NUMERIC(10,4)
);

CREATE TABLE fact_transactions (
    transaction_id  SERIAL PRIMARY KEY,
    invoice_no      VARCHAR(20),
    stock_code      VARCHAR(20) REFERENCES dim_products(stock_code),
    customer_id     VARCHAR(20) REFERENCES dim_customers(customer_id),
    invoice_date    DATE REFERENCES dim_dates(date),
    quantity        INT,
    unit_price      NUMERIC(10,2),
    is_cancelled    BOOLEAN DEFAULT FALSE
);