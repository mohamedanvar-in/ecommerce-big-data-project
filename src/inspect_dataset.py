from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("EcommerceSalesAnalysis")
    .master("local[*]")
    .getOrCreate()
)

# Load CSV
df = spark.read.csv(
    "data/ecommerce_sales_cleaned.csv",
    header=True,
    inferSchema=True
)

print("\n===== DATASET INFORMATION =====")
print("Rows:", df.count())
print("Columns:", len(df.columns))

print("\n===== COLUMN NAMES =====")
print(df.columns)

print("\n===== DATA TYPES =====")
df.printSchema()

print("\n===== FIRST 10 RECORDS =====")
df.show(10)

spark.stop()