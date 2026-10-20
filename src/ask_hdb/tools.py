"""Expose the unchanged deterministic functions as JSON tools."""

import json
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import pandas as pd
from langchain_core.tools import StructuredTool

from ask_hdb import compare, sales
from ask_hdb.rules import BuyerProfile, Flat, eligibility, grants, loan
from ask_hdb.tool_inputs import CompareArgs, FindArgs, LoanArgs, PhgArgs, RuleArgs, SalesArgs


@lru_cache(maxsize=1)
def load_sales():
    # Resolve from the repo, not the terminal's current directory.
    path = Path(__file__).resolve().parents[2] / "data/clean/resale.parquet"
    return pd.read_parquet(path)


def _rule_call(function, values):
    values = values.copy()
    # Models often send both timer fields. Keep the one that fits the scheme.
    values["first_timer" if values["scheme"] == "family" else "family_timers"] = None
    flat = Flat(**{key: values.pop(key) for key in Flat.model_fields})
    extra = {key: values.pop(key) for key in ("relation", "qualifying_rate_pct") if key in values}
    values["citizenships"] = [part.strip() for part in values["citizenships"].split(",")]
    values["ages"] = [int(part.strip()) for part in values["ages"].split(",")]
    return asdict(function(BuyerProfile(**values), flat, **extra))


def _tool(name, description, schema, function, *, rule=False):
    def invoke(**kwargs):
        try:
            # Include defaults here so the flat and profile are complete.
            values = schema.model_validate(kwargs).model_dump()
            result = (_rule_call(function, values) if rule else function(load_sales(), **values))
            if isinstance(result, list):
                result = {"sales": result}
            # Catch non-JSON results before they reach the chat client.
            return json.loads(json.dumps(result, allow_nan=False))
        except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
            # Keep a trace so a real bug is not mistaken for a bad model argument.
            print(f"[tool {name} failed: {type(exc).__name__}: {exc}]", file=sys.stderr)
            return {"error": f"Invalid arguments or unavailable data for {name}"}

    return StructuredTool.from_function(
        func=invoke, name=name, description=description, args_schema=schema,
        handle_validation_error=lambda exc: {"error": f"Invalid arguments for {name}. Missing or invalid: "
                                             + ", ".join(sorted({str(e["loc"][0]) for e in exc.errors()}))
                                             + ". Ask the user for missing details, then call again."},
    )


price_stats = _tool("price_stats", "Summarise recorded resale prices; dates are inclusive months.",
                    SalesArgs, sales.price_stats)
find_sales = _tool("find_sales", "Find newest recorded resale sales using exact filters.",
                   FindArgs, sales.find_sales)
compare_price = _tool("compare_price", "Compare past sales for a stable block_id; not a valuation.",
                      CompareArgs, compare.compare_price)
can_buy_resale = _tool("can_buy_resale", "Check resale purchase eligibility and unresolved checks.",
                       RuleArgs, eligibility.can_buy_resale, rule=True)
cpf_housing_grant = _tool("cpf_housing_grant", "Compute the sourced CPF Housing Grant.",
                          RuleArgs, grants.cpf_housing_grant, rule=True)
ehg_amount = _tool("ehg_amount", "Compute the sourced Enhanced CPF Housing Grant.",
                   RuleArgs, grants.ehg_amount, rule=True)
phg_amount = _tool("phg_amount", "Compute the Proximity Housing Grant for living with or near parents.",
                   PhgArgs, grants.phg_amount, rule=True)
max_loan = _tool("max_loan", "Estimate the HDB loan cap; disclose needs_check and valuation limits.",
                 LoanArgs, loan.max_loan, rule=True)

TOOLS = [price_stats, find_sales, compare_price, can_buy_resale,
         cpf_housing_grant, ehg_amount, phg_amount, max_loan]
