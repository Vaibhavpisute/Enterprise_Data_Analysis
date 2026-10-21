<#
.SYNOPSIS
  Reset the local demo so the pipeline can run "fresh".

.DESCRIPTION
  Clears:  - all files in the MinIO bucket (CSV files)
           - the local Hive tables (Spark warehouse + metastore)
           - the Airflow run history of the DAG (skip with -KeepAirflowHistory)
  Keeps:   - the source database sales_db (all 6 tables and their data)
           - the MinIO bucket itself, the containers, the images, all logins

  The containers must be running:  docker compose up -d

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\reset_demo.ps1
#>
param([switch]$KeepAirflowHistory)

$ErrorActionPreference = 'Continue'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path $dockerBin) { $env:Path += ";$dockerBin" }
Set-Location (Split-Path -Parent $PSScriptRoot)   # local_demo folder (where docker-compose.yml is)

function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# --- read the bucket name from .env (no secrets are printed)
$bucket = ((Get-Content .env | Where-Object { $_ -match '^MINIO_BUCKET=' }) -split '=', 2)[1].Trim()
if (-not $bucket) { Fail "MINIO_BUCKET not found in .env" }

# --- containers must be up
foreach ($svc in 'postgres', 'minio', 'airflow') {
    $id = docker compose ps -q $svc
    if (-not $id -or (docker inspect -f '{{.State.Running}}' $id) -ne 'true') {
        Fail "Service '$svc' is not running. Start it first:  docker compose up -d"
    }
}

Step "1/3  Clearing MinIO bucket '$bucket'"
docker compose run --rm -T minio-init rm --recursive --force "local/$bucket" 2>$null | Out-Null
$left = @(docker compose run --rm -T minio-init ls --recursive "local/$bucket" 2>$null).Count
if ($left -ne 0) { Fail "Bucket still has $left entries." }
Write-Host "    bucket is empty"

Step "2/3  Clearing local Hive tables (Spark warehouse + metastore)"
docker compose exec -T airflow bash -c 'rm -rf /opt/spark-data/warehouse /opt/spark-data/metastore_db /opt/spark-data/derby.log; ls -A /opt/spark-data | wc -l' |
    ForEach-Object { Write-Host "    items left in /opt/spark-data: $_" }

if (-not $KeepAirflowHistory) {
    Step "3/3  Clearing Airflow run history for sales_pipeline_local"
    docker compose exec -T airflow airflow dags delete sales_pipeline_local --yes 2>$null | Out-Null
    # The DAG file is still there, so Airflow registers the DAG again within ~30-60 seconds.
    # "dags list" shows the DAG before it can be triggered. "dags details" reads the stored (serialized)
    # DAG, which is what a trigger needs, so wait for that to work.
    $back = $false
    for ($i = 0; $i -lt 36; $i++) {
        Start-Sleep 5
        docker compose exec -T airflow airflow dags details sales_pipeline_local *> $null
        if ($LASTEXITCODE -eq 0) { $back = $true; break }
    }
    if (-not $back) { Fail "DAG did not come back in Airflow. Check: docker compose logs airflow --tail 50" }
    docker compose exec -T airflow airflow dags unpause sales_pipeline_local 2>$null | Out-Null
    Write-Host "    DAG is loaded again and unpaused (no old runs). You can trigger it now."
} else {
    Step "3/3  Keeping Airflow run history (-KeepAirflowHistory)"
}

Step "Check: source data in sales_db is untouched"
$src = "SELECT (SELECT count(*) FROM customers) || ' customers, ' || (SELECT count(*) FROM orders) || ' orders, ' || (SELECT count(*) FROM order_items) || ' order items';" |
    docker compose exec -T postgres sh -c 'psql -At -U $POSTGRES_USER -d $POSTGRES_DB'
Write-Host "    sales_db: $src"

Write-Host "`nReset done. Trigger DAG 'sales_pipeline_local' in Airflow to run again." -ForegroundColor Green
