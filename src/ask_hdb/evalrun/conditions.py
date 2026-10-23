"""All conditions use the existing model factory and its configuration."""


def make_condition(condition):
    if condition == 'agent':
        from ask_hdb.agent import ask

        return ask  # no profile confirmation, so earlier agent reports stay comparable
    if condition == 'full':
        return _full()
    if condition != 'llm-only':
        raise ValueError('Unknown condition')
    from langchain_core.messages import HumanMessage, SystemMessage

    from ask_hdb.llm import get_chat_model

    model = get_chat_model()

    def baseline(question, context=None):
        reply = model.invoke([SystemMessage(content='Answer the question.'),
                              HumanMessage(content=question)])
        usage = reply.usage_metadata or {}
        # Missing usage is unknown, never a fabricated zero-token result.
        truncated = reply.response_metadata.get('finish_reason') in {'length', 'max_tokens'}
        return {'answer': reply.text, 'tool_calls': [],
                'tokens': usage.get('total_tokens'),
                'stopped_reason': 'tokens' if truncated else None}

    return baseline


def _full():
    """The agent with profile confirmation. The eval user answers "yes" once, as a user who
    checked the profile would; a second confirmation request is left as the answer (and fails)."""
    from langchain_core.messages import AIMessage, HumanMessage

    from ask_hdb.agent import ask

    def full(question, context=None):
        first = ask(question, confirm=True, context=context)
        if not first.get('needs_confirmation'):
            return first
        second = ask('yes', [HumanMessage(content=question), AIMessage(content=first['answer'])], confirm=True,
                     context=context)
        tokens = [r['tokens'] for r in (first, second) if r['tokens'] is not None]
        return {**second, 'tokens': sum(tokens) if tokens else None, 'confirmation': first['answer']}

    return full
