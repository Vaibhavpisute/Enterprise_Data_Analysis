import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    """One small local SparkSession for the whole test run (no cluster, no database, no Hive)."""
    session = (
        SparkSession.builder.master("local[1]")
        .appName("unit-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
