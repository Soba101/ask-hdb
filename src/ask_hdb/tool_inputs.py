"""Flat JSON fields keep tool calls manageable for small local models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Nonnegative = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class Arguments(BaseModel):
    # Reject misspelled filters rather than silently broadening a query.
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SalesArgs(Arguments):
    town: str | None = None
    flat_type: str | None = None
    block_id: str | None = None
    storey_min: Nonnegative | None = None
    storey_max: Nonnegative | None = None
    min_lease_months: Count | None = None
    since: str | None = Field(None, description="First month, YYYY-MM")
    until: str | None = Field(None, description="Last month, YYYY-MM")
    max_price: Nonnegative | None = None

    @field_validator("town", "flat_type", mode="before")
    @classmethod
    def _upper(cls, value):
        # The data stores TAMPINES and 4 ROOM; accept any casing from the model.
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("since", "until", mode="before")
    @classmethod
    def _bare_year(cls, value, info):
        # Models often send "2025". Read it as the whole year, not as January only.
        if isinstance(value, int):
            value = str(value)
        if isinstance(value, str) and value.strip().isdigit() and len(value.strip()) == 4:
            return f"{value.strip()}-{'01' if info.field_name == 'since' else '12'}"
        return value


class FindArgs(SalesArgs):
    limit: Annotated[int, Field(ge=0, le=50)] = 10


class CompareArgs(Arguments):
    block_id: str
    price: Nonnegative
    flat_type: str

    _upper = field_validator("flat_type", mode="before")(SalesArgs._upper.__func__)
    storey_mid: Nonnegative | None = None
    lease_left_months: Count | None = None
    floor_area_sqm: Nonnegative | None = None
    as_of: str | None = Field(None, description="Month, YYYY-MM")
    months: Annotated[int, Field(ge=1)] = 12
    storey_tol: Nonnegative = 3
    lease_tol_months: Count = 60
    area_tol_sqm: Nonnegative = 10
    min_n: Annotated[int, Field(ge=1)] = 5
    max_examples: Annotated[int, Field(ge=0, le=50)] = 10


class RuleArgs(Arguments):
    scheme: Literal["family", "single"]
    citizenships: str = Field(description="Comma-separated SC, SPR or foreigner")
    ages: str = Field(description="Comma-separated applicant ages in years")
    monthly_household_income: Count
    own_monthly_income: Count | None = None
    family_timers: Literal["both_first", "one_first", "none_first"] | None = Field(
        None, description="Family scheme: set it. Are both, one or none first-timers")
    first_timer: bool | None = Field(None, description="Single scheme only")
    marital_status: Literal["unmarried", "divorced", "widowed", "married"] | None = None
    previous_hdb_loans: Count = 0
    works_12_months: bool = True
    owns_private_property: bool = False
    buying_with: Literal["alone", "parents", "family_or_singles"] = "alone"
    extended_family: bool = False
    confirmed: bool = False
    room: Annotated[int, Field(ge=1, le=6)]
    lease_left_months: Count
    price: Count | None = Field(None, description="Flat price in dollars; set it when given")
    category: Literal["standard", "plus", "prime"] | None = Field(
        None, description="Standard, Plus or Prime flat; set it when given")


class PhgArgs(RuleArgs):
    relation: Literal["with", "near"] | None


class LoanArgs(RuleArgs):
    qualifying_rate_pct: Nonnegative | None = None
