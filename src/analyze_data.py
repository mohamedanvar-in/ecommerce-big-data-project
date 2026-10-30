import pandas as pd

# Load dataset
df = pd.read_csv("data/ecommerce_sales.csv")

print("===== DATASET INFORMATION =====")
print("Rows:", len(df))
print("Columns:", len(df.columns))

print("\n===== COLUMN NAMES =====")
print(df.columns.tolist())

print("\n===== FIRST 5 ROWS =====")
print(df.head())

print("\n===== DATA TYPES =====")
print(df.dtypes)

print("\n===== MISSING VALUES =====")
print(df.isnull().sum())

print("\n===== BASIC STATISTICS =====")
print(df.describe())