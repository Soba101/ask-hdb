"""Terminal output keeps the tool evidence visible next to the answer."""

import json

from langchain_core.messages import AIMessage, HumanMessage

from ask_hdb.agent import ask


def print_answer(result):
    for call in result["tool_calls"]:
        print(f"Tool: {call['name']} {json.dumps(call['args'])}")
        print(json.dumps(call["result"], ensure_ascii=False))
    print(result["answer"])


def chat():
    history = []
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question.lower() in {"exit", "quit"}:
            return
        if not question:
            continue
        result = ask(question, history)
        print_answer(result)
        history.extend([HumanMessage(content=question), AIMessage(content=result["answer"])])
