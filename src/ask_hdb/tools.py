"""Expose the unchanged deterministic functions as JSON tools."""

import json
import os
import re
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import pandas as pd
from langchain_core.tools import StructuredTool

from ask_hdb import calc, compare, sales
from ask_hdb.bto import plans, scenario
from ask_hdb.bto import queries as bto
from ask_hdb.geo import filters as geo_filters
from ask_hdb.geo import resolve as geo_resolve
from ask_hdb.rules import BuyerProfile, Flat, eligibility, grants, loan
from ask_hdb.rules import bto as bto_rules
from ask_hdb.tool_inputs import (
    BtoHistoryArgs,
    BtoListArgs,
    BtoNearbyArgs,
    BtoRuleArgs,
    BtoScenarioArgs,
    CalcArgs,
    CompareArgs,
    FindArgs,
    LoanArgs,
    NearestArgs,
    PhgArgs,
    ProfileArgs,
    RailPlansArgs,
    ResolveArgs,
    RuleArgs,
    SalesArgs,
)

# Tools that read their own tables instead of the resale sales frame.
NO_FRAME = {"nearest_places", "calculate", "list_bto_projects", "bto_nearby", "bto_scenario", "bto_history", "rail_plans", "resolve_place"}


@lru_cache(maxsize=1)
def load_sales():
    # Resolve from the repo, not the terminal's current directory.
    path = Path(__file__).resolve().parents[2] / "data/clean/resale.parquet"
    return pd.read_parquet(path)


def _profile_values(values):
    values = values.copy()
    if values["scheme"] == "family" or values["marital_status"] == "unknown":
        values["marital_status"] = None  # only singles use it; unknown becomes a needs_check
    # Models often send both timer fields. Keep the one that fits the scheme.
    if values["scheme"] == "family":
        values["first_timer"] = "not_applicable"
    else:
        values["family_timers"] = "not_applicable"
    values["first_timer"] = {"yes": True, "no": False}.get(values["first_timer"])
    if values["family_timers"] == "not_applicable":
        values["family_timers"] = None
    return values


def _rule_call(function, values):
    values = _profile_values(values)
    flat = Flat(**{key: values.pop(key) for key in Flat.model_fields})
    extra = {key: values.pop(key) for key in ("relation", "qualifying_rate_pct") if key in values}
    values["citizenships"] = [part.strip() for part in values["citizenships"].split(",")]
    values["ages"] = [int(part.strip()) for part in values["ages"].split(",")]
    return asdict(function(BuyerProfile(**values), flat, **extra))


def _bto_call(function, values):
    values = _profile_values(values)
    extra = {key: values.pop(key) for key in ("category", "flat_type", "hfe_after_revision") if key in values}
    values["citizenships"] = [part.strip() for part in values["citizenships"].split(",")]
    values["ages"] = [int(part.strip()) for part in values["ages"].split(",")]
    return asdict(function(BuyerProfile(**values), **extra))


def _validation_error(name):
    def handle(exc):
        errors = exc.errors()
        extra = sorted({str(e["loc"][0]) for e in errors if e["type"] == "extra_forbidden"})
        bad = sorted({str(e["loc"][0]) for e in errors if e["type"] != "extra_forbidden"})
        parts = ([f"Missing or invalid: {', '.join(bad)}."] if bad else []) + (
            [f"Not accepted by this tool, leave out: {', '.join(extra)}."] if extra else [])
        return {"error": f"Invalid arguments for {name}. " + " ".join(parts)
                + " Fix these or ask the user for missing details, then call again."}
    return handle


def _tool(name, description, schema, function, *, rule=False, bto_rule=False):
    def invoke(**kwargs):
        try:
            # Include defaults here so the flat and profile are complete.
            values = schema.model_validate(kwargs).model_dump()
            if os.getenv("LLM_COMPACT_TOOLS") == "1":
                # Small-context servers: shorter example lists keep tool results small.
                for key, cap in (("max_examples", 3), ("limit", 5)):
                    if key in values:
                        values[key] = min(values[key], cap)
            if str(values.get("as_of")).lower() == "latest":
                values["as_of"] = None  # compare_price anchors to the newest data month
            distance_filter, unlocated_frame = False, None
            if name in NO_FRAME:
                result = function(**values)
            elif bto_rule:
                result = _bto_call(function, values)
            elif rule:
                result = _rule_call(function, values)
            else:
                if name in {"price_stats", "find_sales"}:
                    geo_filters.validate_near(values)
                    frame, values, distance_filter, unlocated_frame = geo_filters.filter_sales(load_sales(), values)
                else:
                    frame = load_sales()
                result = function(frame, **values)
            if isinstance(result, list):
                result = {"sales": result}
            if distance_filter:
                result["distance_method"] = "straight-line"
                # Sales in blocks without coordinates are left out of a distance filter.
                same = {k: v for k, v in values.items() if k != "limit"}
                result["sales_without_coordinates"] = sales.price_stats(unlocated_frame, **same)["n_sales"]
            # Catch non-JSON results before they reach the chat client.
            return json.loads(json.dumps(result, allow_nan=False))
        except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
            # Keep a trace so a real bug is not mistaken for a bad model argument.
            print(f"[tool {name} failed: {type(exc).__name__}: {exc}]", file=sys.stderr)
            if name in NO_FRAME or "near_kind" in kwargs or "near_km" in kwargs:
                # Keep the message the model needs ("blocks.parquet is missing") but never a server directory.
                return {"error": f"{name}: " + re.sub(r"(?:/[^/\s'\"]+)+/([^/\s'\"]+)", r"\1", str(exc))}
            return {"error": f"Invalid arguments or unavailable data for {name}"}

    return StructuredTool.from_function(
        func=invoke, name=name, description=description, args_schema=schema,
        handle_validation_error=_validation_error(name),
    )


price_stats = _tool("price_stats", "Summarise recorded resale prices; dates are inclusive months.",
                    SalesArgs, sales.price_stats)
find_sales = _tool("find_sales", "Find newest recorded resale sales using exact filters.",
                   FindArgs, sales.find_sales)
compare_price = _tool("compare_price", "Compare past sales for a stable block_id; not a valuation.",
                      CompareArgs, compare.compare_price)
can_buy_resale = _tool("can_buy_resale", "Check RESALE flat purchase eligibility and unresolved checks (not for new BTO flats).",
                       RuleArgs, eligibility.can_buy_resale, rule=True)
cpf_housing_grant = _tool("cpf_housing_grant", "Compute the sourced CPF Housing Grant for buying a RESALE flat.",
                          RuleArgs, grants.cpf_housing_grant, rule=True)
ehg_amount = _tool("ehg_amount", "Enhanced CPF Housing Grant (EHG) for buying a RESALE flat. Use this for any EHG question that mentions resale, a resale price or lease left.",
                   RuleArgs, grants.ehg_amount, rule=True)
phg_amount = _tool("phg_amount", "Compute the Proximity Housing Grant for living with or near parents.",
                   PhgArgs, grants.phg_amount, rule=True)
max_loan = _tool("max_loan", "Estimate the HDB loan cap; disclose needs_check and valuation limits.",
                 LoanArgs, loan.max_loan, rule=True)

resolve_place = _tool("resolve_place", "Find the id of ONE specific place the user names in words (a block like 'Blk 227 Bishan St 23', a named station, a named school like 'Catholic High School' or a named BTO project). NEVER use it for a category ('a primary school', 'schools in Bishan') or for sales near schools or stations: those use price_stats or find_sales with near_kind and near_km. Skip it when the Map context line already gives the id. If several candidates come back, ask the user which one; if none, say it was not found. A town is not a point.",
                      ResolveArgs, geo_resolve.resolve_place)

nearest_places = _tool("nearest_places", "Find nearest places by straight-line distance from a block, station, school or BTO site (pass its id as block_id). For 'how many within X km', pass within_km and quote n_within.",
                       NearestArgs, geo_filters.nearest_places)

calculate = _tool("calculate", "Add, subtract, multiply or divide numbers taken from tool results. Use it for ALL arithmetic.",
                  CalcArgs, lambda expression: calc.calculate(expression))

list_bto_projects = _tool("list_bto_projects", "List BTO projects from recent HDB launches with units and indicative launch prices (excluding grants). Projects HDB lists as upcoming (not on sale yet, no price) come back under upcoming_projects.",
                          BtoListArgs, bto.list_bto_projects)
bto_nearby = _tool("bto_nearby", "Nearest MRT stations or primary schools to a BTO project's approximate site.",
                   BtoNearbyArgs, bto.bto_nearby)

bto_history = _tool("bto_history", "PAST BTO launch price ranges next to resale prices of comparable flats sold a little after the minimum occupation period, by town and flat type. Descriptive history only, never a forecast; quote the limits.",
                    BtoHistoryArgs, bto.bto_history)

rail_plans = _tool("rail_plans", "PLANNED MRT lines and their LTA target years, from a dated factsheet. Facts only; never say a line will raise or lower flat prices.",
                   RailPlansArgs, plans.rail_plans)

can_apply_bto = _tool("can_apply_bto", "Check NEW BTO flat eligibility only (never resale): income ceilings (previous vs revised 24 Aug 2026), singles limits, MOP.",
                      BtoRuleArgs, bto_rules.can_apply_bto, bto_rule=True)
def _bto_scenario(**values):
    return scenario.bto_scenario(load_sales(), **values)


bto_scenario = _tool("bto_scenario", "BTO flat loan figures: maximum loan, monthly instalment, upfront cost, loan balance at MOP and illustrative sale scenarios from past growth (not a forecast). Use this, not max_loan or calculate, for any BTO loan question.",
                     BtoScenarioArgs, _bto_scenario)
bto_ehg_amount = _tool("bto_ehg_amount", "EHG for a NEW BTO flat ONLY (no resale price or lease). If the user says resale, use ehg_amount instead.",
                       ProfileArgs, bto_rules.bto_ehg, bto_rule=True)

TOOLS = [price_stats, find_sales, compare_price, can_buy_resale,
         cpf_housing_grant, ehg_amount, phg_amount, max_loan, nearest_places, calculate, list_bto_projects, bto_nearby, can_apply_bto, bto_ehg_amount,
         bto_scenario, bto_history, rail_plans, resolve_place]
