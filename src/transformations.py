"""Pure DataFrame transformations of the pipeline (no JDBC, HDFS or Hive code here).

Every function takes DataFrames in and returns a DataFrame out, so it can be
tested with a local SparkSession and hand-made data.
"""
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    abs as spark_abs, avg, coalesce, col, count, dayofmonth, dense_rank, lag, lead,
    lit, month, rank, row_number, sum, udf, year,
)
from pyspark.sql.functions import round as spark_round
from pyspark.sql.types import StringType
from pyspark.sql.window import Window


# ---------------------------------------------------------------- validate
def count_nulls(df: DataFrame) -> DataFrame:
    """One row: for every column, how many values are NULL."""
    return df.select([sum(col(c).isNull().cast("int")).alias(c) for c in df.columns])


def handle_missing_values(df: DataFrame) -> DataFrame:
    """Replace NULL price and total_price with 0."""
    return df.fillna({"price": 0, "total_price": 0})


# -------------------------------------------------------------------- join
def join_sources(customers_df, orders_df, order_items_df, products_df, categories_df, suppliers_df) -> DataFrame:
    """Inner join of the 6 source tables, starting from orders."""
    return orders_df.join(customers_df, orders_df.customer_id == customers_df.customer_id, "inner") \
                    .join(order_items_df, orders_df.order_id == order_items_df.order_id, "inner") \
                    .join(products_df, order_items_df.product_id == products_df.product_id, "inner") \
                    .join(categories_df, products_df.category_id == categories_df.category_id, "inner") \
                    .join(suppliers_df, products_df.supplier_id == suppliers_df.supplier_id, "inner")


def build_order_lines(full_df: DataFrame) -> DataFrame:
    """Pick the report columns, keep quantity >= 2 and add total_price = quantity * price."""
    return full_df.select("customer_name", "order_date", "product_name", "quantity", "price") \
                  .withColumnRenamed("customer_name", "customer") \
                  .filter(col("quantity") >= 2) \
                  .withColumn("total_price", col("quantity") * col("price"))


# ---------------------------------------------------------------- enrich
def add_upper_customer_name(df: DataFrame) -> DataFrame:
    # A NULL customer name must not crash the Spark task, so it stays NULL.
    upper_case_udf = udf(lambda name: name.upper() if name is not None else None, StringType())
    return df.withColumn("upper_customer_name", upper_case_udf(col("customer")))


def add_date_parts(df: DataFrame) -> DataFrame:
    return df.withColumn("order_year", year("order_date")) \
             .withColumn("order_month", month("order_date")) \
             .withColumn("order_day", dayofmonth("order_date"))


def add_window_columns(df: DataFrame) -> DataFrame:
    """Per-customer window functions, ordered by order_date."""
    window_spec = Window.partitionBy("customer").orderBy("order_date")
    return df.withColumn("row_num", row_number().over(window_spec)) \
             .withColumn("rank", rank().over(window_spec)) \
             .withColumn("dense_rank", dense_rank().over(window_spec)) \
             .withColumn("cumulative_sum", sum("quantity").over(window_spec)) \
             .withColumn("lag_quantity", lag("quantity", 1).over(window_spec)) \
             .withColumn("lead_quantity", lead("quantity", 1).over(window_spec)) \
             .withColumn("percentage", (col("quantity") / sum("quantity").over(window_spec)) * 100)


def customer_totals(df: DataFrame) -> DataFrame:
    """Total quantity and average price per customer."""
    return df.groupBy("customer").agg(
        sum("quantity").alias("total_quantity"),
        avg("price").alias("avg_price"),
    )


# ------------------------------------------------- summary / ranking (Hive side)
def yearly_customer_summary(df: DataFrame) -> DataFrame:
    """Per customer and year: total quantity, total sales, order lines, average price."""
    return df.groupBy("customer", year("order_date").alias("order_year")).agg(
        sum("quantity").alias("total_quantity"),
        spark_round(sum("total_price"), 2).alias("total_sales"),
        count(lit(1)).alias("order_count"),
        spark_round(avg("price"), 2).alias("average_price"),
    )


def rank_customers(df: DataFrame) -> DataFrame:
    """Rank customers by total sales (RANK and DENSE_RANK) and add row number, previous and next order value."""
    customer_window = Window.partitionBy("customer").orderBy("order_date")
    ranking_window = Window.orderBy(col("customer_total_sales").desc())
    return df.withColumn("customer_total_sales", spark_round(sum("total_price").over(Window.partitionBy("customer")), 2)) \
             .withColumn("sales_rank", rank().over(ranking_window)) \
             .withColumn("sales_dense_rank", dense_rank().over(ranking_window)) \
             .withColumn("order_row_num", row_number().over(customer_window)) \
             .withColumn("prev_order_value", spark_round(lag("total_price", 1).over(customer_window), 2)) \
             .withColumn("next_order_value", spark_round(lead("total_price", 1).over(customer_window), 2)) \
             .select("customer", "order_date", "total_price", "customer_total_sales", "sales_rank",
                     "sales_dense_rank", "order_row_num", "prev_order_value", "next_order_value")


# --------------------------------------------------------------- reconcile
def reconcile_totals(source_df: DataFrame, target_df: DataFrame, key: str = "customer",
                     value: str = "total_price", tolerance: float = 0.005) -> DataFrame:
    """Compare row count and total of `value` per `key` between source and target.

    Returns only the keys that do not match (empty DataFrame = reconciled).
    A key missing on one side counts as 0 rows and total 0.
    """
    def per_key(df, side):
        return df.groupBy(col(key).alias(f"{side}_key")).agg(
            count(lit(1)).alias(f"{side}_rows"),
            sum(value).alias(f"{side}_total"),
        )

    # eqNullSafe: a NULL key on both sides is the same key (e.g. a customer without a name)
    joined = per_key(source_df, "source").join(
        per_key(target_df, "target"), col("source_key").eqNullSafe(col("target_key")), "full_outer"
    ).select(
        coalesce(col("source_key"), col("target_key")).alias(key),
        coalesce(col("source_rows"), lit(0)).alias("source_rows"),
        coalesce(col("target_rows"), lit(0)).alias("target_rows"),
        coalesce(col("source_total"), lit(0.0)).alias("source_total"),
        coalesce(col("target_total"), lit(0.0)).alias("target_total"),
    )
    return joined.filter(
        (col("source_rows") != col("target_rows"))
        | (spark_abs(col("source_total") - col("target_total")) > tolerance)
    )


class ReconciliationError(RuntimeError):
    """Source and target do not have the same row count / total."""


def check_reconciliation(source_df: DataFrame, target_df: DataFrame, key: str = "customer",
                         value: str = "total_price", tolerance: float = 0.005) -> dict:
    """Compare overall row count and total of `value` (and per `key`); log the result.

    Raises ReconciliationError when anything differs. Returns the totals when everything matches.
    """
    def totals(df):
        row = df.agg(count(lit(1)).alias("rows"), sum(value).alias("total")).collect()[0]
        return row["rows"], float(row["total"] or 0.0)

    source_rows, source_total = totals(source_df)
    target_rows, target_total = totals(target_df)
    print(f"Reconciliation: source rows={source_rows}, total {value}={source_total:.2f}")
    print(f"Reconciliation: target rows={target_rows}, total {value}={target_total:.2f}")

    mismatches = reconcile_totals(source_df, target_df, key, value, tolerance).limit(10).collect()
    if source_rows != target_rows or abs(source_total - target_total) > tolerance or mismatches:
        sample = ", ".join(f"{r[key]} (source {r['source_rows']}/{r['source_total']:.2f}, "
                           f"target {r['target_rows']}/{r['target_total']:.2f})" for r in mismatches)
        message = (f"Reconciliation FAILED: rows {source_rows} vs {target_rows}, "
                   f"total {source_total:.2f} vs {target_total:.2f}. Mismatching {key}: {sample or 'none'}")
        print(message)
        raise ReconciliationError(message)
    print("Reconciliation OK: row count and total sales match")
    return {"rows": source_rows, "total": source_total}
