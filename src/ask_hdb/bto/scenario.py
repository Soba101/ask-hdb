"""Illustrative BTO purchase scenario: loan, upfront cost, and a modest sale-after-MOP picture. Not a forecast."""

import pandas as pd

from ask_hdb.rules import load_rules
from ask_hdb.rules._checks import RuleUse
from ask_hdb.rules.bto import BTO_FILE

NOTE = ("Illustrative, from past growth, not a forecast. Starts from the launch price, ignores the resale premium "
        "of a finished flat, renovation, agent fees and loan interest already paid in CPF.")
ROOM = {"2-room Flexi": "2 ROOM", "3-room": "3 ROOM", "4-room": "4 ROOM", "5-room": "5 ROOM"}
MIN_GROWTH_YEARS = 5
GROWTH_CAP = 0.03  # our own conservative ceiling on every scenario: the 2021-23 run-up would overpromise


def instalment(principal: float, annual_rate_pct: float, years: int) -> float:
    n, r = years * 12, annual_rate_pct / 100 / 12
    return principal / n if r == 0 else principal * r / (1 - (1 + r) ** -n)


def balance(principal: float, annual_rate_pct: float, years: int, months_paid: int) -> float:
    n, r = years * 12, annual_rate_pct / 100 / 12
    months_paid = min(months_paid, n)
    if r == 0:
        return principal * (1 - months_paid / n)
    return principal * ((1 + r) ** n - (1 + r) ** months_paid) / ((1 + r) ** n - 1)


def past_growth(sales: pd.DataFrame, town: str, room: str) -> dict | None:
    """Year-on-year growth of the yearly median resale price (complete years only); None if the history is too short."""
    rows = sales[(sales.town == town.upper()) & (sales.flat_type == room)]
    year = rows.sale_month.dt.year
    medians = rows.groupby(year).resale_price.median()
    medians = medians[medians.index < sales.sale_month.max().year]  # drop the partial latest year
    growth = medians.pct_change().dropna()
    if len(growth) < MIN_GROWTH_YEARS:
        return None
    return {"low": max(0.0, float(growth.quantile(.25))), "median": max(0.0, float(growth.median())),
            "years": f"{medians.index.min()}-{medians.index.max()}", "n_years": len(growth)}


def bto_scenario(sales, price, grants, loan_kind, interest_rate_pct, loan_years, category,
                 town=None, flat_type=None) -> dict:
    use = RuleUse(load_rules(BTO_FILE))
    ltv = use.get(f"loan.{'hdb' if loan_kind == 'hdb' else 'bank'}_ltv")
    mop = use.get(f"mop.{'plus_prime_years' if category in {'Plus', 'Prime'} else 'standard_years'}")
    loan = ltv * price
    payment = instalment(loan, interest_rate_pct, loan_years)
    out = {"purchase_price": price, "grants": grants, "loan_kind": loan_kind, "loan_amount": round(loan),
           "interest_rate_pct": interest_rate_pct, "loan_years": loan_years,
           "monthly_instalment": round(payment), "upfront_needed_cash_or_cpf": round(max(0.0, price - loan - grants)),
           "mop_years": mop, "rules": use.result.rules, "note": NOTE,
           "needs_check": ["cpf_refund_and_accrued_interest_on_sale", "grant_refund_on_sale"], "scenarios": []}
    if category in {"Plus", "Prime"}:
        out["needs_check"].append("plus_prime_subsidy_recovery")
    growth = past_growth(sales, town, ROOM[flat_type]) if town and flat_type in ROOM else None
    if growth is None:
        out["needs_check"].append("growth_history_for_town_and_flat_type")
        return out
    out["growth_basis"] = (f"{town.upper()} {ROOM[flat_type]} yearly median resale prices {growth['years']}, "
                           f"{growth['n_years']} year-on-year changes; rates floored at 0 and capped at 3% a year (past low {growth['low'] * 100:.1f}%, past median {growth['median'] * 100:.1f}%)")
    left = balance(loan, interest_rate_pct, loan_years, mop * 12)
    for name, rate in (("flat", 0.0), ("low past growth (headline)", min(growth["low"], GROWTH_CAP)), ("median past growth", min(growth["median"], GROWTH_CAP))):
        sale = price * (1 + rate) ** mop
        out["scenarios"].append({"name": name, "annual_growth_pct": round(rate * 100, 1), "sale_price": round(sale),
                                 "loan_balance_at_sale": round(left),
                                 "cash_before_cpf_refund": round(sale - left)})
    return out
