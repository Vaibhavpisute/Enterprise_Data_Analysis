from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, sum, avg, year, month, dayofmonth
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number, rank, dense_rank, lag, lead, udf
from pyspark.sql.types import StringType
from main1 import DataPipeline

# Initialize Spark session with Hive support
spark = SparkSession.builder.appName("Rds_to_hdfs").master("yarn").enableHiveSupport().getOrCreate()

# JDBC connection properties
host = "jdbc:postgresql://database-1.cpyaoguwudqo.ap-south-1.rds.amazonaws.com:5432/health_db"
user = "postgres"
pwd = "mypostgreypassword"
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

# Sort and group the DataFrame
result_df = result_df.orderBy(col("order_date").desc())

# Fill null values in `price` and `total_price`
result_df = result_df.fillna({'price': 0, 'total_price': 0})

# Define UDF and apply it
upper_case_udf = udf(lambda name: name.upper(), StringType())
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


# Define HDFS path
hdfs_path = "hdfs:///user/hadoop/test_write_final_csv"

# Write DataFrame to HDFS
try:
    result_df.write.option("header", "true").option("delimiter", ",").mode("overwrite").csv(hdfs_path)
    print("DataFrame written to HDFS successfully")
except Exception as e:
    print(f"Error writing DataFrame to HDFS: {e}")

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


