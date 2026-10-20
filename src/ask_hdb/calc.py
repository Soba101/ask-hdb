"""Plain arithmetic for the agent, so the model never adds or subtracts numbers itself."""

import ast
import operator

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Only numbers and + - * / ( ) are allowed")


def calculate(expression: str) -> dict:
    # Commas and $ are common in copied amounts; strip them. Nothing else is allowed through ast.
    cleaned = expression.replace(",", "").replace("$", "").strip()
    if len(cleaned) > 200:
        raise ValueError("Expression too long")
    try:
        result = _eval(ast.parse(cleaned, mode="eval"))
    except (SyntaxError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"Cannot calculate: {type(exc).__name__}") from None
    return {"expression": cleaned, "result": round(result, 6) if isinstance(result, float) else result}
