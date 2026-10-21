import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, rank, dense_rank, row_number, lag, lead
from pyspark.sql.functions import round as spark_round
from pyspark.sql.window import Window

# Initialize Spark session with Hive support
# LOCAL DEMO: no .master("yarn"); run_spark.sh starts Spark in local mode.
spark = SparkSession.builder.appName("Hdfs_to_hive").enableHiveSupport().getOrCreate()

# LOCAL DEMO: MinIO (S3 API) replaces HDFS
bucket = os.environ["MINIO_BUCKET"]
staging_location = f"s3a://{bucket}/sales/sales_detail_csv"

def table_is_empty(table_name):
    """
    Function to check if a Hive table is empty.
    :param table_name: str
    :return: bool
    """
    try:
        result = spark.sql(f"SELECT COUNT(*) AS count FROM {table_name}").collect()
        print(f"✅ Table {table_name} has {result[0]['count']} rows")
        return result[0]['count'] == 0
    except Exception as e:
        print(f"❌ Error checking table {table_name}: {e}")
        raise  # Let it fail loudly!


def load_staging_and_final_tables():
    """Task 'transform_load_hive': staging table (from MinIO files) and final table."""
    try:
        # Create Hive database if it doesn't exist
        spark.sql("CREATE DATABASE IF NOT EXISTS staging_db")

        # Use the staging database
        spark.sql("USE staging_db")

        # Drop the staging table if it exists
        spark.sql("DROP TABLE IF EXISTS staging_table")


        # Create Hive staging table
        # LOCAL DEMO: the detail CSV files have no header line (see rds_to_hdfs.py).
        spark.sql(f"""
            CREATE EXTERNAL TABLE IF NOT EXISTS staging_table (
                customer STRING,
                order_date DATE,
                product_name STRING,
                quantity INT,
                price DOUBLE,
                total_price DOUBLE
            )
            ROW FORMAT DELIMITED
            FIELDS TERMINATED BY ','
            STORED AS TEXTFILE
            LOCATION '{staging_location}'
        """)
        print("Hive staging table created successfully")

        # Drop the final table if it exists
        spark.sql("DROP TABLE IF EXISTS final_table")

        # Remove duplicates and create final table
        if table_is_empty("staging_table"):
            # LOCAL DEMO FIX: was only a print, so the task still ended as "success" with no data.
            raise RuntimeError("staging_table is empty. Nothing to load into final_table.")
        else:
            spark.sql("""
                CREATE TABLE IF NOT EXISTS final_table AS
                SELECT DISTINCT *
                FROM staging_table
            """)
            print("Final table created successfully")

    except Exception as e:
        print(f"Error creating staging and final tables: {e}")
        raise  # LOCAL DEMO: do not hide the error, so Airflow shows the task as failed


def build_sales_report_tables():
    """Task 'build_sales_reports': business tables built from final_table."""
    try:
        spark.sql("USE staging_db")

        # Drop the business logic table if it exists
        spark.sql("DROP TABLE IF EXISTS customer_yearly_sales")

        # Example business logic: Calculate total sales by customer and year and store in a final table
        if table_is_empty("final_table"):
            # LOCAL DEMO FIX: was only a print, so the task still ended as "success" with no data.
            raise RuntimeError("final_table is empty. Nothing to build customer_yearly_sales from.")
        else:
            # LOCAL DEMO FIX: total_sales was SUM(quantity). Now: total_quantity = SUM(quantity),
            # total_sales = SUM(total_price), order_count = number of order lines (one per order here).
            spark.sql("""
                CREATE TABLE IF NOT EXISTS customer_yearly_sales AS
                SELECT
                    customer,
                    year(order_date) AS order_year,
                    SUM(quantity) AS total_quantity,
                    ROUND(SUM(total_price), 2) AS total_sales,
                    COUNT(*) AS order_count,
                    ROUND(AVG(price), 2) AS average_price
                FROM
                    final_table
                GROUP BY
                    customer,
                    year(order_date)
            """)
            print("Business logic applied and final table created successfully")

    except Exception as e:
        print(f"Error building sales report tables: {e}")
        raise  # LOCAL DEMO: do not hide the error, so Airflow shows the task as failed


def build_customer_sales_ranking():
    """Task 'build_customer_ranking': the window functions of rds_to_hdfs.py, kept in a Hive table.

    One row per order line. Customers are ranked by their total sales; lag/lead give the
    previous and next order value of the same customer (NULL when there is none).
    """
    try:
        spark.sql("USE staging_db")
        spark.sql("DROP TABLE IF EXISTS customer_sales_ranking")

        if table_is_empty("final_table"):
            raise RuntimeError("final_table is empty. Nothing to build customer_sales_ranking from.")

        customer_window = Window.partitionBy("customer").orderBy("order_date")
        ranking_window = Window.orderBy(col("customer_total_sales").desc())

        ranking_df = spark.table("final_table") \
            .withColumn("customer_total_sales", spark_round(sum("total_price").over(Window.partitionBy("customer")), 2)) \
            .withColumn("sales_rank", rank().over(ranking_window)) \
            .withColumn("sales_dense_rank", dense_rank().over(ranking_window)) \
            .withColumn("order_row_num", row_number().over(customer_window)) \
            .withColumn("prev_order_value", spark_round(lag("total_price", 1).over(customer_window), 2)) \
            .withColumn("next_order_value", spark_round(lead("total_price", 1).over(customer_window), 2)) \
            .select("customer", "order_date", "total_price", "customer_total_sales", "sales_rank",
                    "sales_dense_rank", "order_row_num", "prev_order_value", "next_order_value") \
            .orderBy("sales_rank", "customer", "order_date")

        ranking_df.write.mode("overwrite").saveAsTable("customer_sales_ranking")
        print("customer_sales_ranking created successfully")

    except Exception as e:
        print(f"Error building customer_sales_ranking: {e}")
        raise  # LOCAL DEMO: do not hide the error, so Airflow shows the task as failed


# LOCAL DEMO: the original ran everything in one call. Airflow now runs it as three tasks:
#   hdfs_to_hive.py load      -> staging_table + final_table
#   hdfs_to_hive.py reports   -> customer_yearly_sales
#   hdfs_to_hive.py ranking   -> customer_sales_ranking
#   hdfs_to_hive.py           -> all three, like the original
stage = sys.argv[1] if len(sys.argv) > 1 else "all"
if stage not in ("load", "reports", "ranking", "all"):
    raise SystemExit(f"Unknown stage '{stage}'. Use: load, reports, ranking or all")
if stage in ("load", "all"):
    load_staging_and_final_tables()
if stage in ("reports", "all"):
    build_sales_report_tables()
if stage in ("ranking", "all"):
    build_customer_sales_ranking()
