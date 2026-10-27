import os

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from main1 import DataPipeline
from src.transformations import (
    add_date_parts, add_upper_customer_name, add_window_columns, build_order_lines,
    count_nulls, customer_totals, handle_missing_values, join_sources,
)

# Initialize Spark session with Hive support
spark = SparkSession.builder.appName("Rds_to_hdfs").master("yarn").enableHiveSupport().getOrCreate()

# JDBC connection properties
# Connection settings come from environment variables (see .env.example)
host = f"jdbc:postgresql://{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ.get('SOURCE_DB', 'health_db')}"
user = os.environ.get("POSTGRES_USER")
pwd = os.environ.get("POSTGRES_PASSWORD")
driver = "org.postgresql.Driver"

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
full_df = join_sources(customers_df, orders_df, order_items_df, products_df, categories_df, suppliers_df)

print("Joined DataFrame:")
full_df.show()

#keep this
# Select specific columns and rename as necessary
result_df = build_order_lines(full_df)

print("Filtered and selected DataFrame:")
result_df.show()

# These 6 columns are what the Hive staging table (hdfs_to_hive.py) expects.
# Writing only the customer totals to that location made the staging table not match the files.
detail_df = result_df

# Sort and group the DataFrame
result_df = result_df.orderBy(col("order_date").desc())

# Fill null values in `price` and `total_price`
result_df = handle_missing_values(result_df)

# Upper-case customer name (UDF)
result_df = add_upper_customer_name(result_df)

# Extract date components
result_df = add_date_parts(result_df)

# Window functions and percentage
result_df = add_window_columns(result_df)

# Aggregate multiple columns
result_df = customer_totals(result_df)

print("Final DataFrame Created Successfully")

# Repartition the DataFrame
result_df = result_df.repartition(5)

# Show final result
result_df.show()

# Count null values in each column 
null_counts = count_nulls(result_df)
# Show the result 
null_counts.show()


# Define HDFS paths
detail_path = "hdfs:///user/hadoop/test_write_final_csv"   # input of the Hive staging table
totals_path = "hdfs:///user/hadoop/customer_totals_csv"    # customer totals

# Write DataFrames to HDFS
# The detail files have no header line: the Hive staging table does not skip it, so a header
# would be loaded as an extra row of NULLs.
try:
    detail_df.write.option("header", "false").option("delimiter", ",").mode("overwrite").csv(detail_path)
    print(f"Sales detail written to {detail_path}")
    result_df.write.option("header", "true").option("delimiter", ",").mode("overwrite").csv(totals_path)
    print(f"Customer totals written to {totals_path}")
except Exception as e:
    print(f"Error writing DataFrame to HDFS: {e}")
    raise

#df.write.option("header", "true").option("delimiter", ",").mode("overwrite").csv(hdfs_path)
# Write DataFrame to CSV df.write.mode("overwrite").csv(hdfs_path)
#result_df.write.mode("overwrite").parquet(hdfs_path)

# Check if the directory is created
print("Check the directory listing using: hdfs dfs -ls /user/hadoop/test_write")



print("DataFrame written to HDFS successfully")
print("data_pipeline ran successfully")



print("null counts")
null_counts.show()
result_df.show()


