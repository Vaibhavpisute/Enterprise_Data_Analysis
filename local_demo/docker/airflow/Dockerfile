# Airflow + Java 17 + PySpark (Spark runs in local mode inside this one container)
FROM apache/airflow:2.10.5-python3.11

USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl procps \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /opt/spark-data /opt/airflow/state \
 && chown -R airflow:root /opt/spark-data /opt/airflow/state

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

USER airflow

# PySpark 3.5.x ships with Hadoop 3.3.4, so hadoop-aws must be 3.3.4 too.
ARG PYSPARK_VERSION=3.5.3
ARG HADOOP_AWS_VERSION=3.3.4
ARG AWS_SDK_VERSION=1.12.262
ARG PG_JDBC_VERSION=42.7.4

RUN pip install --no-cache-dir "pyspark==${PYSPARK_VERSION}"

# Put the S3A and PostgreSQL JDBC jars inside PySpark, so jobs need no internet at run time.
RUN JARS="$(python -c 'import os,pyspark;print(os.path.join(os.path.dirname(pyspark.__file__),"jars"))')" \
 && M2=https://repo1.maven.org/maven2 \
 && curl -fsSL -o "$JARS/hadoop-aws-${HADOOP_AWS_VERSION}.jar" \
      "$M2/org/apache/hadoop/hadoop-aws/${HADOOP_AWS_VERSION}/hadoop-aws-${HADOOP_AWS_VERSION}.jar" \
 && curl -fsSL -o "$JARS/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar" \
      "$M2/com/amazonaws/aws-java-sdk-bundle/${AWS_SDK_VERSION}/aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar" \
 && curl -fsSL -o "$JARS/postgresql-${PG_JDBC_VERSION}.jar" \
      "$M2/org/postgresql/postgresql/${PG_JDBC_VERSION}/postgresql-${PG_JDBC_VERSION}.jar"

COPY --chown=airflow:root entrypoint.sh /opt/airflow/entrypoint-local.sh
