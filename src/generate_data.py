import pandas as pd
import numpy as np

# For reproducible data
np.random.seed(42)

# Number of records
num_records = 50000

# Product information
products = {
    "Laptop": ("Electronics", 55000),
    "Smartphone": ("Electronics", 25000),
    "Headphones": ("Electronics", 2500),
    "T-Shirt": ("Fashion", 799),
    "Jeans": ("Fashion", 1499),
    "Shoes": ("Fashion", 2499),
    "Backpack": ("Accessories", 1299),
    "Watch": ("Accessories", 3999),
    "Coffee Maker": ("Home Appliances", 4999),
    "Mixer": ("Home Appliances", 2999),
}

cities = [
    "Chennai",
    "Bangalore",
    "Hyderabad",
    "Mumbai",
    "Delhi",
    "Pune",
    "Coimbatore",
    "Madurai",
]

payment_methods = [
    "UPI",
    "Credit Card",
    "Debit Card",
    "Cash on Delivery",
]

product_names = np.random.choice(
    list(products.keys()),
    num_records
)

data = []

for i in range(num_records):
    product = product_names[i]
    category, price = products[product]

    quantity = np.random.randint(1, 5)

    data.append({
        "Order_ID": f"ORD{i+1:06d}",
        "Order_Date": pd.Timestamp("2025-01-01") +
                      pd.to_timedelta(
                          np.random.randint(0, 365),
                          unit="D"
                      ),
        "Customer_ID": f"CUST{np.random.randint(1, 10001):05d}",
        "Product": product,
        "Category": category,
        "Price": price,
        "Quantity": quantity,
        "City": np.random.choice(cities),
        "Payment_Method": np.random.choice(payment_methods),
    })

# Create DataFrame
df = pd.DataFrame(data)

# Calculate total sales
df["Total_Sales"] = df["Price"] * df["Quantity"]

# Save dataset
df.to_csv(
    "data/ecommerce_sales.csv",
    index=False
)

print("Dataset created successfully!")
print(f"Total records: {len(df)}")
print("\nFirst 5 records:")
print(df.head())