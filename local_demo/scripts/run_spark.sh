#!/usr/bin/env bash
# Run one Spark job in local mode.   Usage: run_spark.sh <job.py> [job arguments]
# All cluster/connection settings live here, so the job files stay close to the originals.
set -euo pipefail

JOB="${1:?usage: run_spark.sh <job.py> [args]}"
shift

exec spark-submit \
  --master "local[${SPARK_LOCAL_CORES:-2}]" \
  --driver-memory "${SPARK_DRIVER_MEMORY:-1g}" \
  --conf spark.ui.enabled=false \
  --conf spark.sql.shuffle.partitions=4 \
  --conf spark.sql.warehouse.dir=/opt/spark-data/warehouse \
  --conf "spark.hadoop.javax.jdo.option.ConnectionURL=jdbc:derby:;databaseName=/opt/spark-data/metastore_db;create=true" \
  --conf "spark.hadoop.fs.s3a.endpoint=${MINIO_ENDPOINT:?MINIO_ENDPOINT is not set}" \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
  --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
  "$JOB" "$@"
