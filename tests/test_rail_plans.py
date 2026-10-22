from ask_hdb import tools
from ask_hdb.bto import plans


def test_area_filter_matches_name_or_areas():
    names = [line["name"] for line in plans.rail_plans("punggol")["lines"]]
    assert names == ["Cross Island Line Punggol Extension (CPE)"]
    assert plans.rail_plans("cross island")["n_lines"] == 4


def test_every_entry_has_timing_and_the_result_is_dated():
    out = plans.rail_plans()
    assert all(line["timing"] and line["areas"] for line in out["lines"])
    assert out["as_of"] == "2026-03-04" and out["source"].startswith("https://www.lta.gov.sg")


def test_tool_runs_without_arguments():
    assert tools.rail_plans.invoke({})["n_lines"] == 11
