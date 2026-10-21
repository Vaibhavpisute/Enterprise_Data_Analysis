# Local demo: Enterprise Sales Data Pipeline

This folder runs the whole sales pipeline on your own PC with Docker. It needs no AWS account.

## What replaces what

| On AWS | In this demo |
|---|---|
| PostgreSQL on RDS | PostgreSQL container, database `sales_db` |
| HDFS | MinIO container (S3-compatible storage), bucket `sales-data` |
| Spark on YARN | PySpark in local mode, inside the Airflow container |
| Hive | Spark's built-in local Hive metastore (Derby), database `staging_db` |
| (manual runs) | Airflow, DAG `sales_pipeline_local` |

## Architecture

```
  +---------------------+      +------------------------------+
  | PostgreSQL          |      | Airflow (standalone)         |
  | sales_db            |      |  + Java + PySpark (local)    |
  | 6 tables, 100 rows  |      |                              |
  | each                |      |  DAG: sales_pipeline_local   |
  +----------+----------+      +---------------+--------------+
             |                                 |
   1. extract_postgres_to_minio                |  runs the 3 Spark jobs
             |  (joins, window functions, UDF) |
             v                                 |
  +---------------------+                      |
  | MinIO               |                      |
  | bucket: sales-data  |                      |
  | sales/..._csv files |                      |
  +----------+----------+                      |
             |                                 |
   2. transform_load_hive                      |
             v                                 |
  +-----------------------------------------+  |
  | Hive (local metastore), db staging_db   |<-+
  |  staging_table -> final_table           |
  |  3. build_sales_reports ->              |
  |       customer_yearly_sales             |
  |  4. build_customer_ranking ->           |
  |       customer_sales_ranking            |
  +-----------------------------------------+
```

## Sample data

- The original `sql_whole_ddl.sql` has 100 customers, 100 orders (one per customer) and 100 order items. It is copied here without changes (except the `commit;` lines).
- `sql/02_extra_sample_orders.sql` adds **400 synthetic (fake) orders**, with one order item each. They are sample data made only for this demo, not real sales. Dates are in 2023 and 2024, quantities are 1 to 5, and prices are 10.00 to 64.99. With them, every customer has 4 to 8 orders in both years. A fixed random seed makes the data the same every time.
- PostgreSQL loads both files by itself, in order, **only on the first start** (when its data volume is empty). To load the data again from zero, remove the PostgreSQL volume (see Stop below).

## What you need

- Windows with Docker Desktop (WSL2) running
- About 3 GB of free RAM for the containers
- The Docker image `health-demo-airflow:local` (also used by the Health_Data_Pipeline demo). If it is missing, Docker builds it for you.

## Start

1. Open PowerShell in this folder (`local_demo`).
2. Create your settings file: `Copy-Item .env.example .env`, then open `.env` and change the passwords.
3. Start everything: `docker compose up -d`
4. Wait about one minute. PostgreSQL loads `sql_whole_ddl.sql` by itself on the first start, and the bucket is created by itself.
5. Open Airflow at http://localhost:8081 and log in with `AIRFLOW_ADMIN_USER` and `AIRFLOW_ADMIN_PASSWORD` from `.env`.

## Run

Trigger the DAG with the play button in Airflow, or from PowerShell:

```powershell
docker compose exec airflow airflow dags trigger sales_pipeline_local
```

A run takes about 90 seconds. The four tasks run one after the other:

1. `extract_postgres_to_minio`: reads the 6 tables, joins them, and writes CSV files to MinIO
2. `transform_load_hive`: creates `staging_table` on those files, then `final_table` (no duplicate rows)
3. `build_sales_reports`: creates `customer_yearly_sales` (one row per customer and year: total quantity, total sales, order count, average price)
4. `build_customer_ranking`: creates `customer_sales_ranking` (customers ranked by total sales, with the previous and next order value of each customer)

If a task fails, Airflow tries it one more time. The Spark jobs print the error and then stop with a failure, so a broken step never looks like a success.

## Check the results

```powershell
# Row counts only
docker compose exec airflow bash /opt/airflow/scripts/run_spark.sh /opt/airflow/scripts/check_results.py --counts

# 5 sample rows of one table
docker compose exec airflow bash /opt/airflow/scripts/run_spark.sh /opt/airflow/scripts/check_results.py --table customer_yearly_sales
```

Expected counts: `staging_table` 414, `final_table` 414, `customer_sales_ranking` 414, and fewer rows in `customer_yearly_sales` (one row per customer and year). 414 is the number of order items with quantity of 2 or more.

With the original data only (one order per customer), `customer_yearly_sales` had the same number of rows as `final_table`, and `prev_order_value` and `next_order_value` were always NULL. The synthetic orders fix this. A customer's first order still has a NULL `prev_order_value`, and the last one a NULL `next_order_value`.

You can also look at the CSV files in the MinIO console: http://localhost:9011 (login from `.env`).

## Run again from zero

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset_demo.ps1
```

This clears the MinIO files, the Hive tables and the Airflow run history. It keeps the data in `sales_db`. The script waits until Airflow has loaded the DAG again (up to a few minutes), so you can trigger it as soon as the script ends.

## Stop

- Stop and keep all data: `docker compose stop` (start again with `docker compose start`)
- Remove the containers, keep the data: `docker compose down`
- Remove everything, including all data: `docker compose down -v`
- Load the sample data again from zero (only PostgreSQL): `docker compose rm -sf postgres`, then `docker volume rm sales-demo_pgdata`, then `docker compose up -d postgres`

## Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | The services: postgres, minio, minio-init, airflow |
| `.env.example` | Settings with dummy values. Copy it to `.env`. |
| `sql/sql_whole_ddl.sql` | Creates and fills the 6 source tables (loaded on the first start) |
| `sql/02_extra_sample_orders.sql` | 400 synthetic sample orders and order items (loaded after the file above) |
| `spark_jobs/main1.py` | `DataPipeline` class: reads a table over JDBC |
| `spark_jobs/rds_to_hdfs.py` | Reads, joins and transforms; writes CSV files to MinIO |
| `spark_jobs/hdfs_to_hive.py` | Builds the Hive tables (`load`, `reports` and `ranking` steps) |
| `dags/sales_pipeline_local.py` | The Airflow DAG |
| `scripts/run_spark.sh` | Starts a Spark job in local mode with the storage settings |
| `scripts/check_results.py` | Shows row counts and sample rows (`--counts`, `--table`, `--columns`) |
| `scripts/check_results.sh` | Short way to run `check_results.py` with the Spark settings |
| `scripts/reset_demo.ps1` | Clears the outputs, keeps the source data |
| `docker/airflow/` | Dockerfile and start script (only used if the image is missing) |

## What we changed from the original scripts

The join, window function, aggregation and UDF logic is the same. Only connection and storage settings changed, plus these bug fixes:
(Fixes 1 to 6, 11 and 12 are also applied to the AWS scripts in the repository root, which keep HDFS and YARN.)

1. **Staging table did not match the files.** The original wrote only customer totals (`customer, total_quantity, avg_price`), but the Hive staging table expects `customer, order_date, product_name, quantity, price, total_price`. Now the 6-column detail data is also written, and the staging table reads it. The customer totals are still written, to a second folder.
2. **Header line loaded as data.** The CSV header would become a row of NULLs (81 rows instead of 80). The detail files are now written without a header.
3. **Errors were hidden.** All `except` blocks only printed the error. Now they print it and raise it again, so the Airflow task fails.
4. **Empty tables did not fail.** If `staging_table` or `final_table` was empty, the original only printed a message and the run still looked successful. Now it raises an error.
5. **UDF crashed on a NULL name.** `name.upper()` now returns NULL for a NULL name.
6. **Hard-coded RDS host, user and password** are replaced by values from `.env`.
7. **`.master("yarn")`** is removed. Spark runs in local mode (set in `run_spark.sh`).
8. **Misleading messages removed.** The original printed "written successfully" even after a failed write, plus several repeated `show()` calls at the end.
9. **`hdfs_to_hive.py` runs in three steps** (`load`, `reports`, `ranking`) so Airflow can show them as three tasks. With no argument it runs all of them, like the original.
10. **`commit;` lines removed from the SQL.** PostgreSQL printed a warning for each one (no transaction was open). The tables and data are unchanged.
11. **`customer_yearly_sales` had a wrong column.** `total_sales` was `SUM(quantity)`, and there was no order count. Now it has `total_quantity` (`SUM(quantity)`), `total_sales` (`SUM(total_price)`), `order_count` and `average_price`. The `order_count` counts order lines; the staging data has no order id, and the sample data has one line per order.
12. **Window functions reach an output now.** In `rds_to_hdfs.py` they are still calculated and dropped by the final `groupBy` (the original logic). The new table `customer_sales_ranking` is built from `final_table` with `rank`, `dense_rank`, `row_number`, `lag` and `lead`.

## Problems and fixes

- **A port is already in use:** change the `*_HOST_PORT` values in `.env`.
- **See task logs:** in Airflow, click the task, then Logs. Or run `docker compose logs airflow --tail 100`.
