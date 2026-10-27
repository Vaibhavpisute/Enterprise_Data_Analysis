from datetime import date

import pytest

from src.transformations import (
    ReconciliationError, add_upper_customer_name, add_window_columns, build_order_lines,
    check_reconciliation, count_nulls, handle_missing_values, join_sources,
    rank_customers, reconcile_totals, yearly_customer_summary,
)

LINES_SCHEMA = "customer string, order_date date, product_name string, quantity int, price double, total_price double"


# ---------------------------------------------------------------- null count
def test_count_nulls_returns_nulls_per_column(spark):
    df = spark.createDataFrame(
        [("Ann", 10.0), (None, None), (None, 5.0)],
        "customer string, price double",
    )
    row = count_nulls(df).collect()[0]
    assert row["customer"] == 2
    assert row["price"] == 1


# ------------------------------------------------------------ missing values
def test_handle_missing_values_leaves_no_nulls_in_price_columns(spark):
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), "P1", 2, 10.0, 20.0),
         ("Bob", date(2023, 1, 2), "P2", 3, None, None)],
        LINES_SCHEMA,
    )
    result = handle_missing_values(df)
    nulls = count_nulls(result.select("price", "total_price")).collect()[0]
    assert nulls["price"] == 0 and nulls["total_price"] == 0


def test_handle_missing_values_keeps_all_rows_and_valid_values(spark):
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), "P1", 2, 10.0, 20.0),
         ("Bob", date(2023, 1, 2), "P2", 3, None, None)],
        LINES_SCHEMA,
    )
    result = {r["customer"]: r for r in handle_missing_values(df).collect()}
    assert len(result) == 2
    assert result["Ann"]["price"] == 10.0 and result["Ann"]["total_price"] == 20.0
    assert result["Bob"]["price"] == 0.0 and result["Bob"]["total_price"] == 0.0


# --------------------------------------------------------------------- join
def make_six_tables(spark):
    customers = spark.createDataFrame([(1, "Ann"), (2, "Bob")], "customer_id int, customer_name string")
    orders = spark.createDataFrame(
        [(1, 1, date(2023, 1, 1)), (2, 2, date(2023, 1, 2)), (3, 1, date(2023, 1, 3)), (4, 99, date(2023, 1, 4))],
        "order_id int, customer_id int, order_date date",
    )
    order_items = spark.createDataFrame(
        [(1, 1, 10, 2, 5.0), (2, 1, 20, 1, 8.0), (3, 2, 10, 4, 5.0), (4, 3, 20, 3, 8.0), (5, 4, 10, 2, 5.0)],
        "order_item_id int, order_id int, product_id int, quantity int, price double",
    )
    products = spark.createDataFrame(
        [(10, "Pen", 100, 1000), (20, "Book", 200, 2000)],
        "product_id int, product_name string, category_id int, supplier_id int",
    )
    categories = spark.createDataFrame([(100, "Office"), (200, "Study")], "category_id int, category_name string")
    suppliers = spark.createDataFrame([(1000, "Acme"), (2000, "Globex")], "supplier_id int, supplier_name string")
    return customers, orders, order_items, products, categories, suppliers


def test_join_sources_returns_one_row_per_order_item_without_duplicates(spark):
    customers, orders, order_items, products, categories, suppliers = make_six_tables(spark)
    joined = join_sources(customers, orders, order_items, products, categories, suppliers)
    # 5 order items, but item 5 belongs to an order of unknown customer 99, so the inner join drops it.
    assert joined.count() == 4
    selected = joined.select("order_item_id", "customer_name", "product_name", "category_name", "supplier_name")
    assert selected.distinct().count() == 4


def test_join_sources_has_columns_of_all_six_tables(spark):
    joined = join_sources(*make_six_tables(spark))
    for name in ["customer_name", "order_date", "quantity", "price", "product_name", "category_name", "supplier_name"]:
        assert name in joined.columns


# ------------------------------------------------------------------ ranking
def test_rank_customers_gives_ties_the_same_rank_and_skips_numbers(spark):
    # Ann and Bob both have 300, Cara 100, Dan 50.
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), 300.0), ("Bob", date(2023, 1, 1), 300.0),
         ("Cara", date(2023, 1, 1), 100.0), ("Dan", date(2023, 1, 1), 50.0)],
        "customer string, order_date date, total_price double",
    )
    rows = {r["customer"]: r for r in rank_customers(df).collect()}
    # RANK leaves a gap after a tie: 1, 1, 3, 4
    assert [rows[c]["sales_rank"] for c in ["Ann", "Bob", "Cara", "Dan"]] == [1, 1, 3, 4]
    # DENSE_RANK has no gap: 1, 1, 2, 3
    assert [rows[c]["sales_dense_rank"] for c in ["Ann", "Bob", "Cara", "Dan"]] == [1, 1, 2, 3]


# ------------------------------------------------------------ window columns
def test_window_columns_cumulative_sum_lag_and_lead_for_one_customer(spark):
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), 2, 10.0), ("Ann", date(2023, 1, 2), 3, 10.0),
         ("Ann", date(2023, 1, 3), 5, 10.0), ("Bob", date(2023, 1, 1), 7, 10.0)],
        "customer string, order_date date, quantity int, price double",
    )
    ann = [r for r in add_window_columns(df).orderBy("order_date").collect() if r["customer"] == "Ann"]
    assert [r["row_num"] for r in ann] == [1, 2, 3]
    assert [r["cumulative_sum"] for r in ann] == [2, 5, 10]          # 2, 2+3, 2+3+5
    assert [r["lag_quantity"] for r in ann] == [None, 2, 3]          # previous order
    assert [r["lead_quantity"] for r in ann] == [3, 5, None]         # next order


def test_build_order_lines_keeps_quantity_two_or_more_and_adds_total_price(spark):
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), "Pen", 1, 5.0), ("Bob", date(2023, 1, 2), "Pen", 3, 5.0)],
        "customer_name string, order_date date, product_name string, quantity int, price double",
    )
    rows = build_order_lines(df).collect()
    assert len(rows) == 1
    assert rows[0]["customer"] == "Bob" and rows[0]["total_price"] == 15.0


# --------------------------------------------------------- yearly summary
def test_yearly_customer_summary_totals_per_customer_and_year(spark):
    df = spark.createDataFrame(
        [("Ann", date(2023, 1, 1), "Pen", 2, 10.0, 20.0), ("Ann", date(2023, 6, 1), "Book", 3, 20.0, 60.0),
         ("Ann", date(2024, 1, 1), "Pen", 1, 10.0, 10.0), ("Bob", date(2023, 2, 1), "Pen", 4, 5.0, 20.0)],
        LINES_SCHEMA,
    )
    rows = {(r["customer"], r["order_year"]): r for r in yearly_customer_summary(df).collect()}
    assert len(rows) == 3
    ann_2023 = rows[("Ann", 2023)]
    assert ann_2023["total_quantity"] == 5
    assert ann_2023["total_sales"] == 80.0
    assert ann_2023["order_count"] == 2
    assert ann_2023["average_price"] == 15.0
    assert rows[("Ann", 2024)]["total_sales"] == 10.0
    assert rows[("Bob", 2023)]["total_sales"] == 20.0


# ----------------------------------------------------------- reconciliation
def make_totals(spark, rows):
    return spark.createDataFrame(rows, "customer string, total_price double")


def test_reconcile_totals_passes_when_totals_match(spark):
    source = make_totals(spark, [("Ann", 20.0), ("Ann", 60.0), ("Bob", 20.0)])
    target = make_totals(spark, [("Ann", 60.0), ("Ann", 20.0), ("Bob", 20.0)])
    assert reconcile_totals(source, target).count() == 0


def test_reconcile_totals_fails_when_a_row_is_missing_in_target(spark):
    source = make_totals(spark, [("Ann", 20.0), ("Ann", 60.0), ("Bob", 20.0)])
    target = make_totals(spark, [("Ann", 20.0), ("Bob", 20.0)])   # one Ann row (60.0) is missing
    mismatches = reconcile_totals(source, target).collect()
    assert len(mismatches) == 1
    assert mismatches[0]["customer"] == "Ann"
    assert mismatches[0]["source_total"] == 80.0 and mismatches[0]["target_total"] == 20.0


def test_reconcile_totals_fails_when_a_whole_customer_is_missing(spark):
    source = make_totals(spark, [("Ann", 20.0), ("Bob", 20.0)])
    target = make_totals(spark, [("Ann", 20.0)])
    assert [r["customer"] for r in reconcile_totals(source, target).collect()] == ["Bob"]


def test_reconcile_totals_treats_a_null_customer_as_one_key(spark):
    source = make_totals(spark, [(None, 20.0), ("Ann", 5.0)])
    target = make_totals(spark, [(None, 20.0), ("Ann", 5.0)])
    assert reconcile_totals(source, target).count() == 0


# ------------------------------- final pipeline step: source vs loaded Hive data
def test_check_reconciliation_passes_and_returns_totals_when_hive_matches_source(spark):
    # Source = the real chain: 6-table join -> order lines. Target = what was "loaded" (same lines).
    source = build_order_lines(join_sources(*make_six_tables(spark))).select("customer", "total_price")
    loaded = spark.createDataFrame(
        [("Ann", 10.0), ("Bob", 20.0), ("Ann", 24.0)], "customer string, total_price double"
    )
    # Order lines with quantity >= 2: Ann 2*5=10, Bob 4*5=20, Ann 3*8=24 (the quantity-1 item is dropped).
    result = check_reconciliation(source, loaded)
    assert result == {"rows": 3, "total": 54.0}


def test_check_reconciliation_raises_when_a_row_is_missing_in_hive(spark):
    source = make_totals(spark, [("Ann", 10.0), ("Bob", 20.0), ("Ann", 24.0)])
    loaded = make_totals(spark, [("Ann", 10.0), ("Bob", 20.0)])          # Ann's 24.0 line was not loaded
    with pytest.raises(ReconciliationError, match="Reconciliation FAILED"):
        check_reconciliation(source, loaded)


def test_check_reconciliation_raises_when_total_differs_but_row_count_is_equal(spark):
    source = make_totals(spark, [("Ann", 10.0), ("Bob", 20.0)])
    loaded = make_totals(spark, [("Ann", 10.0), ("Bob", 25.0)])
    with pytest.raises(ReconciliationError):
        check_reconciliation(source, loaded)


# ------------------------------------------------------------------- UDF
def test_add_upper_customer_name_upper_cases_and_keeps_null(spark):
    df = spark.createDataFrame([("ann",), (None,)], "customer string")
    names = [r["upper_customer_name"] for r in add_upper_customer_name(df).collect()]
    assert sorted(names, key=lambda n: (n is None, n)) == ["ANN", None]
