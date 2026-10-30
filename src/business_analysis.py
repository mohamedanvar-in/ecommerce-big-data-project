import pandas as pd

# Load dataset
df = pd.read_csv("data/ecommerce_sales.csv")

# Convert Order_Date to datetime
df["Order_Date"] = pd.to_datetime(df["Order_Date"])

print("===== 1. TOTAL REVENUE =====")

total_revenue = df["Total_Sales"].sum()

print(f"Total Revenue: ₹{total_revenue:,.2f}")


print("\n===== 2. TOTAL ORDERS =====")

total_orders = df["Order_ID"].nunique()

print(f"Total Orders: {total_orders}")


print("\n===== 3. TOTAL QUANTITY SOLD =====")

total_quantity = df["Quantity"].sum()

print(f"Total Quantity Sold: {total_quantity}")


print("\n===== 4. TOP PRODUCTS BY REVENUE =====")

product_sales = (
    df.groupby("Product")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

print(product_sales)


print("\n===== 5. SALES BY CATEGORY =====")

category_sales = (
    df.groupby("Category")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

print(category_sales)


print("\n===== 6. SALES BY CITY =====")

city_sales = (
    df.groupby("City")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

print(city_sales)


print("\n===== 7. SALES BY PAYMENT METHOD =====")

payment_sales = (
    df.groupby("Payment_Method")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

print(payment_sales)


print("\n===== 8. MONTHLY SALES =====")

monthly_sales = (
    df.groupby(df["Order_Date"].dt.month)["Total_Sales"]
    .sum()
)

print(monthly_sales)