# Enterprise Sales Data Pipeline on AWS

## Demo

Watch the pipeline run end to end:

## Overview

An online shop stores its sales in a PostgreSQL database: customers, orders, order items, products, categories and suppliers in six separate tables. To answer business questions such as "how much did each customer buy per year?" or "who are our top customers?", the data has to be joined, cleaned and summarised.

This project is a batch data pipeline on AWS that does this. It was built and run on AWS in 2025. The pipeline:

1. reads the six tables from PostgreSQL on Amazon RDS with PySpark,
2. joins them, filters and enriches the order lines (total price, upper-case customer name, date parts, window functions),
3. writes the result to HDFS as CSV files,
4. loads the files into Hive: a staging table, a de-duplicated final table, a yearly sales summary per customer, and a customer sales ranking built with window functions.

## Architecture

```
 +----------------------+     +--------------------------------+     +---------------------+
 |  PostgreSQL          |     |  PySpark on YARN               |     |  HDFS               |
 |  on Amazon RDS       |JDBC |  rds_to_hdfs.py                |     |  CSV files          |
 |  6 tables            |---->|  joins, filter, UDF,           |---->|  sales detail       |
 |  (Customers, Orders, |     |  window functions, aggregation |     |  customer totals    |
 |  Order_Items,        |     +--------------------------------+     +----------+----------+
 |  Products,           |                                                        |
 |  Categories,         |                                                        v
 |  Suppliers)          |                              +-----------------------------------------+
 +----------------------+                              |  Apache Hive (Spark SQL)                |
                                                       |  hdfs_to_hive.py, database staging_db   |
                                                       |                                         |
                                                       |  staging_table (external, on HDFS)      |
                                                       |        |  SELECT DISTINCT               |
                                                       |        v                                |
                                                       |  final_table                            |
                                                       |        |-> customer_yearly_sales        |
                                                       |        '-> customer_sales_ranking       |
                                                       +-----------------------------------------+
```

## Tech Stack

| Area | Tools |
|---|---|
| Processing | PySpark (DataFrame API, window functions, UDF), Spark SQL |
| Data warehouse | Apache Hive (external and managed tables) |
| Storage | HDFS (CSV files) |
| Cloud | AWS: PostgreSQL on Amazon RDS, Spark on YARN |
| Source database | PostgreSQL (JDBC) |
| Language | Python, SQL |

## Pipeline Steps and Transformations

**Step 1 - `rds_to_hdfs.py` (with the `DataPipeline` class in `main1.py`)**
- Reads Customers, Orders, Order_Items, Products, Categories and Suppliers over JDBC.
- Joins all six tables (inner joins on customer, order, product, category and supplier IDs).
- Keeps order lines with `quantity >= 2` and adds `total_price = quantity * price`.
- Fills null prices, sorts by order date, and adds an upper-case customer name with a UDF (NULL-safe).
- Adds `order_year`, `order_month` and `order_day`.
- Applies window functions per customer: `row_number`, `rank`, `dense_rank`, cumulative `sum`, `lag` and `lead`.
- Aggregates per customer (total quantity, average price), repartitions to 5 partitions and counts null values per column.
- Writes two CSV outputs to HDFS: the order-line detail (6 columns, no header line) for the Hive staging table, and the customer totals.

**Step 2 - `hdfs_to_hive.py`**
- Creates the Hive database `staging_db` and an external `staging_table` on the HDFS detail files (`customer, order_date, product_name, quantity, price, total_price`).
- Builds `final_table` with `SELECT DISTINCT`.
- Builds `customer_yearly_sales`: per customer and year, `SUM(quantity)`, `SUM(total_price)`, `COUNT(*)` and `AVG(price)`.
- Builds `customer_sales_ranking` with window functions: `RANK` and `DENSE_RANK` over the customer's total sales, `ROW_NUMBER` per customer, and `LAG` / `LEAD` for the previous and next order value.
- Fails the job when a table is empty or a step raises an error, instead of only printing a message.

## Output Tables

Row counts for the sample data in `sql_whole_ddl.sql` (100 rows in each of the six source tables, orders from 2023):

| Table | Rows | Content |
|---|---:|---|
| `staging_table` | 80 | Order lines with `quantity >= 2` |
| `final_table` | 80 | The same rows without duplicates |
| `customer_yearly_sales` | 80 | One row per customer and year |
| `customer_sales_ranking` | 80 | One row per order line, with rank, previous and next order value |

Sample of `customer_yearly_sales`:

| customer | order_year | total_quantity | total_sales | order_count | average_price |
|---|---:|---:|---:|---:|---:|
| Amy Collins | 2023 | 5 | 290.00 | 1 | 58.00 |
| Angela Sanchez | 2023 | 2 | 58.00 | 1 | 29.00 |
| Anna Peterson | 2023 | 3 | 126.00 | 1 | 42.00 |

Top of `customer_sales_ranking`:

| customer | order_date | total_price | customer_total_sales | sales_rank |
|---|---|---:|---:|---:|
| Dorothy Hayes | 2023-04-08 | 340.00 | 340.00 | 1 |
| Michelle Bryant | 2023-04-03 | 335.00 | 335.00 | 2 |
| Donna Washington | 2023-03-29 | 330.00 | 330.00 | 3 |

Each customer has one order in the sample data, so `prev_order_value` and `next_order_value` are NULL there.

## Project Structure

```
Enterprise_Data_Analysis/
├── main1.py            # DataPipeline class: starts Spark, reads a table over JDBC
├── rds_to_hdfs.py      # Reads, joins and transforms; writes CSV to HDFS
├── hdfs_to_hive.py     # Creates the Hive staging, final, yearly sales and ranking tables
├── sql_whole_ddl.sql   # Creates and fills the 6 source tables (100 rows each)
├── .env.example        # Names of the environment variables (no real values)
├── .gitignore
├── local_demo/         # Local version (see the last section)
└── README.md
```

### Configuration

The database host, user and password are not stored in the code. `rds_to_hdfs.py` reads them from the environment variables `POSTGRES_HOST`, `POSTGRES_PORT`, `SOURCE_DB`, `POSTGRES_USER` and `POSTGRES_PASSWORD`. See `.env.example`.

### Run on AWS

```bash
# 1. Run sql_whole_ddl.sql in your PostgreSQL database
# 2. Set the variables from .env.example, then submit the two jobs
spark-submit --jars /path/to/postgresql-jdbc.jar rds_to_hdfs.py
spark-submit hdfs_to_hive.py
```

## Local demo (Docker)

The pipeline was originally built and run on AWS. After the AWS free tier ended, I created a local version with Docker Compose to keep it runnable for demos: MinIO stands in for HDFS, PostgreSQL stands in for RDS, and Spark runs inside Airflow in local mode. See [`local_demo/README.md`](local_demo/README.md) for steps.
The local demo adds synthetic sample orders for testing.
