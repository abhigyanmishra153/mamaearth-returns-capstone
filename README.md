# Mamaearth Returns & Growth Intelligence Pipeline

Capstone project - Data Analytics with AI & Gen AI, E&ICT Academy IIT Roorkee.

The growth team suspected that returns were eating into margins. This repo checks that end to end:
a SQL layer for the order data, a pandas layer that cleans it and finds where returns come from,
and a narrator layer that turns the verified numbers into a short business report.

## Repo structure

```
README.md
sql/
    schema.sql          creates the 3 tables
    seed_data.sql       loads the CSVs into them (INSERT statements)
    reports.sql         9 report queries, output pasted above each one
data/
    customers.csv       45 rows
    products.csv        16 rows
    orders.csv          180 rows (raw, never edited)
analysis/
    clean_and_eda.py    cleaning + EDA, also writes narrator/findings.json
    visualize.py        makes the two charts
visualizations/
    return_rate_by_payment.png
    monthly_revenue_trend.png
narrator/
    findings.json       numbers exported by clean_and_eda.py
    generate_narrative.py
    sample_output.txt   saved Gemini output (see step 3)
```

## How the three layers connect

1. **SQL layer** loads the raw CSVs into SQLite and gives the raw numbers (for example the raw revenue of 99,860.20).
2. **Analysis layer** reads the same raw CSVs with pandas (not the database), cleans them, and finds the real patterns.
   It reconciles its cleaned revenue against the SQL raw revenue, and the 2,501.90 difference is the 5 duplicate orders.
3. **Narrator layer** reads `narrator/findings.json`, which the analysis layer wrote, and writes the
   Situation / Complication / Resolution report from those numbers only.

Order of running: SQL -> analysis -> narrator. Part 1 and Part 2 are independent of each other,
but Part 3 needs `findings.json`, so Part 2 has to be run before it.

## Requirements

Python 3.10+ and SQLite.

```
pip install pandas numpy matplotlib google-genai
```

`google-genai` is only needed for the Gemini path. The offline path works without it.

## Step 1 - SQL layer

From the repo root:

```
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

`seed_data.sql` ends with three COUNT queries, which should print 45, 16 and 180.
Report (i) in `reports.sql` uses ALTER TABLE, so to run `reports.sql` a second time,
run `schema.sql` and `seed_data.sql` again first (schema.sql drops and recreates the tables).

## Step 2 - Analysis layer

```
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` prints the result of every task (shapes, cleaning counts, reconciliation,
outliers, hypotheses, correlation, monthly revenue). Its last step writes `narrator/findings.json`,
so that file is never typed by hand. `visualize.py` rebuilds the cleaned data from the raw CSVs
and saves both charts into `visualizations/`.

## Step 3 - Narrator layer

Without any API key (offline template, nothing to configure):

```
python narrator/generate_narrative.py
```

With a Gemini API key (free key from Google AI Studio):

```
export GEMINI_API_KEY="your_key_here"        # Windows PowerShell: $env:GEMINI_API_KEY="your_key_here"
python narrator/generate_narrative.py
```

If the key is set, the script calls Gemini and saves the answer to `narrator/sample_output.txt`.
If there is no key, or the API call fails, it falls back to the offline template automatically.
Either way it runs a check that the five required figures are in the text
(97,358.30 / 44.4 / 54.5 / 2,501.90 / March with 20,318.90) and prints PASS or FAIL for each.

## Key results

| Item | Value |
|---|---|
| Raw revenue (SQL) | Rs 99,860.20 |
| Cleaned revenue (pandas) | Rs 97,358.30 |
| Difference | Rs 2,501.90 (5 duplicate orders) |
| Return rate COD / UPI / Card | 44.4% / 18.9% / 14.7% |
| Highest-risk segment | COD in Tier-2 cities, 54.5% |
| True peak month | March 2026, Rs 20,318.90 (January only looked higher because of 2 bulk orders) |
