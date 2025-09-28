# 🏥 Health Data Pipeline

[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-FDEE21?style=flat-square&logo=apachespark&logoColor=black)](https://spark.apache.org/)
[![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=flat-square&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/)
[![Python](https://img.shields.io/badge/python-3670A0?style=flat-square&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/postgres-%23316192.svg?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Apache Hive](https://img.shields.io/badge/Apache%20Hive-FDEE21?style=flat-square&logo=apachehive&logoColor=black)](https://hive.apache.org/)

A comprehensive big data analytics solution for healthcare and e-commerce data processing, designed to analyze customer orders, product trends, and sales patterns at scale using distributed computing technologies.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Data Pipeline Flow](#data-pipeline-flow)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Monitoring](#monitoring)

## 🔍 Overview

This project implements a robust, scalable data pipeline architecture for processing customer order data and generating business insights. Built on AWS cloud infrastructure with Apache Spark and Hive, it processes large-scale transactional data to provide comprehensive analytics on customer behavior, product performance, and sales trends.

### Key Objectives

- **Sales Analytics**: Analyze customer purchasing patterns and product performance
- **Data Integration**: Seamlessly integrate data from multiple business entities (customers, orders, products, suppliers)
- **Business Intelligence**: Generate yearly sales reports and customer insights
- **Data Quality**: Ensure data integrity through comprehensive validation and deduplication
- **Scalability**: Handle large volumes of transactional data efficiently
- **Automation**: Provide end-to-end automated data processing workflows

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ PostgreSQL RDS  │───▶│   Apache Spark  │───▶│      HDFS       │
│  (Source Data)  │    │ (ETL Processing)│    │ (Data Storage)  │
│   - Customers   │    │   - PySpark     │    │  - Raw CSV      │
│   - Orders      │    │   - DataFrames  │    │  - Processed    │
│   - Products    │    │   - Window Funcs│    │                 │
│   - Categories  │    │   - Aggregations│    │                 │
│   - Suppliers   │    └─────────────────┘    └─────────────────┘
└─────────────────┘                                    │
                                                       ▼
                            ┌─────────────────┐    ┌─────────────────┐
                            │   Apache Hive   │◀───│   Data Mart     │
                            │ - Staging Table │    │ - Final Table   │
                            │ - Final Table   │    │ - Business      │
                            │ - Sales Summary │    │   Analytics     │
                            └─────────────────┘    └─────────────────┘
```

## ✨ Features

### Data Processing
- **Multi-Table ETL**: Extract data from 6 related PostgreSQL tables (Customers, Orders, Order_Items, Products, Categories, Suppliers)
- **Advanced Joins**: Complex inner joins across multiple tables for comprehensive data integration
- **Data Transformation**: Column renaming, filtering, calculated fields (total_price = quantity × price)
- **Window Functions**: Row numbering, ranking, cumulative calculations, and lag/lead operations
- **UDF Applications**: Custom transformations like uppercase customer names

### Analytics & Insights
- **Sales Analysis**: Customer-wise total quantities and average prices
- **Date Analytics**: Extract year, month, day components for time-series analysis
- **Customer Segmentation**: Ranking customers by order frequency and purchase behavior
- **Product Performance**: Filter products with quantity >= 2 for meaningful analysis
- **Trend Analysis**: Year-over-year sales comparisons and growth metrics

### Data Quality & Operations
- **Deduplication**: Remove duplicate records using DISTINCT operations
- **Null Handling**: Fill missing values for price and total_price columns
- **Data Validation**: Count null values across all columns for quality assessment
- **Partitioning**: Optimize data storage with 5-way partitioning
- **Schema Management**: Automated table creation and schema validation

## 🛠️ Tech Stack

### Big Data & Processing
- **Apache Spark 3.x**: Distributed data processing engine
- **PySpark**: Python API for Spark with advanced transformations
- **Apache Hive**: Data warehouse for SQL-based analytics
- **HDFS**: Hadoop Distributed File System for scalable storage

### Database & Storage
- **PostgreSQL**: Source relational database on AWS RDS
- **AWS RDS**: Managed database service
- **CSV Storage**: Structured data export format

### Data Processing Libraries
- **Spark SQL**: For complex queries and aggregations
- **Window Functions**: Advanced analytics operations
- **UDFs**: Custom user-defined functions
- **DataFrame API**: High-level data manipulation

## 📋 Prerequisites

- Python 3.8+
- Apache Spark 3.2+
- PostgreSQL JDBC Driver
- AWS CLI configured with appropriate permissions
- Hadoop ecosystem (HDFS, Hive) properly configured
- Network access to PostgreSQL RDS instance

### Required Python Packages
```
pyspark>=3.2.0
py4j
psycopg2-binary (for PostgreSQL connectivity)
```

### AWS/Database Permissions Required
- RDS: Read access to PostgreSQL database
- S3/HDFS: Read/Write access for data storage
- Network: Security group access to RDS instance

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/health_data_pipeline.git
cd health_data_pipeline
```

### 2. Configure Database Connection
Update the connection parameters in `rds_to_hdfs.py`:
```python
host = "jdbc:postgresql://your-database-endpoint:5432/your_database"
user = "your_username"
pwd = "your_password"
driver = "org.postgresql.Driver"
```

### 3. Set Up HDFS Path
Ensure HDFS directory exists:
```bash
hdfs dfs -mkdir -p /user/hadoop/test_write_final_csv
```

### 4. Start Spark Session
```bash
spark-submit --jars /path/to/postgresql-jdbc.jar rds_to_hdfs.py
```

## 💻 Usage

### 1. Run Data Extraction and Processing
```bash
# Execute the main ETL pipeline
python rds_to_hdfs.py
```

### 2. Create Hive Tables
```bash
# Run Hive table creation
python hdfs_to_hive.py
```

### 3. Verify Results
```bash
# Check HDFS output
hdfs dfs -ls /user/hadoop/test_write_final_csv

# Query Hive tables
beeline -u jdbc:hive2://localhost:10000
> USE staging_db;
> SELECT * FROM customer_yearly_sales LIMIT 10;
```

## 🔄 Data Pipeline Flow

### 1. Data Extraction Phase
- Connect to PostgreSQL RDS database
- Extract data from 6 source tables:
  - **Customers**: Customer information and contact details
  - **Orders**: Order transactions with dates
  - **Order_Items**: Product quantities and prices per order
  - **Products**: Product catalog with categories and suppliers
  - **Categories**: Product categorization
  - **Suppliers**: Supplier information

### 2. Data Transformation Phase
- **Multi-table Joins**: Create comprehensive dataset by joining all tables
- **Data Filtering**: Apply business rules (quantity >= 2)
- **Calculated Fields**: Generate total_price = quantity × price
- **Date Operations**: Extract year, month, day components
- **Window Analytics**: Apply ranking, cumulative sums, lag/lead operations
- **Data Cleaning**: Handle null values and apply UDFs

### 3. Data Aggregation Phase
- **Customer Analytics**: Group by customer for total quantities and average prices
- **Business Metrics**: Calculate percentages and cumulative statistics
- **Data Quality Checks**: Count null values across all columns
- **Partitioning**: Optimize data layout with 5-way partitioning

### 4. Data Storage Phase
- **HDFS Storage**: Write processed data as CSV to HDFS
- **Hive Integration**: Create external tables pointing to HDFS data
- **Data Mart Creation**: Build final analytical tables
- **Business Tables**: Generate customer yearly sales summaries

## 📁 Project Structure

```
health_data_pipeline/
├── src/
│   ├── main1.py                # DataPipeline class for database connections
│   ├── rds_to_hdfs.py         # Main ETL pipeline script
│   └── hdfs_to_hive.py        # Hive table creation and management
├── sql/
│   └── sql_whole_ddl.sql      # Database schema and sample data            
└── README.md                 # This file
```

## ⚙️ Configuration

### Database Configuration
Edit connection parameters in your scripts:
```python
# PostgreSQL RDS Connection
JDBC_URL = "jdbc:postgresql://database-endpoint:5432/database_name"
USERNAME = "your_username"
PASSWORD = "your_password"
DRIVER = "org.postgresql.Driver"
```

### HDFS Configuration
```python
# HDFS Storage Path
HDFS_OUTPUT_PATH = "hdfs:///user/hadoop/test_write_final_csv"
```

### Spark Configuration
```python
# Spark Session Configuration
spark = SparkSession.builder \
    .appName("RDS_to_HDFS_Pipeline") \
    .master("yarn") \
    .enableHiveSupport() \
    .getOrCreate()
```

## 📊 Monitoring

### Data Quality Monitoring
- **Null Value Counts**: Automated checking across all columns
- **Record Counts**: Validation of data volume at each stage
- **Schema Validation**: Ensure data types and structures are maintained
  
### Performance Monitoring
- **Spark UI**: Monitor job execution and resource utilization
- **YARN ResourceManager**: Track cluster resource usage
- **Hive Metastore**: Monitor table metadata and statistics

---


