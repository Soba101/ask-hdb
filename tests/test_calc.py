"""Raw arithmetic must be safe evidence before any tool serialization."""

import pytest

from ask_hdb.calc import calculate


@pytest.mark.parametrize("expression", ["1e308 * 1e308", "1e309 - 1e309"])
def test_nonfinite_arithmetic_is_rejected(expression):
    with pytest.raises(ValueError, match="finite"):
        calculate(expression)
