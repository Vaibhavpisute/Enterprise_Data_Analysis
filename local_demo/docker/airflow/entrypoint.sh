#!/usr/bin/env bash
# Start Airflow in standalone mode (web server + scheduler in one container).
set -euo pipefail

airflow db migrate

# Create the login from .env. Ignore the error if it already exists (restart).
airflow users create \
  --username "${AIRFLOW_ADMIN_USER}" \
  --password "${AIRFLOW_ADMIN_PASSWORD}" \
  --firstname Demo --lastname Admin \
  --role Admin --email demo@example.com || true

exec airflow standalone
