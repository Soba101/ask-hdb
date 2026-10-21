"""Flat JSON fields keep tool calls manageable for small local models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Nonnegative = Annotated[float, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]
PlaceKind = Literal["mrt", "primary_school"]


class Arguments(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def _text_none(cls, data):
        # The 9B model writes the text "None" or "null" for "no value". For a required-but-nullable field that
        # means null; for a field with a default it means "use the default", so drop the key.
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for key, value in list(data.items()):
            field = cls.model_fields.get(key)
            empty = isinstance(value, str) and value.strip() == "" and field is not None and not field.is_required() \
                and field.default is None
            if empty or (isinstance(value, str) and value.strip().lower() in {"none", "null"}):
                if field is not None and field.is_required():
                    data[key] = None
                else:
                    del data[key]
        return data

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
    near_kind: PlaceKind | None = None
    near_km: Nonnegative | None = None

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


class NearestArgs(Arguments):
    block_id: str
    kind: PlaceKind
    n: Annotated[int, Field(ge=1)] = 3


class CompareArgs(Arguments):
    block_id: str
    price: Nonnegative
    flat_type: str

    _upper = field_validator("flat_type", mode="before")(SalesArgs._upper.__func__)
    # Required but nullable: the model must write a value or null, so it cannot silently skip a filter
    # (omitting lease_left_months gave wrong medians in two eval questions).
    storey_mid: Nonnegative | None = Field(description="Storey midpoint to match, or null for no storey filter")
    lease_left_months: Count | None = Field(description="Remaining lease in months, or null for no lease filter")
    floor_area_sqm: Nonnegative | None = Field(description="Floor area in sqm, or null for no area filter")
    # Required: the 9B model skips optional fields, which silently moved the window by a month.
    as_of: str = Field(description="Month YYYY-MM the comparison is as of, or 'latest' if none given")

    months: Annotated[int, Field(ge=1)] = 12
    storey_tol: Nonnegative = 3
    lease_tol_months: Count = 60
    area_tol_sqm: Nonnegative = 10
    min_n: Annotated[int, Field(ge=1)] = 5
    max_examples: Annotated[int, Field(ge=0, le=50)] = 10


class ProfileArgs(Arguments):
    scheme: Literal["family", "single"]
    citizenships: str = Field(description="Comma-separated SC, SPR or foreigner")
    ages: str = Field(description="Comma-separated applicant ages in years")
    monthly_household_income: Count
    own_monthly_income: Count | None = None
    # Required, because the 9B model fills required fields but skips optional ones.
    family_timers: Literal["both_first", "one_first", "none_first", "not_applicable"] = Field(
        description="Family scheme: are both, one or none first-timers. Single scheme: not_applicable")
    first_timer: Literal["yes", "no", "not_applicable"] = Field(
        description="Single scheme: is the buyer a first-timer. Family scheme: not_applicable")
    marital_status: Literal["unmarried", "divorced", "widowed", "married", "unknown"] = Field(
        description="Always set. Family scheme: married. Single scheme: what the user said, "
                    "or unknown if the user did not say")
    previous_hdb_loans: Count = Field(description="Number of previous HDB loans; ask if unknown")
    works_12_months: bool = Field(description="Worked continuously for the past 12 months; ask if unknown")
    owns_private_property: bool = Field(description="Owns private property; ask if unknown")
    buying_with: Literal["alone", "parents", "family_or_singles"] = "alone"
    extended_family: bool = False
    confirmed: bool = False


class RuleArgs(ProfileArgs):
    room: Annotated[int, Field(ge=1, le=6)]
    lease_left_months: Count
    price: Count | None = Field(None, description="Flat price in dollars; set it when given")
    category: Literal["standard", "plus", "prime"] | None = Field(
        None, description="Standard, Plus or Prime flat; set it when given")


class PhgArgs(RuleArgs):
    relation: Literal["with", "near"] | None


class LoanArgs(RuleArgs):
    qualifying_rate_pct: Nonnegative | None = None


class CalcArgs(Arguments):
    expression: str = Field(description="Arithmetic on numbers from tool results, e.g. 80000 + 70000 - 25000")


class BtoListArgs(Arguments):
    # Optional filters: leave out what the user did not ask for. (Required-nullable made the 9B model invent values.)
    name: str | None = Field(None, description="Part of a project name such as 'Tampines Nova'")
    town: str | None = Field(None, description="Town name such as TAMPINES")
    flat_type: Literal["2-room Flexi", "3-room", "4-room", "5-room", "3Gen", "CCA"] | None = Field(None, description="2-room Flexi, 3-room, 4-room, 5-room, 3Gen or CCA")
    launch_month: str | None = Field(None, description="Launch month YYYY-MM (2025-02, 2025-07, 2025-10, 2026-02, 2026-06)")
    category: Literal["Standard", "Plus", "Prime"] | None = Field(None, description="Project category")
    max_price: Nonnegative | None = Field(None, description="Keep flats whose lowest indicative price is at most this")
    limit: Annotated[int, Field(ge=1, le=20)] = 10


class BtoNearbyArgs(Arguments):
    project_id: str = Field(description="BTO project id such as bto_tampines-nova")
    kind: PlaceKind
    n: Annotated[int, Field(ge=1)] = 3


class BtoRuleArgs(ProfileArgs):
    category: Literal["Standard", "Plus", "Prime"] = Field(description="BTO project category")
    flat_type: Literal["2-room Flexi", "3-room", "4-room", "5-room", "3Gen"] = Field(description="BTO flat type")
    hfe_after_revision: bool | None = Field(
        description="True if the HFE letter was applied for on or after 24 Aug 2026 (revised income ceilings), False if before, null if unknown")
