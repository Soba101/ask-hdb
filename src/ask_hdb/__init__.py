def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="ask-hdb")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("chat", help="Chat with the housing tools")
    one_shot = commands.add_parser("ask", help="Ask a housing question")
    one_shot.add_argument("question")
    commands.add_parser("routing", help="Run the week two tool-call check")
    evaluation = commands.add_parser("eval", help="Score answers against frozen questions")
    evaluation.add_argument("--condition", choices=("llm-only", "agent"), default="agent")
    evaluation.add_argument("--only", choices=("price", "eligibility", "grants", "price_check", "refuse"))
    evaluation.add_argument("--verbose", action="store_true")
    evaluation.add_argument("--heldout", action="store_true")
    evaluation.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command is None:
        print("Hello from ask-hdb!")
        return
    if args.command == "eval":
        from ask_hdb.evalrun import run

        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be positive")
        run(args.condition, only=args.only, verbose=args.verbose,
            heldout=args.heldout, limit=args.limit)
        return
    if args.command == "routing":
        from ask_hdb.tool_check import main as evaluate

        evaluate()
        return
    from ask_hdb.cli import chat, print_answer

    if args.command == "chat":
        chat()
    else:
        from ask_hdb.agent import ask

        print_answer(ask(args.question))
