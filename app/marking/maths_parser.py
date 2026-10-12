"""A small, locked-down parser for typed Mathematics answers (owner: maths).

Student input is reachable from the web (the answer box and the live preview), so it is never
handed to ``eval``, ``sympify`` or ``parse_expr``. Instead this module

* normalises calculator / LaTeX / unicode notation into a short ASCII string,
* tokenises it against a fixed whitelist (digits, ``+ - * / ^ ( ) |`` and the names ``x n t k``,
  ``pi e``, ``sin cos tan exp ln log sqrt abs``),
* builds a tiny AST with a recursive-descent parser that has hard caps on length, tokens, nodes,
  nesting depth, literal size, exponents and constant magnitudes, and
* evaluates that AST with plain floating-point / ``mpmath`` arithmetic (bounded work per node).

Nothing here can execute code, and every operation is O(size of the input), so a crafted answer
cannot hang a worker. Every failure is a :class:`ParseError` with a message written for the student.
"""
from __future__ import annotations

import cmath
import math
import re
from dataclasses import dataclass
from fractions import Fraction

import mpmath

# ------------------------------------------------------------------ limits ---
MAX_CHARS = 300          # one answer (a value or an expression)
MAX_TOKENS = 160
MAX_NODES = 160
MAX_DEPTH = 40           # nesting of brackets / functions
MAX_INT_DIGITS = 15      # digits before the decimal point in one literal
MAX_DECIMALS = 12        # digits after the decimal point in one literal
MAX_EXPONENT = 1000      # |constant exponent|
MAX_MAGNITUDE = 1e60     # |any constant sub-expression|

FUNCTIONS = ("sqrt", "sin", "cos", "tan", "exp", "log", "abs", "ln", "sec", "cosec", "csc", "cot")
RECIPROCAL_TRIG = {"sec": "cos", "cosec": "sin", "csc": "sin", "cot": "tan"}  # rewritten as 1/cos etc.
CONSTANTS = ("pi", "e")
DEFAULT_VARS = ("x", "n", "t", "k")


class ParseError(ValueError):
    """The input could not be read as mathematics (message is shown to the student)."""


# ------------------------------------------------------------- normalising ---
_SUPERSCRIPTS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-", "⁺": "+"}
_VULGAR = {"½": "(1/2)", "⅓": "(1/3)", "⅔": "(2/3)", "¼": "(1/4)", "¾": "(3/4)", "⅕": "(1/5)", "⅛": "(1/8)"}
_SIMPLE_REPLACE = [
    ("−", "-"), ("–", "-"), ("—", "-"), ("‐", "-"), ("×", "*"), ("·", "*"), ("⋅", "*"), ("∙", "*"), ("÷", "/"),
    ("π", "pi"), ("√", "sqrt"), ("∞", "oo"), ("≤", "<="), ("⩽", "<="), ("≥", ">="), ("⩾", ">="), ("∪", " U "),
    ("\u00a0", " "), ("\u2009", " "), ("\u202f", " "), ("ℯ", "e"), ("∈", " in "),
]
_LATEX_WORDS = [
    ("\\pi", "pi"), ("\\ln", "ln"), ("\\log", "log"), ("\\sin", "sin"), ("\\cos", "cos"), ("\\tan", "tan"), ("\\exp", "exp"),
    ("\\sec", "sec"), ("\\csc", "csc"), ("\\cot", "cot"),
    ("\\cdot", "*"), ("\\times", "*"), ("\\div", "/"), ("\\infty", "oo"), ("\\leq", "<="), ("\\le", "<="), ("\\geq", ">="),
    ("\\ge", ">="), ("\\lt", "<"), ("\\gt", ">"), ("\\cup", " U "), ("\\in", " in "), ("\\%", "%"), ("\\$", "$"),
    ("\\lvert", "|"), ("\\rvert", "|"), ("\\vert", "|"), ("\\mid", "|"),
]


def _latex_to_plain(s: str) -> str:
    for junk in ("\\left", "\\right", "\\displaystyle", "\\,", "\\!", "\\;", "\\:", "\\quad", "\\qquad"):
        s = s.replace(junk, " " if junk in ("\\,", "\\;", "\\:", "\\quad", "\\qquad") else "")
    s = s.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    s = re.sub(r"\\(?:text|mathrm|textrm|operatorname|mbox)\{([^{}]*)\}", r" \1 ", s)
    for _ in range(12):  # nested \frac{..}{..}, \sqrt{..}, ^{..}
        s2 = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", s)
        s2 = re.sub(r"\\sqrt\s*\[([^\[\]]*)\]\s*\{([^{}]*)\}", r"((\2)^(1/(\1)))", s2)
        s2 = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", s2)
        s2 = re.sub(r"\^\s*\{([^{}]*)\}", r"^(\1)", s2)
        s2 = re.sub(r"_\s*\{([^{}]*)\}", r"_(\1)", s2)
        if s2 == s:
            break
        s = s2
    for a, b in _LATEX_WORDS:
        s = s.replace(a, b)
    s = s.replace("{", "(").replace("}", ")")
    s = re.sub(r"\\[A-Za-z]+", " ", s)  # any other command is dropped
    return s.replace("\\", " ")


def normalise(text: str) -> str:
    """Calculator / LaTeX / unicode -> plain ASCII maths (no evaluation happens here)."""
    s = (text or "").strip()
    if len(s) > MAX_CHARS * 4:
        raise ParseError("That answer is too long to read. Give just the final answer.")
    for a, b in (("\\(", " "), ("\\)", " "), ("\\[", " "), ("\\]", " "), ("$$", " ")):
        s = s.replace(a, b)
    for a, b in _SIMPLE_REPLACE:
        s = s.replace(a, b)
    for a, b in _VULGAR.items():
        s = s.replace(a, b)
    s = re.sub("[" + "".join(_SUPERSCRIPTS) + "]+", lambda m: "^(" + "".join(_SUPERSCRIPTS[c] for c in m.group(0)) + ")", s)
    s = re.sub(r"(?i)\b(?:the\s+)?square\s+root\s+of\b|\broot\b", "sqrt", s)
    if "\\" in s or "{" in s:
        s = _latex_to_plain(s)
    s = s.replace("**", "^")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------- tokens ---
@dataclass
class Tok:
    kind: str  # num | name | op
    text: str
    space_before: bool
    value: Fraction | None = None
    decimal: bool = False


_NAME_PARTS = sorted(FUNCTIONS + CONSTANTS, key=len, reverse=True)


def _split_name(run: str, allowed_vars: tuple[str, ...]) -> list[str]:
    """Split a run of letters into whitelisted names, e.g. 'xcosx' -> x, cos, x."""
    low = run.lower() if run not in ("E",) else "e"
    if run == "Abs":
        return ["abs"]
    out, i = [], 0
    while i < len(low):
        for name in _NAME_PARTS:
            if low.startswith(name, i):
                out.append(name)
                i += len(name)
                break
        else:
            ch = low[i]
            if ch in allowed_vars:
                out.append(ch)
                i += 1
            else:
                bad = run[i]
                hint = ", ".join(allowed_vars) if allowed_vars else "no letters"
                raise ParseError(f"I don't recognise '{bad}' in '{run}'. Letters allowed here: {hint}; functions sin, cos, tan, ln, log, exp, sqrt; constants pi and e.")
    return out


def tokenize(s: str, allowed_vars: tuple[str, ...] = DEFAULT_VARS) -> list[Tok]:
    toks: list[Tok] = []
    i, space = 0, False
    while i < len(s):
        ch = s[i]
        if ch.isspace():
            space = True
            i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < len(s) and s[i + 1].isdigit()):
            m = re.match(r"\d*\.?\d*", s[i:])
            lit = m.group(0)
            sci = re.match(r"[eE]([+-]?\d{1,2})(?![A-Za-z0-9^(.])", s[i + len(lit):])
            if sci and lit.replace(".", "").isdigit():
                expo = int(sci.group(1))
                whole, _, frac = lit.partition(".")
                if len(whole.lstrip("0")) > MAX_INT_DIGITS or len(frac) > MAX_DECIMALS:
                    raise ParseError("That number has too many digits to be a sensible answer.")
                val = Fraction(lit) * (Fraction(10) ** expo)
                toks.append(Tok("num", lit + sci.group(0), space, val, True))
                i += len(lit) + len(sci.group(0))
                space = False
                continue
            whole, _, frac = lit.partition(".")
            if len(whole.lstrip("0")) > MAX_INT_DIGITS:
                raise ParseError("That number has too many digits to be a sensible answer.")
            if len(frac) > MAX_DECIMALS:
                raise ParseError(f"Give at most {MAX_DECIMALS} decimal places.")
            toks.append(Tok("num", lit, space, Fraction(lit if lit != "." else "0"), "." in lit))
            i += len(lit)
        elif ch.isalpha():
            m = re.match(r"[A-Za-z]+", s[i:])
            run = m.group(0)
            for j, part in enumerate(_split_name(run, allowed_vars)):
                toks.append(Tok("name", part, space if j == 0 else False))
            i += len(run)
        elif ch in "+-*/^()|_,":
            toks.append(Tok("op", ch, space))
            i += 1
        else:
            raise ParseError(f"I can't use the character '{ch}' here.")
        space = False
        if len(toks) > MAX_TOKENS:
            raise ParseError("That answer is too long to read. Give just the final answer.")
    return toks


# ------------------------------------------------------------------- AST ---
# Nodes are tuples: ('num', Fraction, decimal) ('var', name) ('const', 'pi'|'e') ('neg', a)
# ('add', a, b) ('sub', a, b) ('mul', a, b) ('div', a, b) ('pow', a, b) ('fn', name, a)
# ('logb', base, a) ('abs', a)


class _Parser:
    def __init__(self, toks: list[Tok]):
        self.toks, self.i, self.depth, self.nodes, self.abs_open = toks, 0, 0, 0, 0

    # -- helpers --
    def peek(self, k: int = 0) -> Tok | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def take(self) -> Tok:
        t = self.peek()
        if t is None:
            raise ParseError("The answer seems unfinished (a bracket or a number is missing).")
        self.i += 1
        return t

    def is_op(self, text: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t is not None and t.kind == "op" and t.text == text

    def node(self, *n):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise ParseError("That expression is too long. Simplify it before submitting.")
        return n

    def enter(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ParseError("Too many nested brackets or functions.")

    def leave(self):
        self.depth -= 1

    # -- grammar --
    def parse(self):
        if not self.toks:
            raise ParseError("empty answer")
        e = self.sum()
        if self.peek() is not None:
            t = self.peek()
            raise ParseError(f"I couldn't read the answer from '{t.text}' onwards.")
        return e

    def sum(self):
        left = self.term()
        while self.is_op("+") or self.is_op("-"):
            op = self.take().text
            right = self.term()
            left = self.node("add" if op == "+" else "sub", left, right)
        return left

    def starts_atom(self, t: Tok | None) -> bool:
        if t is None:
            return False
        if t.kind in ("num", "name"):
            return True
        if t.kind == "op" and t.text == "(":
            return True
        return t.kind == "op" and t.text == "|" and self.abs_open == 0

    def term(self):
        left = self.unary()
        while True:
            if self.is_op("*") or self.is_op("/"):
                op = self.take().text
                right = self.unary()
                left = self.node("mul" if op == "*" else "div", left, right)
            elif self.starts_atom(self.peek()):
                t = self.peek()
                if t.kind == "num":
                    raise ParseError("Two numbers are next to each other: put an operator (or a comma) between them, and write 2x rather than x2.")
                right = self.power()
                left = self.node("mul", left, right)
            else:
                return left

    def unary(self):
        if self.is_op("-"):
            self.take()
            self.enter()
            a = self.unary()
            self.leave()
            return self.node("neg", a)
        if self.is_op("+"):
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.is_op("^"):
            self.take()
            self.enter()
            exp = self.exponent(absorb=base == ("const", "e"))
            self.leave()
            return self.node("pow", base, exp)
        return base

    def exponent(self, absorb: bool = False):
        """Right-associative; allows a sign. For base e, 'e^2x' and 'e^-3t' mean e^(2x), e^(-3t)."""
        if self.is_op("-"):
            self.take()
            return self.node("neg", self.exponent(absorb))
        if self.is_op("+"):
            self.take()
            return self.exponent(absorb)
        e = self.atom()
        if absorb and e[0] == "num":
            while (t := self.peek()) is not None and t.kind == "name" and not t.space_before and t.text not in FUNCTIONS:
                e = self.node("mul", e, self.atom())
        if self.is_op("^"):
            self.take()
            self.enter()
            e = self.node("pow", e, self.exponent())
            self.leave()
        return e

    def atom(self):
        t = self.take()
        if t.kind == "num":
            return self.node("num", t.value, t.decimal)
        if t.kind == "name":
            if t.text in CONSTANTS:
                return self.node("const", t.text)
            if t.text in FUNCTIONS:
                return self.function(t.text)
            return self.node("var", t.text)
        if t.text == "(":
            self.enter()
            e = self.sum()
            self.leave()
            if not self.is_op(")"):
                raise ParseError("A closing bracket ')' is missing.")
            self.take()
            return e
        if t.text == "|":
            self.enter()
            self.abs_open += 1
            e = self.sum()
            self.abs_open -= 1
            self.leave()
            if not self.is_op("|"):
                raise ParseError("A closing '|' is missing.")
            self.take()
            return self.node("abs", e)
        raise ParseError(f"I didn't expect '{t.text}' there.")

    def function(self, name: str):
        self.enter()
        power = None
        base = None
        if name == "log":
            if self.is_op("_"):
                self.take()
                b = self.take()
                if b.kind == "num":
                    base = self.node("num", b.value, b.decimal)
                elif b.kind == "name" and b.text == "e":
                    base = self.node("const", "e")
                elif b.kind == "op" and b.text == "(":
                    self.i -= 1
                    base = self.atom()
                else:
                    raise ParseError("Write a logarithm base like log_2(8).")
            elif (t := self.peek()) is not None and t.kind == "num" and not t.space_before and self.is_op("(", 1):
                b = self.take()  # log2(8), log10(100)
                base = self.node("num", b.value, b.decimal)
        if self.is_op("^") and name in ("sin", "cos", "tan", "ln", "log", "sec", "cosec", "csc", "cot"):
            self.take()  # sin^2 x  ==  (sin x)^2
            power = self.exponent()
        arg = self.func_arg(single=name == "sqrt")
        if name in RECIPROCAL_TRIG:  # sec x = 1/cos x, cosec x = 1/sin x, cot x = 1/tan x
            res = self.node("div", self.node("num", Fraction(1), False), self.node("fn", RECIPROCAL_TRIG[name], arg))
        elif name == "ln":
            res = self.node("fn", "log", arg)
        elif name == "log" and base is not None:
            res = self.node("logb", base, arg)
        else:
            res = self.node("fn", name, arg)
        self.leave()
        if power is not None:
            res = self.node("pow", res, power)
        return res

    def func_arg(self, single: bool):
        t = self.peek()
        if t is None:
            raise ParseError("A function needs something to act on, e.g. sin(2x) or ln(x).")
        if t.kind == "op" and t.text == "(":
            return self.atom()
        if t.kind == "op" and t.text == "|":
            return self.atom()
        if t.kind == "op" and t.text == "-":
            self.take()
            return self.node("neg", self.func_arg(single))
        # without brackets: 'sin 2x' = sin(2x); 'ln x^2' = ln(x^2); stops at + - * / and other functions
        items = []
        if t.kind == "name" and t.text in FUNCTIONS:
            return self.power()  # 'ln sqrt x', 'sin cos x'
        while (t := self.peek()) is not None:
            if t.kind == "num" and items:
                break
            if t.kind == "name" and t.text in FUNCTIONS:
                break
            if not (t.kind in ("num", "name") or (t.kind == "op" and t.text == "(")):
                break
            items.append(self.power())
            if single:
                break
        if not items:
            raise ParseError("A function needs something to act on, e.g. sin(2x) or ln(x).")
        arg = items[0]
        for it in items[1:]:
            arg = self.node("mul", arg, it)
        return arg


# ------------------------------------------------------------ evaluation ---
def _f(name: str, a: complex) -> complex:
    if name == "sin":
        return cmath.sin(a)
    if name == "cos":
        return cmath.cos(a)
    if name == "tan":
        return cmath.tan(a)
    if name == "exp":
        if a.real > 700:
            raise OverflowError
        return cmath.exp(a)
    if name == "log":
        if a == 0:
            raise ZeroDivisionError
        return cmath.log(a)
    if name == "sqrt":
        return cmath.sqrt(a)
    if name == "abs":
        return complex(abs(a))
    raise ValueError(name)


def _pow(a: complex, b: complex) -> complex:
    if a == 0:
        if b.real > 0:
            return 0j
        raise ZeroDivisionError
    if b.imag == 0 and float(b.real).is_integer() and abs(b.real) <= MAX_EXPONENT and a.imag == 0:
        r = float(a.real) ** int(b.real)
        return complex(r)
    if a.imag == 0 and a.real > 0 and b.imag == 0:
        lr = b.real * math.log(a.real)
        if lr > 700:
            raise OverflowError
        return complex(math.exp(lr))
    m = b * cmath.log(a)
    if m.real > 700:
        raise OverflowError
    return cmath.exp(m)


def evaluate(node, env: dict[str, complex] | None = None) -> complex:
    """Floating-point evaluation (complex). Raises ZeroDivisionError/OverflowError/ValueError."""
    env = env or {}
    k = node[0]
    if k == "num":
        return complex(node[1])
    if k == "var":
        if node[1] not in env:
            raise ValueError(f"no value for {node[1]}")
        return env[node[1]]
    if k == "const":
        return complex(math.pi if node[1] == "pi" else math.e)
    if k == "neg":
        return -evaluate(node[1], env)
    if k in ("add", "sub", "mul", "div", "pow"):
        a, b = evaluate(node[1], env), evaluate(node[2], env)
        if k == "add":
            r = a + b
        elif k == "sub":
            r = a - b
        elif k == "mul":
            r = a * b
        elif k == "div":
            if b == 0:
                raise ZeroDivisionError
            r = a / b
        else:
            r = _pow(a, b)
        if not (math.isfinite(r.real) and math.isfinite(r.imag)):
            raise OverflowError
        return r
    if k == "fn":
        return _f(node[1], evaluate(node[2], env))
    if k == "logb":
        b = evaluate(node[1], env)
        lb = cmath.log(b) if b != 0 else 0
        if lb == 0:
            raise ZeroDivisionError
        return cmath.log(evaluate(node[2], env)) / lb
    if k == "abs":
        return complex(abs(evaluate(node[1], env)))
    raise ValueError(k)


def evaluate_mp(node, ctx: mpmath.MPContext):
    """High-precision evaluation of a constant (variable-free) AST with an mpmath context."""
    k = node[0]
    if k == "num":
        return ctx.mpf(node[1].numerator) / node[1].denominator
    if k == "const":
        return +ctx.pi if node[1] == "pi" else ctx.e
    if k == "neg":
        return -evaluate_mp(node[1], ctx)
    if k in ("add", "sub", "mul", "div", "pow"):
        a, b = evaluate_mp(node[1], ctx), evaluate_mp(node[2], ctx)
        if k == "add":
            return a + b
        if k == "sub":
            return a - b
        if k == "mul":
            return a * b
        if k == "div":
            if b == 0:
                raise ZeroDivisionError
            return a / b
        if a == 0 and ctx.re(b) <= 0:
            raise ZeroDivisionError
        return ctx.power(a, b)
    if k == "fn":
        a = evaluate_mp(node[2], ctx)
        name = node[1]
        if name == "log" and a == 0:
            raise ZeroDivisionError
        if name == "abs":
            return abs(a)
        return {"sin": ctx.sin, "cos": ctx.cos, "tan": ctx.tan, "exp": ctx.exp, "log": ctx.log, "sqrt": ctx.sqrt}[name](a)
    if k == "logb":
        b, a = evaluate_mp(node[1], ctx), evaluate_mp(node[2], ctx)
        lb = ctx.log(b)
        if lb == 0:
            raise ZeroDivisionError
        return ctx.log(a) / lb
    if k == "abs":
        return abs(evaluate_mp(node[1], ctx))
    raise ValueError(k)


def free_vars(node) -> set[str]:
    k = node[0]
    if k == "var":
        return {node[1]}
    if k in ("num", "const"):
        return set()
    out: set[str] = set()
    for child in node[1:]:
        if isinstance(child, tuple):
            out |= free_vars(child)
    return out


def has_decimal(node) -> bool:
    if node[0] == "num":
        return bool(node[2])
    return any(isinstance(c, tuple) and has_decimal(c) for c in node[1:])


def _guard(node):
    """Reject constant sub-expressions that are huge (bounded work everywhere afterwards)."""
    k = node[0]
    for child in node[1:]:
        if isinstance(child, tuple):
            _guard(child)
    if k == "pow":
        e = node[2]
        if not free_vars(e):
            try:
                ev = evaluate(e)
            except (ZeroDivisionError, OverflowError, ValueError):
                raise ParseError("That power can't be evaluated.") from None
            if abs(ev) > MAX_EXPONENT:
                raise ParseError("That power is far too large to be a sensible answer.")
    if not free_vars(node):
        try:
            v = evaluate(node)
        except ZeroDivisionError:
            raise ParseError("That answer divides by zero (or takes the log of zero).") from None
        except (OverflowError, ValueError):
            raise ParseError("That number is far too large to be a sensible answer.") from None
        if abs(v) > MAX_MAGNITUDE:
            raise ParseError("That number is far too large to be a sensible answer.")


def parse_ast(text: str, allowed_vars: tuple[str, ...] = DEFAULT_VARS, normalised: bool = False):
    s = text if normalised else normalise(text)
    if not s:
        raise ParseError("empty answer")
    if len(s) > MAX_CHARS:
        raise ParseError("That answer is too long to read. Give just the final answer.")
    ast = _Parser(tokenize(s, allowed_vars)).parse()
    _guard(ast)
    return ast


# ------------------------------------------------------------- rendering ---
_PREC = {"add": 1, "sub": 1, "neg": 2, "mul": 3, "div": 3, "pow": 5}


def _num_latex(v: Fraction, decimal: bool, text: str | None = None) -> str:
    if v.denominator == 1:
        return str(v.numerator)
    if decimal:
        s = f"{float(v):.12f}".rstrip("0").rstrip(".")
        return s
    return f"\\frac{{{v.numerator}}}{{{v.denominator}}}"


def to_latex(node, parent: int = 0) -> str:
    k = node[0]
    if k == "num":
        return _num_latex(node[1], node[2])
    if k == "var":
        return node[1]
    if k == "const":
        return "\\pi" if node[1] == "pi" else "e"
    if k == "neg":
        s = "-" + to_latex(node[1], 2)
        return f"\\left({s}\\right)" if parent > 2 else s
    if k in ("add", "sub"):
        a = to_latex(node[1], 1)
        b = to_latex(node[2], 2 if k == "sub" else 1)
        s = f"{a} {'+' if k == 'add' else '-'} {b}"
        return f"\\left({s}\\right)" if parent > 1 else s
    if k == "mul":
        a, b = to_latex(node[1], 2), to_latex(node[2], 3)
        sep = " \\times " if node[2][0] == "num" or (node[2][0] == "pow" and node[2][1][0] == "num") else " "
        s = f"{a}{sep}{b}"
        return f"\\left({s}\\right)" if parent > 3 else s
    if k == "div":
        return f"\\frac{{{to_latex(node[1])}}}{{{to_latex(node[2])}}}"
    if k == "pow":
        base = to_latex(node[1], 6)
        return f"{base}^{{{to_latex(node[2])}}}"
    if k == "fn":
        name, a = node[1], node[2]
        if name == "sqrt":
            return f"\\sqrt{{{to_latex(a)}}}"
        if name == "abs":
            return f"\\left|{to_latex(a)}\\right|"
        if name == "exp":
            return f"e^{{{to_latex(a)}}}"
        cmd = {"log": "\\ln", "sin": "\\sin", "cos": "\\cos", "tan": "\\tan"}[name]
        return f"{cmd}\\left({to_latex(a)}\\right)"
    if k == "logb":
        return f"\\log_{{{to_latex(node[1])}}}\\left({to_latex(node[2])}\\right)"
    if k == "abs":
        return f"\\left|{to_latex(node[1])}\\right|"
    return "?"


def to_text(node, parent: int = 0) -> str:
    """Plain calculator-style rendering of how the answer was read."""
    k = node[0]
    if k == "num":
        v = node[1]
        if v.denominator == 1:
            return str(v.numerator)
        if node[2]:
            return f"{float(v):.12f}".rstrip("0").rstrip(".")
        s = f"{v.numerator}/{v.denominator}"
        return f"({s})" if parent >= 3 else s
    if k == "var":
        return node[1]
    if k == "const":
        return node[1]
    if k == "neg":
        s = "-" + to_text(node[1], 2)
        return f"({s})" if parent > 2 else s
    if k in ("add", "sub"):
        s = f"{to_text(node[1], 1)} {'+' if k == 'add' else '-'} {to_text(node[2], 2 if k == 'sub' else 1)}"
        return f"({s})" if parent > 1 else s
    if k in ("mul", "div"):
        s = f"{to_text(node[1], 2 if k == 'mul' else 3)}{'*' if k == 'mul' else '/'}{to_text(node[2], 4 if k == 'div' else 3)}"
        return f"({s})" if parent > 3 else s
    if k == "pow":
        return f"{to_text(node[1], 6)}^{to_text(node[2], 6)}"
    if k == "fn":
        return f"{'ln' if node[1] == 'log' else node[1]}({to_text(node[2])})"
    if k == "logb":
        return f"log_{to_text(node[1], 6)}({to_text(node[2])})"
    if k == "abs":
        return f"|{to_text(node[1])}|"
    return "?"


def to_sympy(node):
    """Convert a guarded AST to SymPy (only after :func:`parse_ast` has checked the limits)."""
    import sympy as sp

    k = node[0]
    if k == "num":
        return sp.Rational(node[1].numerator, node[1].denominator)
    if k == "var":
        return sp.Symbol(node[1])
    if k == "const":
        return sp.pi if node[1] == "pi" else sp.E
    if k == "neg":
        return -to_sympy(node[1])
    a = to_sympy(node[1]) if isinstance(node[1], tuple) else None
    if k in ("add", "sub", "mul", "div", "pow"):
        b = to_sympy(node[2])
        return {"add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b, "div": lambda: a / b, "pow": lambda: a ** b}[k]()
    if k == "fn":
        arg = to_sympy(node[2])
        return {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt, "abs": sp.Abs}[node[1]](arg)
    if k == "logb":
        return sp.log(to_sympy(node[2])) / sp.log(a)
    if k == "abs":
        return sp.Abs(a)
    raise ValueError(k)
