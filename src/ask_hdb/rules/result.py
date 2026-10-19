"""Results keep estimates, unresolved checks and rule sources together."""

from dataclasses import dataclass, field


@dataclass
class RuleResult:
    eligible: bool | None = None
    amount: int = 0
    reasons: list[str] = field(default_factory=list)
    needs_check: list[str] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    detail: dict = field(default_factory=dict)
