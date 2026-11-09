from ask_hdb import policy, tools


def test_policy_tool_is_offered_only_when_pages_are_built():
    assert (tools.policy_explain in tools.TOOLS) == policy.PASSAGES_PATH.exists()
