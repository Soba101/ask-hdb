"""Illustrative BTO purchase scenario: loan, upfront cost, and a modest sale-after-MOP picture. Not a forecast."""

import pandas as pd

from ask_hdb.rules import load_rules
from ask_hdb.rules._checks import RuleUse
from ask_hdb.rules.bto import BTO_FILE

NOTE = ("Illustrative, from past growth, not a forecast. Starts from the launch price, ignores the resale premium "
        "of a finished flat, renovation, agent fees and loan interest already paid in CPF. Prices can also fall; "
        "no scenario is shown below flat.")
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
    return {"low": float(growth.quantile(.25)), "median": float(growth.median()),
            "years": f"{medians.index.min()}-{medians.index.max()}", "n_years": len(growth)}


def bto_scenario(sales, price, grants, loan_kind, category=None, interest_rate_pct=None, loan_years=None,
                 town=None, flat_type=None) -> dict:
    use = RuleUse(load_rules(BTO_FILE))
    ltv = use.get(f"loan.{'hdb' if loan_kind == 'hdb' else 'bank'}_ltv")
    mop = use.get(f"mop.{'plus_prime_years' if category in {'Plus', 'Prime'} else 'standard_years'}") if category else None
    loan = ltv * price
    known = interest_rate_pct is not None and loan_years is not None
    payment = instalment(loan, interest_rate_pct, loan_years) if known else None
    out = {"purchase_price": price, "grants": grants, "loan_kind": loan_kind, "ltv_pct": round(ltv * 100, 6),
           "loan_amount": round(loan),
           "interest_rate_pct": interest_rate_pct, "loan_years": loan_years,
           "monthly_instalment": round(payment) if known else None, "upfront_needed_cash_or_cpf": round(max(0.0, price - loan - grants)),
           "mop_years": mop, "rules": use.result.rules, "note": NOTE,
           "needs_check": ["cpf_refund_and_accrued_interest_on_sale", "grant_refund_on_sale",
                         "loan_amount_assumes_max_ltv_check_hle_msr_and_cpf_paid_in"], "scenarios": []}
    if loan_kind == "bank":
        out["needs_check"].append("bank_ltv_not_separately_confirmed")
    if category in {"Plus", "Prime"}:
        out["needs_check"].append("plus_prime_subsidy_recovery")
    if not known:
        out["needs_check"].append("interest_rate_and_loan_years_for_instalment_and_scenarios")
    if mop is None:
        out["needs_check"].append("category_for_mop_years_and_sale_scenarios")
    if not known or mop is None:
        return out
    growth = past_growth(sales, town, ROOM[flat_type]) if town and flat_type in ROOM else None
    if growth is None:
        out["needs_check"].append("growth_history_for_town_and_flat_type")
        return out
    out["growth_basis"] = (f"{town.upper()} {ROOM[flat_type]} yearly median resale prices {growth['years']}, "
                           f"{growth['n_years']} year-on-year changes; past low {growth['low'] * 100:.1f}%, past median "
                           f"{growth['median'] * 100:.1f}%; scenario rates are floored at 0 and capped at 3% a year")
    left = balance(loan, interest_rate_pct, loan_years, mop * 12)
    for name, raw in (("low past growth (headline)", growth["low"]), ("median past growth", growth["median"])):
        rate = min(max(raw, 0.0), GROWTH_CAP)
        if rate != raw:
            name += ", capped at 3%" if raw > GROWTH_CAP else ", floored at 0"
        out["scenarios"].append(_scenario(name, rate, price, mop, left))
    out["scenarios"].insert(0, _scenario("flat", 0.0, price, mop, left))
    return out


def _scenario(name, rate, price, mop, left):
    sale = price * (1 + rate) ** mop
    # Rounded to $1,000 so it does not read as an exact future price.
    return {"name": name, "annual_growth_pct": round(rate * 100, 1), "sale_price": round(sale, -3),
            "loan_balance_at_sale": round(left), "cash_before_cpf_refund": round(sale - left, -3)}
