def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="ask-hdb")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("chat", help="Chat with the housing tools")
    one_shot = commands.add_parser("ask", help="Ask a housing question")
    one_shot.add_argument("question")
    commands.add_parser("eval", help="Run the week two tool-call check")
    args = parser.parse_args()
    if args.command is None:
        print("Hello from ask-hdb!")
        return
    if args.command == "eval":
        from ask_hdb.tool_check import main as evaluate

        evaluate()
        return
    from ask_hdb.cli import chat, print_answer

    if args.command == "chat":
        chat()
    else:
        from ask_hdb.agent import ask

        print_answer(ask(args.question))
