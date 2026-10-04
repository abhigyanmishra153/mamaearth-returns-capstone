"""
Part 3 - turns narrator/findings.json into a Situation / Complication / Resolution narrative.

Usage:
    python narrator/generate_narrative.py                 (no key, runs the offline template)
    GEMINI_API_KEY=your_key python narrator/generate_narrative.py   (uses Gemini)
"""
import os
import json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS_PATH = os.path.join(BASE, "narrator", "findings.json")

MODEL_NAME = "gemini-3.8-flash"

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write the report in exactly three labeled sections: Situation, Complication, Resolution. "
    "Every number in your output must come from the findings supplied by the user and must "
    "appear with the same value. Do not invent any statistics, percentages or rupee figures. "
    "Keep it to about 250 words, in plain business language."
)


def load_findings(path=FINDINGS_PATH):
    with open(path) as f:
        return json.load(f)


def month_name(ym):
    names = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
    year, month = ym.split("-")
    return names[int(month) - 1]


def build_prompt(findings):
    """User prompt, every number comes from the findings dict."""
    rr = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    infl = findings["outlier_inflated_month"]
    return (
        "Write the Situation-Complication-Resolution narrative using only these verified findings.\n\n"
        f"- Cleaned total revenue: Rs {findings['cleaned_total_revenue_inr']:,.2f}\n"
        f"- Raw total revenue before cleaning: Rs {findings['raw_total_revenue_inr']:,.2f}\n"
        f"- Difference caused by removing duplicate orders: Rs {findings['duplicate_reconciliation_delta_inr']:,.2f}\n"
        "- Return rate by payment method: "
        + ", ".join(f"{k} {v}%" for k, v in rr.items()) + "\n"
        f"- Highest-risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities "
        f"with a return rate of {seg['return_rate_pct']}%\n"
        f"- True peak month: {month_name(peak['month'])} ({peak['month']}) with revenue of Rs {peak['revenue_inr']:,.2f}\n"
        f"- {month_name(infl['month'])} ({infl['month']}) looked like the peak at Rs {infl['apparent_revenue_inr']:,.2f} "
        f"but is only Rs {infl['corrected_revenue_inr']:,.2f} once two bulk orders are excluded\n"
    )


def generate_scr_narrative_offline(findings):
    """Fixed template, no network and no key needed."""
    rr = findings["return_rate_by_payment"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    infl = findings["outlier_inflated_month"]
    text = (
        "Situation\n"
        f"After cleaning the order data, total revenue stands at Rs {findings['cleaned_total_revenue_inr']:,.2f}. "
        f"The raw figure was Rs {findings['raw_total_revenue_inr']:,.2f}; the gap of "
        f"Rs {findings['duplicate_reconciliation_delta_inr']:,.2f} comes entirely from duplicate orders "
        f"that were submitted twice and removed. The real peak month is {month_name(peak['month'])}, "
        f"with Rs {peak['revenue_inr']:,.2f} in revenue. {month_name(infl['month'])} only looked higher "
        f"(Rs {infl['apparent_revenue_inr']:,.2f}) because of two unusually large bulk orders; without them "
        f"it was Rs {infl['corrected_revenue_inr']:,.2f}.\n\n"
        "Complication\n"
        f"Returns are not spread evenly. Cash on Delivery orders are returned at {rr['COD']}%, compared "
        f"with {rr['CARD']}% for card and {rr['UPI']}% for UPI. The problem is worst for "
        f"{seg['payment_method']} orders in Tier-{seg['city_tier']} cities, where the return rate reaches "
        f"{seg['return_rate_pct']}%. Discounts do not explain it, so cutting or raising offers is unlikely "
        f"to fix this.\n\n"
        "Resolution\n"
        f"Regional ops should focus first on {seg['payment_method']} in Tier-{seg['city_tier']} cities, for example "
        "by confirming orders before dispatch or nudging customers towards prepaid payment. Finance should "
        f"plan from the corrected revenue base of Rs {findings['cleaned_total_revenue_inr']:,.2f} and treat "
        f"{month_name(peak['month'])} as the benchmark month, not {month_name(infl['month'])}. "
        "The order system should also block double submissions so duplicates stop inflating reported sales."
    )
    return {"status": "success", "narrative": text, "tokens": None}


def generate_scr_narrative(findings):
    """Calls Gemini. Falls back to the offline template if there is no API key."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return generate_scr_narrative_offline(findings)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        prompt = build_prompt(findings)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                # temperature 0 because this is a factual business report,
                # we want the same wording and the same numbers every time
                temperature=0.0,
                max_output_tokens=1000,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=30000),  # milliseconds = 30 s
            ),
        )
        tokens = None
        if response.usage_metadata is not None:
            tokens = response.usage_metadata.total_token_count
        return {"status": "success", "narrative": response.text, "tokens": tokens}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}


def check_figures(narrative):
    """Checks that the five required figures appear in the narrative."""
    text = narrative.replace(",", "")
    checks = [
        ("Cleaned total revenue 97,358.30", "97358.3" in text),
        ("COD return rate 44.4", "44.4" in text),
        ("Highest-risk segment rate 54.5", "54.5" in text),
        ("Duplicate delta 2,501.90", "2501.9" in text),
        ("Peak month March with 20,318.90", "March" in text and "20318.9" in text),
    ]
    all_ok = True
    for label, ok in checks:
        print(("PASS" if ok else "FAIL") + " - " + label)
        all_ok = all_ok and ok
    return all_ok


def main():
    findings = load_findings()
    result = generate_scr_narrative(findings)
    used_api = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))

    if result["status"] == "error":
        print("Gemini call failed:", result["message"])
        print("Using the offline template instead.\n")
        result = generate_scr_narrative_offline(findings)
        used_api = False

    print(result["narrative"])
    print("\n--- figure check ---")
    ok = check_figures(result["narrative"])
    print("Overall:", "PASS" if ok else "FAIL")

    # only the Gemini output is saved, since that one can change from run to run
    if used_api:
        with open(os.path.join(BASE, "narrator", "sample_output.txt"), "w", encoding="utf-8") as f:
            f.write(result["narrative"])
        print("Saved narrator/sample_output.txt")


if __name__ == "__main__":
    main()
