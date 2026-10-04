"""
Part 2, Task 11 - the two charts.
Run after clean_and_eda.py:  python analysis/visualize.py
It rebuilds the cleaned data from the raw CSVs so the charts always match the analysis.
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "visualizations")
os.makedirs(OUT, exist_ok=True)

customers = pd.read_csv(os.path.join(DATA, "customers.csv"))
products = pd.read_csv(os.path.join(DATA, "products.csv"))
orders = pd.read_csv(os.path.join(DATA, "orders.csv"))

# same cleaning steps as clean_and_eda.py
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
dup_cols = ["customer_id", "product_id", "order_date", "quantity",
            "discount_pct", "payment_method", "rating", "returned"]
orders = orders[~orders.duplicated(subset=dup_cols, keep="first")].copy()
orders["discount_pct"] = orders["discount_pct"].fillna(0)
orders["rating"] = orders["rating"].fillna(orders["rating"].median())

df = orders.merge(products, on="product_id").merge(customers, on="customer_id")
df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100)

q1, q3 = df["quantity"].quantile(0.25), df["quantity"].quantile(0.75)
iqr = q3 - q1
df["is_outlier"] = (df["quantity"] < q1 - 1.5 * iqr) | (df["quantity"] > q3 + 1.5 * iqr)

# ---------- chart 1: return rate by payment method ----------
rate = (df.groupby("payment_method")["returned"].mean() * 100).round(1)
rate = rate.sort_values(ascending=False)
ratio = rate["COD"] / rate["CARD"]

fig, ax = plt.subplots(figsize=(7, 5))
bars = ax.bar(rate.index, rate.values, color=["#d9534f", "#f0ad4e", "#5bc0de"])
for b, v in zip(bars, rate.values):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v}%", ha="center", fontsize=11)
ax.set_title(f"COD Returns at {rate['COD']}% - {ratio:.0f}x Card")
ax.set_xlabel("Payment method")
ax.set_ylabel("Return rate (%)")
ax.set_ylim(0, rate.max() + 8)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "return_rate_by_payment.png"), dpi=150)
plt.close()

# ---------- chart 2: monthly revenue without the outliers ----------
df["order_date"] = pd.to_datetime(df["order_date"])
df["month"] = df["order_date"].dt.to_period("M")
monthly = df[~df["is_outlier"]].groupby("month")["order_value"].sum()
peak = monthly.idxmax()
peak_name = peak.to_timestamp().strftime("%B %Y")

fig, ax = plt.subplots(figsize=(8, 5))
x = [str(m) for m in monthly.index]
ax.plot(x, monthly.values, marker="o", color="#2a7f62")
ax.annotate(f"Rs {monthly[peak]:,.0f}", (str(peak), monthly[peak]),
            textcoords="offset points", xytext=(0, 10), ha="center")
ax.set_title(f"Monthly Revenue (outliers removed) - Peak in {peak_name}")
ax.set_xlabel("Month")
ax.set_ylabel("Revenue (Rs)")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "monthly_revenue_trend.png"), dpi=150)
plt.close()

print("Saved charts to", OUT)
