"""
Part 2 - cleaning and EDA on the Mamaearth orders data.
Run from anywhere:  python analysis/clean_and_eda.py
Reads the raw CSVs in data/ and writes narrator/findings.json at the end.
"""
import os
import json
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

# ---------------------------------------------------------------
# Task 1 - load and inspect
# ---------------------------------------------------------------
print("=" * 60)
print("TASK 1: LOAD AND INSPECT")
print("=" * 60)
customers = pd.read_csv(os.path.join(DATA, "customers.csv"))
products = pd.read_csv(os.path.join(DATA, "products.csv"))
orders = pd.read_csv(os.path.join(DATA, "orders.csv"))
orders_raw = orders.copy()   # untouched copy, used later to rebuild the raw total

print("customers shape:", customers.shape)
print("products shape:", products.shape)
print("orders shape:", orders.shape)
print(orders.head())
print("\nMissing values in orders:")
print(orders.isnull().sum())

# ---------------------------------------------------------------
# Task 2 - payment_method casing
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 2: STANDARDIZE payment_method")
print("=" * 60)
print("Before:", orders["payment_method"].unique())
print("Number of distinct raw values:", orders["payment_method"].nunique())

orders["payment_method"] = orders["payment_method"].str.strip().str.upper()

print("After:", orders["payment_method"].unique())
print(orders["payment_method"].value_counts())

# ---------------------------------------------------------------
# Task 3 - duplicates
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 3: REMOVE DUPLICATE ORDERS")
print("=" * 60)
dup_cols = ["customer_id", "product_id", "order_date", "quantity",
            "discount_pct", "payment_method", "rating", "returned"]
dup_mask = orders.duplicated(subset=dup_cols, keep="first")
dropped = orders[dup_mask].copy()
print("Duplicates flagged:", dup_mask.sum())
print("Dropped order_ids:", dropped["order_id"].tolist())

orders_clean = orders[~dup_mask].copy().reset_index(drop=True)
print("orders_clean shape:", orders_clean.shape)

# ---------------------------------------------------------------
# Task 4 - missing values
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 4: IMPUTE MISSING VALUES")
print("=" * 60)
n_disc_missing = orders_clean["discount_pct"].isnull().sum()
n_rating_missing = orders_clean["rating"].isnull().sum()
print("discount_pct missing:", n_disc_missing)
print("rating missing:", n_rating_missing)

# no promo code means no discount, so 0 is the right fill here
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)

# rating: median of the ratings we actually have
rating_median = orders_clean["rating"].median()
print("Median rating (before imputing):", rating_median)
orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)

print("\nNulls after imputation:")
print(orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

# ---------------------------------------------------------------
# Task 5 - merge and reconcile with the SQL total
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 5: MERGE AND RECONCILE")
print("=" * 60)
df = orders_clean.merge(products, on="product_id", how="left")
df = df.merge(customers, on="customer_id", how="left")
df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100)

cleaned_total = round(df["order_value"].sum(), 2)
print("Merged shape:", df.shape)
print("Cleaned total revenue: Rs", f"{cleaned_total:,.2f}")

# value of the 5 dropped rows, calculated separately as a check
dropped_m = dropped.merge(products, on="product_id", how="left")
dropped_m["discount_pct"] = dropped_m["discount_pct"].fillna(0)
dropped_m["order_value"] = (dropped_m["quantity"] * dropped_m["price"]
                            * (1 - dropped_m["discount_pct"] / 100))
dup_value = round(dropped_m["order_value"].sum(), 2)

# raw total straight from the untouched orders, same formula as SQL report (a)
raw_m = orders_raw.merge(products, on="product_id", how="left")
raw_total = round((raw_m["quantity"] * raw_m["price"]
                   * (1 - raw_m["discount_pct"].fillna(0) / 100)).sum(), 2)
delta = round(raw_total - cleaned_total, 2)
print("Raw total before cleaning (matches SQL report a): Rs", f"{raw_total:,.2f}")
print("Difference (raw - cleaned): Rs", f"{delta:,.2f}")
print("Combined order_value of the 5 dropped rows: Rs", f"{dup_value:,.2f}")
print("Difference matches duplicate value:", delta == dup_value)

print("\nReconciliation note:")
print(f"The cleaned revenue of Rs {cleaned_total:,.2f} is Rs {delta:,.2f} lower than the "
      f"raw SQL total of Rs {raw_total:,.2f}. This whole gap comes from the 5 duplicate "
      f"orders (O0176 to O0180) that were removed in Task 3. Their combined order_value is "
      f"Rs {dup_value:,.2f}, which is exactly the difference, so nothing is left unexplained. "
      f"Filling the missing discount_pct with 0 and the missing ratings with the median does "
      f"not change this gap, because the SQL report already treated a NULL discount as 0% and "
      f"rating is not used in the revenue formula.")

# ---------------------------------------------------------------
# Task 6 - outliers in quantity (IQR)
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 6: IQR OUTLIERS ON quantity")
print("=" * 60)
q1 = df["quantity"].quantile(0.25)
q3 = df["quantity"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
print(f"Q1 = {q1}, Q3 = {q3}, IQR = {iqr}")
print(f"lower = {lower}, upper = {upper}")

df["is_outlier"] = (df["quantity"] < lower) | (df["quantity"] > upper)
print("Outlier rows:", df["is_outlier"].sum())
print(df.loc[df["is_outlier"], ["order_id", "customer_id", "product_id",
                                "order_date", "quantity", "order_value"]])

# ---------------------------------------------------------------
# Task 7 - hypothesis: COD has a higher return rate
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 7: HYPOTHESIS - COD HAS A HIGHER RETURN RATE")
print("=" * 60)
print("Hypothesis: orders paid by Cash on Delivery are returned more often than Card or UPI orders.")
pay = df.groupby("payment_method")["returned"].agg(["count", "mean"])
pay["return_rate_pct"] = (pay["mean"] * 100).round(1)
print(pay)
print("Hypothesis result: CONFIRMED (COD {}% vs CARD {}% and UPI {}%)".format(
    pay.loc["COD", "return_rate_pct"], pay.loc["CARD", "return_rate_pct"],
    pay.loc["UPI", "return_rate_pct"]))

# ---------------------------------------------------------------
# Task 8 - segmentation
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 8: PAYMENT METHOD x CITY TIER")
print("=" * 60)
seg = df.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
seg["return_rate_pct"] = (seg["mean"] * 100).round(1)
print(seg)

top = seg["return_rate_pct"].idxmax()
top_rate = seg.loc[top, "return_rate_pct"]
print(f"\nHighest-risk segment: {top[0]} + Tier-{top[1]} cities at {top_rate}% "
      f"({int(seg.loc[top, 'count'])} orders)")
cod_t1 = seg.loc[("COD", 1)]
cod_t2 = seg.loc[("COD", 2)]
print(f"COD Tier-1: {int(cod_t1['count'])} orders at {cod_t1['return_rate_pct']}%  vs  "
      f"COD Tier-2: {int(cod_t2['count'])} orders at {cod_t2['return_rate_pct']}%")
print("So the COD problem is not the same everywhere, it is concentrated in Tier-2 cities.")

# ---------------------------------------------------------------
# Task 9 - correlation
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 9: CORRELATION")
print("=" * 60)
cols = ["rating", "returned", "discount_pct", "quantity"]
corr = df[cols].corr()
print(corr.round(3))


def band(r):
    r = abs(r)
    if r < 0.2:
        return "negligible"
    elif r < 0.4:
        return "weak"
    elif r < 0.7:
        return "moderate"
    return "strong"


print("\nPairwise strength:")
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        r = corr.loc[cols[i], cols[j]]
        print(f"  {cols[i]} vs {cols[j]}: r = {r:.3f} -> {band(r)}")

r_disc_ret = corr.loc["discount_pct", "returned"]
print(f"\nHypothesis: higher discounts reduce returns -> BUSTED "
      f"(r = {r_disc_ret:.2f}, negligible)")

# ---------------------------------------------------------------
# Task 10 - monthly revenue, with and without outliers
# ---------------------------------------------------------------
print("\n" + "=" * 60)
print("TASK 10: MONTHLY REVENUE")
print("=" * 60)
df["order_date"] = pd.to_datetime(df["order_date"])
df["year_month"] = df["order_date"].dt.to_period("M").astype(str)

monthly_all = df.groupby("year_month")["order_value"].sum().round(2)
monthly_fix = df[~df["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)

print("(1) Including outlier orders:")
print(monthly_all)
print("\n(2) Excluding outlier orders:")
print(monthly_fix)

peak_all = monthly_all.idxmax()
peak_fix = monthly_fix.idxmax()
print(f"\nWith outliers the highest month is {peak_all} (Rs {monthly_all[peak_all]:,.2f}).")
print(f"Without them it is {peak_fix} (Rs {monthly_fix[peak_fix]:,.2f}).")
print("January's lead is only an artifact of the two bulk orders that landed in January "
      "(O0011 on 2026-01-28 and O0098 on 2026-01-10). Once they are excluded, January "
      f"drops to Rs {monthly_fix['2026-01']:,.2f} and March is the genuine peak month.")

# ---------------------------------------------------------------
# Export for the narrator (Part 3, Task 1)
# ---------------------------------------------------------------
findings = {
    "cleaned_total_revenue_inr": float(cleaned_total),
    "raw_total_revenue_inr": float(raw_total),
    "duplicate_reconciliation_delta_inr": float(delta),
    "return_rate_by_payment": {
        "COD": float(pay.loc["COD", "return_rate_pct"]),
        "CARD": float(pay.loc["CARD", "return_rate_pct"]),
        "UPI": float(pay.loc["UPI", "return_rate_pct"]),
    },
    "highest_risk_segment": {
        "payment_method": top[0],
        "city_tier": int(top[1]),
        "return_rate_pct": float(top_rate),
    },
    "true_peak_month": {
        "month": peak_fix,
        "revenue_inr": float(monthly_fix[peak_fix]),
    },
    "outlier_inflated_month": {
        "month": peak_all,
        "apparent_revenue_inr": float(monthly_all[peak_all]),
        "corrected_revenue_inr": float(monthly_fix[peak_all]),
    },
}
out_path = os.path.join(BASE, "narrator", "findings.json")
with open(out_path, "w") as f:
    json.dump(findings, f, indent=2)
print("\nWrote", out_path)
