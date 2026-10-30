import pandas as pd

# Load raw dataset
df = pd.read_csv("data/ecommerce_sales.csv")

print("===== BEFORE CLEANING =====")
print("Rows:", len(df))
print("Columns:", len(df.columns))

# 1. Convert date column
df["Order_Date"] = pd.to_datetime(
    df["Order_Date"],
    errors="coerce"
)

# 2. Check missing values
print("\n===== MISSING VALUES =====")
print(df.isnull().sum())

# 3. Check duplicate orders
duplicate_orders = df["Order_ID"].duplicated().sum()

print("\n===== DUPLICATE ORDERS =====")
print("Duplicate Order IDs:", duplicate_orders)

# 4. Check invalid quantities
invalid_quantity = (df["Quantity"] <= 0).sum()

print("\n===== INVALID QUANTITY =====")
print("Invalid quantities:", invalid_quantity)

# 5. Check invalid prices
invalid_price = (df["Price"] <= 0).sum()

print("\n===== INVALID PRICE =====")
print("Invalid prices:", invalid_price)

# 6. Recalculate Total_Sales
df["Calculated_Total"] = df["Price"] * df["Quantity"]

# Check whether stored Total_Sales is correct
incorrect_total = (
    df["Total_Sales"] != df["Calculated_Total"]
).sum()

print("\n===== SALES CALCULATION CHECK =====")
print("Incorrect totals:", incorrect_total)

# Remove helper column
df.drop(columns=["Calculated_Total"], inplace=True)

# 7. Sort by date
df = df.sort_values("Order_Date")

# 8. Reset index
df = df.reset_index(drop=True)

# Save cleaned data
df.to_csv(
    "data/ecommerce_sales_cleaned.csv",
    index=False
)

print("\n===== AFTER CLEANING =====")
print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\nCleaned dataset saved successfully!")