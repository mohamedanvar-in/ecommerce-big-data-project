import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv("data/ecommerce_sales.csv")

# Convert date
df["Order_Date"] = pd.to_datetime(df["Order_Date"])


# =========================
# 1. PRODUCT SALES
# =========================

product_sales = (
    df.groupby("Product")["Total_Sales"]
    .sum()
    .sort_values(ascending=True)
)

plt.figure(figsize=(10, 6))

product_sales.plot(kind="barh")

plt.title("Revenue by Product")
plt.xlabel("Revenue")
plt.ylabel("Product")

plt.tight_layout()
plt.show()


# =========================
# 2. CATEGORY SALES
# =========================

category_sales = (
    df.groupby("Category")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(8, 5))

category_sales.plot(kind="bar")

plt.title("Revenue by Category")
plt.xlabel("Category")
plt.ylabel("Revenue")

plt.xticks(rotation=0)

plt.tight_layout()
plt.show()


# =========================
# 3. CITY SALES
# =========================

city_sales = (
    df.groupby("City")["Total_Sales"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(10, 5))

city_sales.plot(kind="bar")

plt.title("Revenue by City")
plt.xlabel("City")
plt.ylabel("Revenue")

plt.xticks(rotation=45)

plt.tight_layout()
plt.show()


# =========================
# 4. MONTHLY SALES
# =========================

monthly_sales = (
    df.groupby(df["Order_Date"].dt.month)["Total_Sales"]
    .sum()
)

plt.figure(figsize=(10, 5))

monthly_sales.plot(kind="line", marker="o")

plt.title("Monthly Revenue")
plt.xlabel("Month")
plt.ylabel("Revenue")

plt.xticks(range(1, 13))

plt.grid(True)

plt.tight_layout()
plt.show()