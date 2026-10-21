import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, sum, avg, year, month, dayofmonth
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number, rank, dense_rank, lag, lead, udf
from pyspark.sql.types import StringType
from main1 import DataPipeline

# Initialize Spark session with Hive support
# LOCAL DEMO: no .master("yarn"); run_spark.sh starts Spark in local mode.
spark = SparkSession.builder.appName("Rds_to_hdfs").enableHiveSupport().getOrCreate()

# JDBC connection properties
# LOCAL DEMO: the settings come from environment variables (.env). Nothing is hard-coded.
host = f"jdbc:postgresql://{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['SOURCE_DB']}"
user = os.environ["POSTGRES_USER"]
pwd = os.environ["POSTGRES_PASSWORD"]
driver = "org.postgresql.Driver"

# LOCAL DEMO: MinIO (S3 API) replaces HDFS
bucket = os.environ["MINIO_BUCKET"]
detail_path = f"s3a://{bucket}/sales/sales_detail_csv"        # input of the Hive staging table
totals_path = f"s3a://{bucket}/sales/customer_totals_csv"     # the customer totals (original output)

try:
    # Instantiate DataPipeline class
    pipeline = DataPipeline(host, user, pwd, driver)

    # Read data from SQL tables
    customers_df = pipeline.fetch_data_from_sql("Customers")
    orders_df = pipeline.fetch_data_from_sql("Orders")
    order_items_df = pipeline.fetch_data_from_sql("order_items")
    products_df = pipeline.fetch_data_from_sql("Products")
    categories_df = pipeline.fetch_data_from_sql("Categories")
    suppliers_df = pipeline.fetch_data_from_sql("Suppliers")

    # Show initial DataFrames
    print("Customers DataFrame:")
    customers_df.show()

    print("Orders DataFrame:")
    orders_df.show()

    print("Order Items DataFrame:")
    order_items_df.show()

    print("Products DataFrame:")
    products_df.show()

    print("Categories DataFrame:")
    categories_df.show()

    print("Suppliers DataFrame:")
    suppliers_df.show()

    # Perform joins
    full_df = orders_df.join(customers_df, orders_df.customer_id == customers_df.customer_id, "inner") \
                       .join(order_items_df, orders_df.order_id == order_items_df.order_id, "inner") \
                       .join(products_df, order_items_df.product_id == products_df.product_id, "inner") \
                       .join(categories_df, products_df.category_id == categories_df.category_id, "inner") \
                       .join(suppliers_df, products_df.supplier_id == suppliers_df.supplier_id, "inner")

    print("Joined DataFrame:")
    full_df.show()

    #keep this
    # Select specific columns and rename as necessary
    result_df = full_df.select("customer_name", "order_date", "product_name", "quantity", "price") \
                       .withColumnRenamed("customer_name", "customer") \
                       .filter(col("quantity") >=2) \
                       .withColumn("total_price", col("quantity") * col("price"))

    print("Filtered and selected DataFrame:")
    result_df.show()

    # LOCAL DEMO FIX: these 6 columns are what the Hive staging table (hdfs_to_hive.py) expects.
    # The original script only wrote the customer totals, so the staging table did not match the files.
    detail_df = result_df

    # Sort and group the DataFrame
    result_df = result_df.orderBy(col("order_date").desc())

    # Fill null values in `price` and `total_price`
    result_df = result_df.fillna({'price': 0, 'total_price': 0})

    # Define UDF and apply it
    # LOCAL DEMO FIX: a NULL customer name made name.upper() crash the Spark task.
    upper_case_udf = udf(lambda name: name.upper() if name is not None else None, StringType())
    result_df = result_df.withColumn("upper_customer_name", upper_case_udf(col("customer")))

    # Extract date components
    result_df = result_df.withColumn("order_year", year("order_date")) \
                         .withColumn("order_month", month("order_date")) \
                         .withColumn("order_day", dayofmonth("order_date"))

    # Window specification for various window functions
    window_spec = Window.partitionBy("customer").orderBy("order_date")

    # Apply window functions
    result_df = result_df.withColumn("row_num", row_number().over(window_spec)) \
                         .withColumn("rank", rank().over(window_spec)) \
                         .withColumn("dense_rank", dense_rank().over(window_spec)) \
                         .withColumn("cumulative_sum", sum("quantity").over(window_spec)) \
                         .withColumn("lag_quantity", lag("quantity", 1).over(window_spec)) \
                         .withColumn("lead_quantity", lead("quantity", 1).over(window_spec))

    # Calculate percentage
    result_df = result_df.withColumn("percentage", (col("quantity") / sum("quantity").over(window_spec)) * 100)

    # Aggregate multiple columns
    result_df = result_df.groupBy("customer").agg(
        sum("quantity").alias("total_quantity"),
        avg("price").alias("avg_price")
    )

    print("Final DataFrame Created Successfully")

    # Repartition the DataFrame
    result_df = result_df.repartition(5)

    # Show final result
    result_df.show()

    # Count null values in each column
    null_counts = result_df.select([sum(col(c).isNull().cast("int")).alias(c) for c in result_df.columns])
    # Show the result
    null_counts.show()

    # Write DataFrames to MinIO (was: HDFS)
    # LOCAL DEMO FIX: no header line in the detail files. The Hive staging table has no header handling
    # (Spark ignores skip.header.line.count), so the header was loaded as a row of NULLs (81 rows, not 80).
    detail_df.write.option("header", "false").option("delimiter", ",").mode("overwrite").csv(detail_path)
    print(f"Sales detail written to {detail_path}")
    result_df.write.option("header", "true").option("delimiter", ",").mode("overwrite").csv(totals_path)
    print(f"Customer totals written to {totals_path}")

except Exception as e:
    print(f"Error in rds_to_hdfs pipeline: {e}")
    raise  # LOCAL DEMO: do not hide the error, so Airflow shows the task as failed

print("data_pipeline ran successfully")
