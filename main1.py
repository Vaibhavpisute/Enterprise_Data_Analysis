from pyspark.sql import SparkSession

class DataPipeline:
    """
    Data pipeline class for reading from SQL and loading into Hive.
    """

    def __init__(self, jdbc_url, user, pwd, driver):
        # Initialize Spark session
        self.spark = SparkSession.builder \
            .appName("hbtohive_card_details") \
            .master("yarn") \
            .enableHiveSupport() \
            .getOrCreate()
        
        print("Spark session created successfully")

        # Set JDBC connection properties
        self.host = jdbc_url
        self.user = user
        self.pwd = pwd
        self.driver = driver

    def fetch_data_from_sql(self, db_table):
        """
        Fetch data from SQL table and load into DataFrame.
        """
        db_table=db_table
        # JDBC connection properties
        connection_properties = {
            "url": self.host,
            "user": self.user,
            "password": self.pwd,
            "driver": self.driver,
            "dbtable": db_table
        }
        print(f"Reading {db_table}")
        # Read data into DataFrame Fom Rdbms
        dataframe = self.spark.read.format("jdbc")\
        .option("url", connection_properties["url"])\
        .option("user", connection_properties["user"]) \
        .option("password", connection_properties["password"]) \
        .option("driver", connection_properties["driver"]) \
        .option("dbtable", connection_properties["dbtable"]) \
        .load()
        
        # Show sample data
        dataframe.show(10, False)
        print(f"Table read successfully: {db_table}")
        
        return dataframe

