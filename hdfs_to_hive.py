from pyspark.sql import SparkSession

# Initialize Spark session with Hive support
spark = SparkSession.builder.appName("Rds_to_hdfs").master("yarn").enableHiveSupport().getOrCreate()

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


def create_database_and_tables():
    try:
        # Create Hive database if it doesn't exist
        spark.sql("CREATE DATABASE IF NOT EXISTS staging_db")

        # Use the staging database
        spark.sql("USE staging_db")

        # Drop the staging table if it exists
        spark.sql("DROP TABLE IF EXISTS staging_table")


        # Create Hive staging table
        spark.sql("""
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
            LOCATION 'hdfs:///user/hadoop/test_write_final_csv'
        """)
        print("Hive staging table created successfully")

        # Drop the final table if it exists
        spark.sql("DROP TABLE IF EXISTS final_table")

        # Remove duplicates and create final table
        if table_is_empty("staging_table"):
            raise RuntimeError("staging_table is empty. Nothing to load into final_table.")
        else:
            spark.sql("""
                CREATE TABLE IF NOT EXISTS final_table AS
                SELECT DISTINCT *
                FROM staging_table
            """)
            print("Final table created successfully")

        # Drop the business logic table if it exists
        spark.sql("DROP TABLE IF EXISTS customer_yearly_sales")

        # Example business logic: Calculate total sales by customer and year and store in a final table
        if table_is_empty("final_table"):
            raise RuntimeError("final_table is empty. Nothing to build customer_yearly_sales from.")
        else:
            # total_quantity = SUM(quantity), total_sales = SUM(total_price) (the sales value),
            # order_count = number of order lines. Before, total_sales was SUM(quantity).
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
        print(f"Error creating database and tables: {e}")
        raise

# Call the function to create database and tables
create_database_and_tables()
