"""Show what the pipeline put into the Hive tables (database staging_db):
staging_table, final_table, customer_yearly_sales and customer_sales_ranking.

Run it after the DAG has finished (it starts a small Spark session, so it takes ~20 seconds):

    docker compose exec airflow bash /opt/airflow/scripts/run_spark.sh /opt/airflow/scripts/check_results.py --counts
    docker compose exec airflow bash /opt/airflow/scripts/run_spark.sh /opt/airflow/scripts/check_results.py --table customer_yearly_sales

    --counts        only the row counts
    --table NAME    5 sample rows of one table
    --columns A,B   with --table: only these columns (for a narrow screen)
    (no flag)       row counts, then 5 sample rows of every table
"""
import argparse
import sys

from pyspark.sql import SparkSession

DATABASE = "staging_db"
SAMPLE_ROWS = 5
MAX_CELL = 32  # cut long values so each table fits on screen


def short(value):
    text = "NULL" if value is None else str(value)
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 3] + "..."


def print_table(headers, rows):
    cells = [[short(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for r in cells:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))


def main():
    parser = argparse.ArgumentParser(description="Show row counts and sample rows of the Hive tables.")
    parser.add_argument("--counts", action="store_true", help="print only the row counts")
    parser.add_argument("--table", metavar="NAME", help="print 5 sample rows of this table only")
    parser.add_argument("--columns", metavar="A,B,C", help="with --table: show only these columns (narrower output)")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("check_results").enableHiveSupport().getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    if not spark.catalog.databaseExists(DATABASE):
        print(f"Database '{DATABASE}' not found. Run the DAG 'sales_pipeline_local' first.")
        return 1
    tables = sorted(t.name for t in spark.catalog.listTables(DATABASE))
    if not tables:
        print(f"No tables found in '{DATABASE}'. Run the DAG 'sales_pipeline_local' first.")
        return 1
    if args.table and args.table not in tables:
        print(f"Table '{args.table}' not found. Tables: {', '.join(tables)}")
        return 1

    if not args.table:
        counts = [(t, spark.table(f"{DATABASE}.{t}").count()) for t in tables]
        print(f"\n=== Row counts in Hive database '{DATABASE}' ===")
        print_table(["table", "rows"], counts)
    if args.counts:
        return 0

    for t in tables:
        if args.table and t != args.table:
            continue
        print(f"\n=== {DATABASE}.{t} (first {SAMPLE_ROWS} rows) ===")
        df = spark.table(f"{DATABASE}.{t}")
        if args.columns:
            wanted = [c.strip() for c in args.columns.split(",")]
            missing = [c for c in wanted if c not in df.columns]
            if missing:
                print(f"Column(s) not found in {t}: {', '.join(missing)}. Columns: {', '.join(df.columns)}")
                return 1
            df = df.select(*wanted)
        df = df.limit(SAMPLE_ROWS)
        print_table(df.columns, [tuple(r) for r in df.collect()])
    return 0


if __name__ == "__main__":
    sys.exit(main())
