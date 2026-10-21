"""Compute and verify the expected answers of the scenario questions (kind: scenario).

Independent of ask_hdb.bto.scenario: loans are amortised month by month in a loop (no closed form), and growth comes from plain
pandas on data/clean/resale.parquet (shared input). Rules used: HDB loan limit 75% and MOP 5 years (Standard) or 10 (Plus/Prime),
as in rules/bto/2026-10.yaml. The 3% growth cap is the project's own conservative choice (docs/week4b-plan.md).
"""

from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
LTV, CAP = 0.75, 0.03


def amortise(principal, rate_pct, years, months):
    """(monthly payment, balance after `months` payments), by stepping month by month."""
    r, n = rate_pct / 1200, years * 12
    pay = principal / n if r == 0 else principal * r / (1 - (1 + r) ** -n)
    bal = principal
    for _ in range(months):
        bal = bal * (1 + r) - pay
    return pay, bal


def low_growth(sales, town, flat_type):
    rows = sales[(sales.town == town) & (sales.flat_type == flat_type)].copy()
    rows["y"] = rows.sale_month.dt.year
    yearly = rows[rows.y < sales.sale_month.dt.year.max()].groupby("y").resale_price.median().sort_index()
    changes = [yearly.iloc[i] / yearly.iloc[i - 1] - 1 for i in range(1, len(yearly))]
    changes.sort()
    k = (len(changes) - 1) * 0.25  # linear-interpolated 25th percentile
    lo = int(k)
    return changes[lo] + (changes[min(lo + 1, len(changes) - 1)] - changes[lo]) * (k - lo)


def expected(spec, sales):
    op, price = spec["operation"], spec["price"]
    loan = LTV * price
    mop = 10 if spec.get("category") in {"Plus", "Prime"} else 5
    if op == "instalment":
        return round(amortise(loan, spec["rate_pct"], spec["years"], 0)[0])
    if op == "loan_amount":
        return round(loan)
    if op == "upfront":
        return round(max(0, price - loan - spec["grants"]))
    _, bal = amortise(loan, spec["rate_pct"], spec["years"], mop * 12)
    if op == "balance_at_mop":
        return round(bal)
    if op == "flat_cash":
        return round(price - bal, -3)
    rate = min(max(low_growth(sales, spec["town"], spec["flat_type"]), 0), CAP)
    return round(price * (1 + rate) ** mop, -3)  # headline sale price


def main():
    questions = [q for q in yaml.safe_load((ROOT / "eval/questions.yaml").read_text()) if q["kind"] == "scenario"]
    sales = pd.read_parquet(ROOT / "data/clean/resale.parquet")
    bad = [f"{q['id']}: stored {q['expect']['number']}, want {expected(q['query'], sales)}"
           for q in questions if abs(expected(q["query"], sales) - q["expect"]["number"]) > 0.5]
    if bad:
        raise SystemExit("\n".join(bad))
    print(f"Verified {len(questions)} scenario answers")


if __name__ == "__main__":
    main()
