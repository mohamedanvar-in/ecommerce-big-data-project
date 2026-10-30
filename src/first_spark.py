from pyspark.sql import SparkSession

# Create Spark session
spark = (
    SparkSession.builder
    .appName("EcommerceBigDataProject")
    .master("local[*]")
    .getOrCreate()
)

print("================================")
print("Spark started successfully!")
print("================================")

print("Spark version:", spark.version)

# Stop Spark
spark.stop()

print("================================")
print("Spark stopped successfully!")
print("================================")