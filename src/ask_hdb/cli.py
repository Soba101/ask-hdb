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
        try:
            result = ask(question, history, confirm=True)  # "Is this right?" before profile tools
        except Exception as exc:  # noqa: BLE001 - a network blip must not end the chat
            # Print only the type: provider error text can contain URLs or keys.
            print(f"Model call failed ({type(exc).__name__}). Try again.")
            continue
        print_answer(result)
        history.extend([HumanMessage(content=question), AIMessage(content=result["answer"])])
