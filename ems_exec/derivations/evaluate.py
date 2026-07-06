"""derivations/evaluate.py — the ONE safe, generic evaluator for derivation_binding.expression rows.

A DB expression row IS the formula (the RESOLVERS python map collapsed into the table); this module executes it over
the executor's derivation ctx with a strict ast-parse WHITELIST — never eval/exec, never attribute/subscript access on
python objects, never a call outside the tiny fn set. Grammar:
    numeric literals            42, 3.5
    arithmetic                  + - * / **  and unary minus, with parentheses
    functions                   sqrt(x), abs(x), min(...), max(...), round(x[, ndigits])
    names                       <col>            → ctx['row'][col]        (latest-row value; 'nameplate:<k>' keys too)
                                start.<col>      → ctx['start_row'][col]  (window-open endpoint row)
                                end.<col>        → ctx['end_row'][col]    (window-close endpoint row)
                                nameplate.<key>  → ctx['nameplate'][key]  (falls back to row['nameplate:<key>'],
                                                    the pseudo-column the executor already injects)
HONEST-DEGRADE: any missing/None/non-numeric input, any unsafe node, any arithmetic error (÷0, sqrt(<0), overflow) or
a non-finite result → None. NEVER fabricates, NEVER raises. [atomic: this file = the interpreter, nothing else]
"""
from __future__ import annotations

import ast
import math

# the ONLY callables an expression may invoke (dimension-preserving numeric helpers; no I/O, no state)
_FUNCS = {"sqrt": math.sqrt, "abs": abs, "min": min, "max": max, "round": round}

# the ONLY binary/unary operators (arithmetic; no bitwise, no comparisons, no boolean logic).
# Pow COERCES TO FLOAT: int ** int is arbitrary-precision in python — `10 ** 10 ** 10` would grind on a bignum for
# minutes (a DoS, not an OverflowError); float ** float overflows immediately → honest None.
_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: float(a) ** float(b)}
_UNARY = {ast.USub: lambda a: -a, ast.UAdd: lambda a: +a}

# dotted-name roots: `start.x` / `end.x` are WINDOW-ENDPOINT column reads, `nameplate.k` the nameplate read. These are
# the ONLY Attribute forms allowed — a dotted NAME resolution, never python attribute access on an object.
_DOTTED_ROOTS = {"start": "start_row", "end": "end_row"}

_MAX_NODES = 200          # defensive size cap — a formula is a one-liner, not a program


class _Degrade(Exception):
    """Internal: honest-degrade signal (missing input / unsafe node / bad arithmetic). Never escapes evaluate()."""


def _num(x):
    """Coerce one resolved input to a finite float, else degrade (None / text / bool / NaN / inf are NOT numbers)."""
    if x is None or isinstance(x, bool):
        raise _Degrade()
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise _Degrade()
    if not math.isfinite(v):
        raise _Degrade()
    return v


def _lookup(mapping, key):
    v = (mapping or {}).get(key)
    return _num(v)


def _resolve_name(name, ctx):
    """A bare NAME = a latest-row column (ctx['row'])."""
    return _lookup((ctx or {}).get("row"), name)


def _resolve_dotted(root, attr, ctx):
    """start.<col> / end.<col> / nameplate.<key> — the whitelisted dotted-name reads."""
    ctx = ctx or {}
    if root in _DOTTED_ROOTS:
        return _lookup(ctx.get(_DOTTED_ROOTS[root]), attr)
    if root == "nameplate":
        np = ctx.get("nameplate")
        if isinstance(np, dict) and np.get(attr) is not None:
            return _num(np.get(attr))
        # the executor injects nameplate values as 'nameplate:<key>' pseudo-columns on the row — accept that form too
        return _lookup(ctx.get("row"), f"nameplate:{attr}")
    raise _Degrade()


def _eval(node, ctx):
    """Recursive whitelist walk — anything not explicitly allowed degrades."""
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _Degrade()                                   # numeric literals ONLY (no strings/None/bools)
        return node.value                                      # keep int-ness: round(x, 2) needs an int ndigits
    if isinstance(node, ast.Name):
        return _resolve_name(node.id, ctx)
    if isinstance(node, ast.Attribute):
        # ONLY the dotted-name form Name('start'|'end'|'nameplate').<identifier> — never object attribute access
        if isinstance(node.value, ast.Name):
            return _resolve_dotted(node.value.id, node.attr, ctx)
        raise _Degrade()
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise _Degrade()
        return op(_eval(node.left, ctx), _eval(node.right, ctx))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise _Degrade()
        return op(_eval(node.operand, ctx))
    if isinstance(node, ast.Call):
        # a plain whitelisted fn name with positional args only — no keywords, no *args, no attribute calls
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS or node.keywords:
            raise _Degrade()
        args = [_eval(a, ctx) for a in node.args]
        if not args:
            raise _Degrade()
        return _FUNCS[node.func.id](*args)
    raise _Degrade()                                           # subscripts, lambdas, comprehensions, f-strings, …


def evaluate(expression, ctx):
    """Execute one restricted expression over the derivation ctx → finite float, or None (honest-degrade).

    None on: empty/unparseable text, any non-whitelisted construct (the injection net), any missing/None/non-numeric
    input, ÷0 / sqrt(<0) / overflow, or a non-finite result. NEVER raises, NEVER fabricates."""
    if not expression or not isinstance(expression, str):
        return None
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None
    if sum(1 for _ in ast.walk(tree)) > _MAX_NODES:
        return None
    try:
        v = _eval(tree, ctx or {})
    except (_Degrade, ZeroDivisionError, OverflowError, ValueError, TypeError, RecursionError):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError, OverflowError):               # float(huge-int) raises OverflowError
        return None
    return v if math.isfinite(v) else None
