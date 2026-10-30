from pyspark.sql import SparkSession
from pyspark.sql.functions import sum, desc, month, row_number, rank
from pyspark.sql.window import Window
import os
import pandas as pd


# =========================================================
# 1. START SPARK
# =========================================================

spark = (
    SparkSession.builder
    .appName("EcommerceBigDataAnalysis")
    .master("local[*]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# =========================================================
# 2. LOAD CLEANED DATASET
# =========================================================

df = spark.read.csv(
    "data/ecommerce_sales_cleaned.csv",
    header=True,
    inferSchema=True
)


# =========================================================
# 3. DATASET INFORMATION
# =========================================================

print("\n========================================")
print("        DATASET INFORMATION")
print("========================================")

print("Rows:", df.count())
print("Columns:", len(df.columns))

print("\nColumn Names:")
print(df.columns)

print("\nData Types:")
df.printSchema()


# =========================================================
# 4. FIRST 10 RECORDS
# =========================================================

print("\n========================================")
print("        FIRST 10 RECORDS")
print("========================================")

df.show(10, truncate=False)


# =========================================================
# 5. TOTAL REVENUE
# =========================================================

total_revenue = df.agg(
    sum("Total_Sales").alias("Total_Revenue")
)

print("\n========================================")
print("        TOTAL REVENUE")
print("========================================")

total_revenue.show()


# =========================================================
# 6. REVENUE BY PRODUCT
# =========================================================

product_sales = (
    df.groupBy("Product")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
      .orderBy(desc("Total_Revenue"))
)

print("\n========================================")
print("        REVENUE BY PRODUCT")
print("========================================")

product_sales.show(truncate=False)


# =========================================================
# 7. REVENUE BY CATEGORY
# =========================================================

category_sales = (
    df.groupBy("Category")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
      .orderBy(desc("Total_Revenue"))
)

print("\n========================================")
print("        SALES BY CATEGORY")
print("========================================")

category_sales.show(truncate=False)


# =========================================================
# 8. REVENUE BY CITY
# =========================================================

city_sales = (
    df.groupBy("City")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
      .orderBy(desc("Total_Revenue"))
)

print("\n========================================")
print("        SALES BY CITY")
print("========================================")

city_sales.show(truncate=False)


# =========================================================
# 9. REVENUE BY PAYMENT METHOD
# =========================================================

payment_sales = (
    df.groupBy("Payment_Method")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
      .orderBy(desc("Total_Revenue"))
)

print("\n========================================")
print("        SALES BY PAYMENT METHOD")
print("========================================")

payment_sales.show(truncate=False)


# =========================================================
# 10. MONTHLY SALES
# =========================================================

monthly_sales = (
    df.withColumn("Month", month("Order_Date"))
      .groupBy("Month")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
      .orderBy("Month")
)

print("\n========================================")
print("        MONTHLY SALES")
print("========================================")

monthly_sales.show(12)


# =========================================================
# 11. PRODUCT REVENUE RANKING
# =========================================================

product_window = Window.orderBy(
    desc("Total_Revenue")
)

ranked_products = (
    product_sales
    .withColumn(
        "Rank",
        rank().over(product_window)
    )
    .orderBy("Rank")
)

print("\n========================================")
print("        PRODUCT REVENUE RANKING")
print("========================================")

ranked_products.show(truncate=False)


# =========================================================
# 12. TOP 3 PRODUCTS IN EACH CATEGORY
# =========================================================

category_product_sales = (
    df.groupBy("Category", "Product")
      .agg(
          sum("Total_Sales").alias("Total_Revenue")
      )
)

category_window = (
    Window
    .partitionBy("Category")
    .orderBy(desc("Total_Revenue"))
)

top_products_category = (
    category_product_sales
    .withColumn(
        "Rank",
        row_number().over(category_window)
    )
    .filter("Rank <= 3")
    .orderBy("Category", "Rank")
)

print("\n========================================")
print("        TOP 3 PRODUCTS BY CATEGORY")
print("========================================")

top_products_category.show(truncate=False)


# =========================================================
# 13. CREATE RESULTS FOLDER
# =========================================================

results_path = "data/spark_results"

os.makedirs(results_path, exist_ok=True)

print("\n========================================")
print("        SAVING SPARK RESULTS")
print("========================================")


# =========================================================
# 14. SAVE RESULTS USING PANDAS
# =========================================================

product_sales.toPandas().to_csv(
    f"{results_path}/product_sales.csv",
    index=False
)

print("Product sales saved.")


category_sales.toPandas().to_csv(
    f"{results_path}/category_sales.csv",
    index=False
)

print("Category sales saved.")


city_sales.toPandas().to_csv(
    f"{results_path}/city_sales.csv",
    index=False
)

print("City sales saved.")


payment_sales.toPandas().to_csv(
    f"{results_path}/payment_sales.csv",
    index=False
)

print("Payment method sales saved.")


monthly_sales.toPandas().to_csv(
    f"{results_path}/monthly_sales.csv",
    index=False
)

print("Monthly sales saved.")


ranked_products.toPandas().to_csv(
    f"{results_path}/product_ranking.csv",
    index=False
)

print("Product ranking saved.")


top_products_category.toPandas().to_csv(
    f"{results_path}/top_products_category.csv",
    index=False
)

print("Top products by category saved.")


# =========================================================
# 15. FINAL MESSAGE
# =========================================================

print("\n========================================")
print("        ALL RESULTS SAVED")
print("========================================")

print(f"Results location: {results_path}")

print("\nSaved files:")
print("1. product_sales.csv")
print("2. category_sales.csv")
print("3. city_sales.csv")
print("4. payment_sales.csv")
print("5. monthly_sales.csv")
print("6. product_ranking.csv")
print("7. top_products_category.csv")


# =========================================================
# 16. STOP SPARK
# =========================================================

spark.stop()

print("\n========================================")
print("        SPARK ANALYSIS COMPLETED")
print("========================================")