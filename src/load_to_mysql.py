import pandas as pd
import mysql.connector

# Load cleaned CSV
df = pd.read_csv("data/ecommerce_sales_cleaned.csv")

print("CSV loaded successfully!")
print("Records:", len(df))

# Connect to MySQL
connection = mysql.connector.connect(
    host="localhost",
    user="root",
    password="anvar",
    database="ecommerce_db"
)

cursor = connection.cursor()

print("Connected to MySQL successfully!")

# Insert query
insert_query = """
INSERT INTO ecommerce_sales
(
    Order_ID,
    Order_Date,
    Customer_ID,
    Product,
    Category,
    Price,
    Quantity,
    City,
    Payment_Method,
    Total_Sales
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

data = [
    (
        row.Order_ID,
        row.Order_Date,
        row.Customer_ID,
        row.Product,
        row.Category,
        row.Price,
        row.Quantity,
        row.City,
        row.Payment_Method,
        row.Total_Sales
    )
    for row in df.itertuples(index=False)
]

cursor.executemany(insert_query, data)

connection.commit()

print("Data inserted successfully!")
print("Rows inserted:", cursor.rowcount)

cursor.close()
connection.close()

print("MySQL connection closed.")