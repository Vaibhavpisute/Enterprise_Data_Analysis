-- ============================================================================
-- SYNTHETIC SAMPLE DATA - NOT REAL ORDERS.
-- Loaded automatically after sql_whole_ddl.sql (file name order: 01_, 02_).
-- The original 100 orders (order_id 1-100) are not changed.
--
-- Adds 400 fake orders (order_id 101-500), one order line each, for the existing
-- customers (1-100) and products (1-100), dated 2023-01-01 to 2024-12-31.
--   - Orders 101-400: customers 1-100 in turns (3 more orders each).
--   - Orders 401-500: random customers (some get a few extra).
--   - Result: every customer has about 4-8 orders, in both 2023 and 2024.
--   - Quantity 1-5, price 10.00-64.99.
-- A fixed seed (setseed) makes the data the same on every first start.
-- All foreign keys stay valid: customer_id and product_id are from the existing 1-100.
-- ============================================================================

SELECT setseed(0.42);

INSERT INTO Orders (order_id, customer_id, order_date)
SELECT
    n,
    CASE WHEN n <= 400 THEN ((n - 1) % 100) + 1
         ELSE 1 + floor(random() * 100)::int END,
    DATE '2023-01-01' + floor(random() * 731)::int      -- 2023-01-01 .. 2024-12-31
FROM generate_series(101, 500) AS n
ORDER BY n;

INSERT INTO Order_Items (order_item_id, order_id, product_id, quantity, price)
SELECT
    n,
    n,
    1 + floor(random() * 100)::int,                     -- product 1..100
    1 + floor(random() * 5)::int,                       -- quantity 1..5
    10 + floor(random() * 5500)::numeric / 100          -- price 10.00 .. 64.99
FROM generate_series(101, 500) AS n
ORDER BY n;
