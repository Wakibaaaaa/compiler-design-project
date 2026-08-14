"""
compiler.py
Implements the 6 classic phases of a compiler for a small expression language:

    identifier = expression
    expression := term (('+'|'-') term)*
    term       := factor (('*'|'/') factor)*
    factor     := IDENTIFIER | NUMBER | '(' expression ')'

Example valid program:
    x = a + b
    y = x * 10
    z = y + 5
"""

import re

# ---------------------------------------------------------------------------
# PHASE 1: LEXICAL ANALYSIS
# ---------------------------------------------------------------------------
# Converts raw source text into a stream of tokens.

TOKEN_SPEC = [
    ("NUMBER",   r"\d+(\.\d+)?"),
    ("ID",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("ASSIGN",   r"="),
    ("PLUS",     r"\+"),
    ("MINUS",    r"-"),
    ("MUL",      r"\*"),
    ("DIV",      r"/"),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("SEMI",     r";"),
    ("SKIP",     r"[ \t]+"),
    ("MISMATCH", r"."),   # anything else = lexical error
]

MASTER_REGEX = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

KEYWORDS = set()  # reserved for future extension (if/while etc.)


class Token:
    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.col})"

    def to_dict(self):
        return {"type": self.type, "value": self.value, "line": self.line, "col": self.col}


class LexicalError(Exception):
    def __init__(self, message, line, col, char):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.char = char


def tokenize(source, collect_errors=False):
    """
    Turns source code into a list of Token objects.
    If collect_errors=True, lexical errors are gathered into a list instead of
    raising immediately (used by the error-analysis module).
    Returns (tokens, lexical_errors, symbol_table)
    """
    tokens = []
    lexical_errors = []
    symbol_table = {}  # identifier -> first line seen

    lines = source.split("\n")
    for line_no, line_text in enumerate(lines, start=1):
        col = 1
        pos = 0
        while pos < len(line_text):
            match = MASTER_REGEX.match(line_text, pos)
            if not match:
                # Should not happen because MISMATCH catches everything,
                # but guard just in case.
                break
            kind = match.lastgroup
            value = match.group()
            start_col = pos + 1

            if kind == "SKIP":
                pass
            elif kind == "MISMATCH":
                err = LexicalError(
                    f"Unrecognized character '{value}'", line_no, start_col, value
                )
                if collect_errors:
                    lexical_errors.append(err)
                else:
                    raise err
            else:
                tok = Token(kind, value, line_no, start_col)
                tokens.append(tok)
                if kind == "ID" and value not in symbol_table:
                    symbol_table[value] = {"line": line_no, "type": "identifier"}

            pos = match.end()
            col = pos + 1

        tokens.append(Token("NEWLINE", "\\n", line_no, col))

    tokens.append(Token("EOF", "", len(lines) + 1, 1))
    return tokens, lexical_errors, symbol_table


# ---------------------------------------------------------------------------
# PHASE 2: SYNTAX ANALYSIS
# ---------------------------------------------------------------------------
# A recursive-descent parser that builds an Abstract Syntax Tree (AST).
# Grammar:
#   program    := statement*
#   statement  := ID ASSIGN expr (SEMI)? NEWLINE
#   expr       := term (( PLUS | MINUS ) term)*
#   term       := factor (( MUL | DIV ) factor)*
#   factor     := ID | NUMBER | LPAREN expr RPAREN

class ASTNode:
    """Generic AST node used for all constructs."""
    def __init__(self, kind, value=None, children=None, line=None):
        self.kind = kind          # e.g. 'Assign', 'BinOp', 'Id', 'Num'
        self.value = value        # e.g. '+', variable name, number
        self.children = children or []
        self.line = line

    def to_dict(self):
        return {
            "kind": self.kind,
            "value": self.value,
            "line": self.line,
            "children": [c.to_dict() for c in self.children],
        }


class SyntaxError_(Exception):
    def __init__(self, message, token):
        super().__init__(message)
        self.message = message
        self.token = token


def describe_token(tok):
    """Human-readable label for a token, used in error messages."""
    if tok.type == "NEWLINE":
        return "end of line"
    if tok.type == "EOF":
        return "end of file"
    return f"'{tok.value}'"


class Parser:
    """
    Standard parser. Used directly (raises on first error) by the
    6-Phases module. The Error-Analysis module uses PanicModeParser instead
    (see error_analysis.py) which reuses this grammar but recovers from errors.
    """
    def __init__(self, tokens):
        # Filter out NEWLINE tokens is NOT done here on purpose: statements
        # are separated by NEWLINE, so we need them to know where one ends.
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, type_):
        tok = self.peek()
        if tok.type != type_:
            raise SyntaxError_(
                f"Expected {type_} but found {describe_token(tok)}", tok
            )
        return self.advance()

    def skip_blank_lines(self):
        while self.peek().type == "NEWLINE":
            self.advance()

    def parse_program(self):
        statements = []
        self.skip_blank_lines()
        while self.peek().type != "EOF":
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
            self.skip_blank_lines()
        return ASTNode("Program", children=statements)

    def parse_statement(self):
        id_tok = self.expect("ID")
        self.expect("ASSIGN")
        expr = self.parse_expr()
        # optional semicolon
        if self.peek().type == "SEMI":
            self.advance()
        # must end at NEWLINE or EOF
        if self.peek().type not in ("NEWLINE", "EOF"):
            bad = self.peek()
            raise SyntaxError_(
                f"Unexpected token {describe_token(bad)} after expression", bad
            )
        return ASTNode("Assign", value=id_tok.value,
                        children=[ASTNode("Id", value=id_tok.value, line=id_tok.line), expr],
                        line=id_tok.line)

    def parse_expr(self):
        node = self.parse_term()
        while self.peek().type in ("PLUS", "MINUS"):
            op_tok = self.advance()
            right = self.parse_term()
            node = ASTNode("BinOp", value=op_tok.value, children=[node, right], line=op_tok.line)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.peek().type in ("MUL", "DIV"):
            op_tok = self.advance()
            right = self.parse_factor()
            node = ASTNode("BinOp", value=op_tok.value, children=[node, right], line=op_tok.line)
        return node

    def parse_factor(self):
        tok = self.peek()
        if tok.type == "NUMBER":
            self.advance()
            return ASTNode("Num", value=tok.value, line=tok.line)
        elif tok.type == "ID":
            self.advance()
            return ASTNode("Id", value=tok.value, line=tok.line)
        elif tok.type == "LPAREN":
            self.advance()
            node = self.parse_expr()
            self.expect("RPAREN")
            return node
        else:
            raise SyntaxError_(
                f"Expected identifier, number, or '(' but found {describe_token(tok)}", tok
            )


# ---------------------------------------------------------------------------
# PHASE 3: SEMANTIC ANALYSIS
# ---------------------------------------------------------------------------
# This language has no "declare"/"input" statement, so a variable's first
# appearance on the RIGHT-hand side of "=" (before it's ever been assigned)
# is treated as an implicit INPUT variable -- not an error. That mirrors how
# x = a + b is meant to work: a and b are inputs supplied to the program.
#
# What genuinely IS a semantic error in this language:
#   1. Division by a literal constant 0        (e.g. z = a / 0)
#   2. Using a variable on the left of "=" is always fine (any name can be
#      (re)computed), so redefinition itself is NOT an error.
#
# Semantic analysis also builds a symbol table that classifies every
# variable as INPUT (never assigned, only read) or COMPUTED (assigned by
# some statement), which is genuinely useful "semantic processing" to show
# your teacher.

class SemanticError_(Exception):
    def __init__(self, message, line):
        super().__init__(message)
        self.message = message
        self.line = line


def analyze_semantics(ast, collect_errors=False):
    """
    Walks the AST. Returns (annotated_info, semantic_errors)
    """
    computed = set()   # variables that appear on the LHS of some assignment
    referenced = set()  # every variable ever read on a RHS
    semantic_errors = []
    trace = []

    def check_expr(node, target_line):
        if node.kind == "Id":
            referenced.add(node.value)
            role = "computed (already assigned earlier)" if node.value in computed else "input (used as a free variable)"
            trace.append(f"Line {node.line}: '{node.value}' treated as {role} -- OK")
        elif node.kind == "Num":
            pass
        elif node.kind == "BinOp":
            check_expr(node.children[0], target_line)
            check_expr(node.children[1], target_line)
            # Real semantic check: division by the literal constant 0
            if node.value == "/" and node.children[1].kind == "Num" and float(node.children[1].value) == 0:
                err = SemanticError_(
                    f"Division by zero: the divisor is the constant 0", node.line
                )
                if collect_errors:
                    semantic_errors.append(err)
                else:
                    raise err

    for stmt in ast.children:
        var_name = stmt.value
        expr_node = stmt.children[1]
        check_expr(expr_node, stmt.line)
        computed.add(var_name)
        trace.append(f"Line {stmt.line}: '{var_name}' is now COMPUTED (assigned a value)")

    input_vars = sorted(referenced - computed)
    computed_vars = sorted(computed)

    return {
        "input_variables": input_vars,
        "computed_variables": computed_vars,
        "trace": trace,
        "semantic_tree": ast.to_dict(),
    }, semantic_errors


# =============================================================================
# TEXTBOOK ENGINE -- adapted from the user's own compiler code (Part A)
# =============================================================================
# This section preserves the user's original lexical/syntax/semantic/3AC/
# optimization/target-code logic almost exactly as written. The only real
# changes made:
#   1. Functions that used to print() their output now RETURN strings/data
#      instead, since a Flask API needs data, not console text.
#   2. A thin multi-statement wrapper (compile_program) was added at the
#      bottom, because the original parser only ever handled ONE
#      "identifier = expression" line per call. It now loops over each
#      non-blank line of the submitted program, reusing the user's exact
#      per-statement pipeline for each one, while sharing the symbol tables
#      across the whole program (so identifiers/constants get one consistent
#      numbering scheme across all statements).
#   3. Minimal, clearly-flagged error handling was added, because the
#      original code had none: unrecognized characters were silently
#      discarded, and a malformed statement would crash with a raw
#      traceback. Both now raise the same LexicalError / SyntaxError_ /
#      SemanticError_ exceptions used elsewhere in this project, so the API
#      can report them cleanly instead of crashing.
#   4. One real semantic rule was added -- division by the literal constant
#      0 -- since the original code performed a type-coercion ACTION
#      (inttofloat) but never actually checked for an invalid program.

# ------------------------------------------------------------
# GLOBAL SYMBOL TABLES (as in the original)
# ------------------------------------------------------------
identifier_table = {}
operator_table = {}
constant_table = {}
punctuation_table = {}


def add_to_table(table, key):
    if key not in table:
        table[key] = len(table) + 1
    return table[key]


def reset_tables():
    identifier_table.clear()
    operator_table.clear()
    constant_table.clear()
    punctuation_table.clear()


# ------------------------------------------------------------
# PRE-LEXICAL & LEXICAL ANALYSIS (unchanged from the user's code)
# ------------------------------------------------------------
TOKEN_REGEX = r'''
    (?P<NUM>\d+\.?\d*) |
    (?P<ID>[a-zA-Z_][a-zA-Z0-9_]*) |
    (?P<OP>==|!=|<=|>=|[+\-*/=<>]) |
    (?P<PUNCT>[;(),{}]) |
    (?P<SKIP>\s+) |
    (?P<BAD>.)
'''


def lexical_analysis(source):
    tokens = []
    token_stream_display = []
    for mo in re.finditer(TOKEN_REGEX, source, re.VERBOSE):
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'SKIP' or kind == 'BAD':
            continue
        elif kind == 'ID':
            n = add_to_table(identifier_table, value)
            rep = f"<id,{n}>"
        elif kind == 'NUM':
            n = add_to_table(constant_table, value)
            rep = f"<c,{n}>"
        elif kind == 'OP':
            n = add_to_table(operator_table, value)
            rep = f"<op,{n}>"
        elif kind == 'PUNCT':
            n = add_to_table(punctuation_table, value)
            rep = f"<p,{n}>"
        tokens.append((kind, value, rep))
        token_stream_display.append(rep)
    return tokens, token_stream_display


def find_bad_characters(line_text):
    """
    Addition: the original lexer silently discarded unrecognized characters.
    This scans a line and returns a list of (char, column) for anything the
    lexer wouldn't understand, so it can be reported instead of vanishing.
    """
    bad = []
    for mo in re.finditer(TOKEN_REGEX, line_text, re.VERBOSE):
        if mo.lastgroup == 'BAD':
            bad.append((mo.group(), mo.start() + 1))
    return bad


# ------------------------------------------------------------
# AST NODE (unchanged)
# ------------------------------------------------------------
class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right


# ------------------------------------------------------------
# ASCII TREE RENDERER (logic unchanged -- now returns a string
# instead of printing, so it can be sent to the browser)
# ------------------------------------------------------------
def render_ascii_tree(node):
    lines, _, _, _ = _build_classic_tree(node)
    return "\n".join(lines)


def _build_classic_tree(node):
    if node is None:
        return [], 0, 0, 0
    val = str(node.value)
    if val in ('=', '+', '-', '*', '/'):
        val = f"({val})"

    if node.left and not node.right:
        c_lines, c_pos, c_w, c_h = _build_classic_tree(node.left)
        val_w = len(val)
        if c_pos >= val_w // 2:
            val_pad = c_pos - val_w // 2
            child_pad = 0
            root_pos = c_pos
        else:
            val_pad = 0
            child_pad = (val_w // 2) - c_pos
            root_pos = val_w // 2
        top_line = " " * val_pad + val
        pipe_line = " " * root_pos + "|"
        padded_c_lines = [" " * child_pad + line for line in c_lines]
        all_lines = [top_line, pipe_line] + padded_c_lines
        width = max(len(l) for l in all_lines)
        return all_lines, root_pos, width, len(all_lines)

    if not node.left and not node.right:
        val_w = len(val)
        pos = val_w // 2
        return [val], pos, val_w, 1

    l_lines, l_pos, l_w, l_h = _build_classic_tree(node.left)
    r_lines, r_pos, r_w, r_h = _build_classic_tree(node.right)
    gap = 1
    r_root_idx = l_w + gap + r_pos
    root_pos = (l_pos + r_root_idx) // 2
    val_w = len(val)
    offset = 0
    if root_pos < val_w // 2:
        offset = (val_w // 2) - root_pos
        root_pos = val_w // 2
    l_pos += offset
    r_root_idx += offset
    top_line = " " * (root_pos - val_w // 2) + val
    max_len = max(len(top_line), r_root_idx + 1)
    branch_chars = [" "] * max_len
    branch_chars[l_pos] = "/"
    branch_chars[r_root_idx] = "\\"
    branch_line = "".join(branch_chars)
    max_h = max(l_h, r_h)
    combined_lines = []
    for i in range(max_h):
        l_str = l_lines[i] if i < l_h else " " * l_w
        r_str = r_lines[i] if i < r_h else " " * r_w
        l_str = " " * offset + l_str.ljust(l_w)
        combined_lines.append(l_str + " " * gap + r_str)
    all_lines = [top_line, branch_line] + combined_lines
    width = max(len(l) for l in all_lines)
    return all_lines, root_pos, width, len(all_lines)


# ------------------------------------------------------------
# PARSER (Syntax Analysis) -- unchanged grammar/logic
# ------------------------------------------------------------
class SixPhaseParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None, None)

    def consume(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self):
        idtok = self.consume()
        eqtok = self.consume()
        expr = self.parse_expr()
        return Node(f"({eqtok[1]})", Node(idtok[2]), expr)

    def parse_expr(self):
        node = self.parse_term()
        while self.peek()[1] in ('+', '-'):
            op = self.consume()
            right = self.parse_term()
            node = Node(f"({op[1]})", node, right)
        return node

    def parse_term(self):
        node = self.parse_factor()
        while self.peek()[1] in ('*', '/'):
            op = self.consume()
            right = self.parse_factor()
            node = Node(f"({op[1]})", node, right)
        return node

    def parse_factor(self):
        tok = self.consume()
        if tok[1] == '(':
            node = self.parse_expr()
            self.consume()
            return node
        if tok[0] == 'NUM':
            return Node(tok[1])
        return Node(tok[2])


# ------------------------------------------------------------
# SEMANTIC ANALYSIS (inttofloat wrapper) -- unchanged
# ------------------------------------------------------------
def semantic_analysis(node):
    if node is None:
        return None
    if node.left is None and node.right is None:
        val = str(node.value)
        if val.isdigit() or val.replace('.', '', 1).isdigit():
            wrapper = Node("inttofloat")
            wrapper.left = Node(val)
            return wrapper
        return node
    node.left = semantic_analysis(node.left)
    node.right = semantic_analysis(node.right)
    return node


def deep_copy_tree(node):
    if node is None:
        return None
    new_n = Node(node.value)
    new_n.left = deep_copy_tree(node.left)
    new_n.right = deep_copy_tree(node.right)
    return new_n


def check_division_by_zero(node, line_no):
    """
    Addition: the user's code had no semantic error detection at all.
    This walks the syntax tree looking for the one clear, real semantic
    error possible in this grammar: dividing by the literal constant 0.
    """
    if node is None or (node.left is None and node.right is None):
        return
    if node.value == "(/)" and node.right is not None:
        if node.right.left is None and node.right.right is None:
            rv = str(node.right.value)
            if rv.replace('.', '', 1).isdigit() and float(rv) == 0:
                raise SemanticError_("Division by zero: the divisor is the constant 0", line_no)
    check_division_by_zero(node.left, line_no)
    check_division_by_zero(node.right, line_no)


# ------------------------------------------------------------
# INTERMEDIATE CODE GENERATION (Bottom-Up 3AC) -- unchanged
# ------------------------------------------------------------
class BottomUpTACGen:
    def __init__(self):
        self.code = []
        self.steps = []
        self.cnt = 0

    def new_temp(self):
        self.cnt += 1
        return f"t{self.cnt}"

    def generate_bottom_up(self, node):
        self.post_order_traverse(node)
        return self.code, self.steps

    def post_order_traverse(self, node):
        if node is None:
            return None
        if node.left is None and node.right is None:
            return node.value
        if node.value == "inttofloat":
            child_val = self.post_order_traverse(node.left)
            t = self.new_temp()
            line = f"{t} = inttofloat({child_val})"
            step_desc = f"Subtree [inttofloat -> {child_val}] => Op: inttofloat | Result: {t}"
            self.code.append(line)
            self.steps.append((step_desc, line))
            return t
        if node.value == "(=)":
            left_operand = self.post_order_traverse(node.left)
            right_operand = self.post_order_traverse(node.right)
            line = f"{left_operand} = {right_operand}"
            step_desc = f"Root Assignment [ {left_operand} = {right_operand} ] => Final Store"
            self.code.append(line)
            self.steps.append((step_desc, line))
            return left_operand
        left_operand = self.post_order_traverse(node.left)
        right_operand = self.post_order_traverse(node.right)
        t = self.new_temp()
        op_symbol = node.value.strip("()")
        line = f"{t} = {left_operand} {op_symbol} {right_operand}"
        step_desc = f"Subtree [ {left_operand} {op_symbol} {right_operand} ] => Op: {op_symbol} in middle | Result: {t}"
        self.code.append(line)
        self.steps.append((step_desc, line))
        return t


# ------------------------------------------------------------
# CODE OPTIMIZATION -- unchanged
# ------------------------------------------------------------
def optimize(code):
    optimized = []
    replace_map = {}
    for line in code:
        m = re.match(r"(t\d+) = inttofloat\((\d+)\)", line)
        if m:
            temp, num = m.group(1), m.group(2)
            replace_map[temp] = num + ".0"
            continue
        new_line = line
        for k, v in replace_map.items():
            new_line = re.sub(rf"\b{k}\b", v, new_line)
        optimized.append(new_line)
    return optimized


# ------------------------------------------------------------
# TARGET CODE GENERATION (Assembly) -- unchanged
# ------------------------------------------------------------
def generate_target_code_textbook(optimized_code):
    asm = []
    reg_cnt = 0
    temp_reg = {}

    def get_reg():
        nonlocal reg_cnt
        reg_cnt += 1
        return f"R{reg_cnt}"

    for line in optimized_code:
        m = re.match(r"(\S+) = (\S+) ([+\-*/]) (\S+)", line)
        if m:
            dest, a, op, b = m.groups()
            op_map = {'+': 'ADDF', '-': 'SUBF', '*': 'MULF', '/': 'DIVF'}
            asm_op = op_map[op]
            if a in temp_reg:
                ra = temp_reg[a]
            else:
                ra = get_reg()
                asm.append(f"LDF {ra}, {a}")
            if b in temp_reg:
                rb = temp_reg[b]
                asm.append(f"{asm_op:<5} {ra}, {ra}, {rb}")
            elif re.match(r"^\d", b):
                asm.append(f"{asm_op:<5} {ra}, {ra}, #{b}")
            else:
                rb = get_reg()
                asm.append(f"LDF {rb}, {b}")
                asm.append(f"{asm_op:<5} {ra}, {ra}, {rb}")
            temp_reg[dest] = ra
            continue
        m2 = re.match(r"(\S+) = (\S+)$", line)
        if m2:
            dest, src = m2.groups()
            if src in temp_reg:
                asm.append(f"STF {dest}, {temp_reg[src]}")
            else:
                r = get_reg()
                asm.append(f"LDF {r}, {src}")
                asm.append(f"STF {dest}, {r}")
            continue
    return asm


# ------------------------------------------------------------
# Small helper so syntax errors carry the same shape (.line/.col/.value)
# that the rest of the project's SyntaxError_ handling expects
# ------------------------------------------------------------
class _FakeToken:
    def __init__(self, line, col, value):
        self.line = line
        self.col = col
        self.value = value
        self.type = "OTHER"  # so app.py's NEWLINE/EOF display checks don't crash


# ------------------------------------------------------------
# MULTI-STATEMENT WRAPPER (new -- the piece that was missing)
# ------------------------------------------------------------
def compile_program(source):
    """
    Runs the user's original per-statement 6-phase pipeline once for every
    non-blank line of the submitted program, sharing symbol tables across
    all of them. Raises LexicalError / SyntaxError_ / SemanticError_ on the
    first problem found (same contract as before, used by app.py).
    """
    reset_tables()
    lines = source.split("\n")

    # Pass 1: scan the WHOLE program for lexical errors and build the full
    # token stream + symbol tables (this also gives Phase 1 its combined view)
    combined_stream = []
    for line_no, line_text in enumerate(lines, start=1):
        if not line_text.strip():
            continue
        bad_chars = find_bad_characters(line_text)
        if bad_chars:
            char, col = bad_chars[0]
            raise LexicalError(f"Unrecognized character '{char}'", line_no, col, char)
        _, stream = lexical_analysis(line_text)
        combined_stream.extend(stream)

    lexical_result = {
        "identifier_table": dict(identifier_table),
        "operator_table": dict(operator_table),
        "constant_table": dict(constant_table),
        "punctuation_table": dict(punctuation_table),
        "token_stream": " ".join(combined_stream),
    }

    # Pass 2: parse + run phases 2-6 one statement (one line) at a time
    statements = []
    for line_no, line_text in enumerate(lines, start=1):
        stripped = line_text.strip()
        if not stripped:
            continue

        tokens, _ = lexical_analysis(line_text)  # tables already built -> numbers match
        if len(tokens) < 3 or tokens[0][0] != 'ID' or tokens[1][1] != '=':
            raise SyntaxError_(
                f"Expected 'identifier = expression' but got: '{stripped}'",
                _FakeToken(line_no, 1, stripped),
            )

        try:
            parser = SixPhaseParser(tokens)
            syntax_tree = parser.parse()
        except Exception as ex:
            raise SyntaxError_(
                f"Could not parse statement '{stripped}': {ex}",
                _FakeToken(line_no, 1, stripped),
            )

        # Addition: the original parser has no bounds checking -- if an
        # expression runs out of tokens mid-way (e.g. "x = a +"), consume()
        # silently returns an empty placeholder instead of raising an error,
        # so a broken statement would otherwise be reported as successful.
        # Checking that the parser consumed EXACTLY the tokens available
        # (no more, no less) catches both incomplete expressions and
        # leftover/unexpected trailing tokens.
        if parser.pos > len(tokens):
            raise SyntaxError_(
                f"Incomplete expression in statement '{stripped}' -- expected another operand or a closing symbol.",
                _FakeToken(line_no, len(stripped) + 1, "<end of line>"),
            )
        if parser.pos < len(tokens):
            leftover = " ".join(t[1] for t in tokens[parser.pos:])
            raise SyntaxError_(
                f"Unexpected extra token(s) after a complete statement: '{leftover}'",
                _FakeToken(line_no, 1, leftover),
            )

        check_division_by_zero(syntax_tree.right, line_no)

        semantic_tree = deep_copy_tree(syntax_tree)
        if semantic_tree.right:
            semantic_tree.right = semantic_analysis(semantic_tree.right)

        tac_gen = BottomUpTACGen()
        tac_code, steps = tac_gen.generate_bottom_up(semantic_tree)
        opt_code = optimize(tac_code)
        asm = generate_target_code_textbook(opt_code)

        statements.append({
            "line_number": line_no,
            "source_line": stripped,
            "syntax_tree_ascii": render_ascii_tree(syntax_tree),
            "semantic_tree_ascii": render_ascii_tree(semantic_tree),
            "tac_steps": [{"description": desc, "line": ln} for desc, ln in steps],
            "tac_code": tac_code,
            "optimized_code": opt_code,
            "target_code": asm,
        })

    return {
        "success": True,
        "source": source,
        "lexical_analysis": lexical_result,
        "statements": statements,
    }


if __name__ == "__main__":
    import json
    test_source = "position = initial + rate * 60"
    print(json.dumps(compile_program(test_source), indent=2))