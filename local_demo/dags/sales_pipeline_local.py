"""Local version of the Enterprise Sales Data Pipeline (replaces RDS -> HDFS -> Hive on AWS).

Four Spark tasks run one after the other, in local mode inside this container:
  1. extract_postgres_to_minio : PostgreSQL (sales_db) -> join/transform -> CSV files in MinIO
  2. transform_load_hive       : MinIO files -> Hive staging_table -> final_table (no duplicates)
  3. build_sales_reports       : final_table -> customer_yearly_sales
  4. build_customer_ranking    : final_table -> customer_sales_ranking (rank, lag, lead)
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

RUN_SPARK = "bash /opt/airflow/scripts/run_spark.sh"
JOBS = "/opt/airflow/spark_jobs"

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=20),
}

with DAG(
    dag_id="sales_pipeline_local",
    description="Local Docker version: PostgreSQL -> MinIO -> Hive -> sales reports",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,  # run it by hand (Trigger DAG button)
    catchup=False,
    tags=["sales", "local-demo"],
) as dag:

    extract_postgres_to_minio = BashOperator(
        task_id="extract_postgres_to_minio",
        bash_command=f"{RUN_SPARK} {JOBS}/rds_to_hdfs.py",
    )

    transform_load_hive = BashOperator(
        task_id="transform_load_hive",
        bash_command=f"{RUN_SPARK} {JOBS}/hdfs_to_hive.py load",
    )

    build_sales_reports = BashOperator(
        task_id="build_sales_reports",
        bash_command=f"{RUN_SPARK} {JOBS}/hdfs_to_hive.py reports",
    )

    build_customer_ranking = BashOperator(
        task_id="build_customer_ranking",
        bash_command=f"{RUN_SPARK} {JOBS}/hdfs_to_hive.py ranking",
    )

    extract_postgres_to_minio >> transform_load_hive >> build_sales_reports >> build_customer_ranking
