"""Validated inputs shared by the rule functions."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

NonnegativeInt = Annotated[int, Field(ge=0)]
Citizenship = Literal["SC", "SPR", "foreigner"]


class BuyerProfile(BaseModel):
    scheme: Literal["family", "single"]
    citizenships: list[Citizenship] = Field(min_length=1, max_length=2)
    ages: list[NonnegativeInt] = Field(min_length=1, max_length=2)
    monthly_household_income: NonnegativeInt
    own_monthly_income: NonnegativeInt | None = None
    family_timers: Literal["both_first", "one_first", "none_first"] | None = None
    first_timer: bool | None = None
    marital_status: Literal["unmarried", "divorced", "widowed", "married"] | None = None
    works_12_months: bool = True
    owns_private_property: bool = False
    buying_with: Literal["alone", "parents", "family_or_singles"] = "alone"
    extended_family: bool = False
    confirmed: bool = False

    @model_validator(mode="after")
    def consistent_applicants(self):
        if len(self.ages) != len(self.citizenships):
            raise ValueError("Each applicant needs an age and citizenship")
        if self.scheme == "family" and self.first_timer is not None:
            raise ValueError("Use family_timers for families")
        if self.scheme == "single":
            if self.family_timers is not None:
                raise ValueError("Use first_timer for singles")
            if self.own_monthly_income is None:
                self.own_monthly_income = self.monthly_household_income
        return self


class Flat(BaseModel):
    room: int = Field(ge=2, le=5)
    lease_left_months: NonnegativeInt
    price: NonnegativeInt | None = None
    category: Literal["standard", "plus", "prime"] | None = None
