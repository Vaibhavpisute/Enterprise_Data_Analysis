#!/usr/bin/env bash
# Short way to run check_results.py with the Spark settings:  bash scripts/check_results.sh --counts
# Spark's start-up warnings are hidden; if the check fails, they are printed.
log="$(mktemp)"
bash /opt/airflow/scripts/run_spark.sh /opt/airflow/scripts/check_results.py "$@" 2>"$log" || { cat "$log" >&2; exit 1; }
