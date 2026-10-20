"""Both conditions use the existing model factory and its configuration."""


def make_condition(condition):
    if condition == 'agent':
        from ask_hdb.agent import ask

        return ask
    if condition != 'llm-only':
        raise ValueError('Unknown condition')
    from langchain_core.messages import HumanMessage, SystemMessage

    from ask_hdb.llm import get_chat_model

    model = get_chat_model()

    def baseline(question):
        reply = model.invoke([SystemMessage(content='Answer the question.'),
                              HumanMessage(content=question)])
        usage = reply.usage_metadata or {}
        # Missing usage is unknown, never a fabricated zero-token result.
        truncated = reply.response_metadata.get('finish_reason') in {'length', 'max_tokens'}
        return {'answer': reply.text, 'tool_calls': [],
                'tokens': usage.get('total_tokens'),
                'stopped_reason': 'tokens' if truncated else None}

    return baseline
