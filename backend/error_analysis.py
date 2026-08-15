"""
error_analysis.py

Implements REAL panic-mode error recovery on top of the same lexer and
grammar used in compiler.py. This is not a simulation -- it is an actual
recursive-descent parser that:

  1. Collects lexical errors instead of stopping at the first one.
  2. On a syntax error, enters "panic mode": it discards tokens one by one
     until it finds a synchronization token (end of statement: NEWLINE,
     SEMI, or EOF), then resumes parsing from the next statement.
  3. Runs semantic analysis (division-by-zero check) only on statements
     that were parsed successfully.
  4. Produces a structured report of every error and how it was recovered.

Synchronization strategy used here:
  Because this grammar is "one statement per line" (identifier = expression),
  the natural synchronization points are end-of-statement markers:
  NEWLINE, ';' (SEMI), or end of file (EOF). When an error occurs, the
  parser discards tokens until it sees one of these, then continues with
  the next statement. This is the classic panic-mode strategy described in
  the Dragon Book: skip tokens until a token from a "synchronizing set" is
  found.
"""

from compiler import (
    tokenize, Token, LexicalError,
    ASTNode, SyntaxError_, Parser,
    SemanticError_, analyze_semantics,
)

SYNCHRONIZING_TYPES = {"NEWLINE", "SEMI", "EOF"}


class PanicModeParser(Parser):
    """
    Extends the normal Parser but never stops at the first syntax error.
    Instead, each time an error is encountered while parsing a statement,
    it enters panic mode: skip tokens until a synchronizing token, then
    keep going with the next statement.
    """

    def __init__(self, tokens):
        super().__init__(tokens)
        self.errors = []          # list of structured error dicts
        self.statements = []      # successfully-parsed AST statement nodes

    def synchronize(self, error_token):
        """
        Panic-mode recovery: discard tokens starting at the point of error
        until a synchronizing token is found. Returns info about what was
        skipped and where parsing resumes.
        """
        skipped = []
        while self.peek().type not in SYNCHRONIZING_TYPES:
            skipped.append(self.advance())

        sync_token = self.peek()
        if sync_token.type in ("NEWLINE", "SEMI"):
            self.advance()  # consume the synchronizing token itself

        # Addition: look past any further blank/NEWLINE tokens to report the
        # line where the NEXT REAL statement actually begins, not just the
        # next raw token (which is often just another NEWLINE).
        peek_pos = self.pos
        while peek_pos < len(self.tokens) and self.tokens[peek_pos].type == "NEWLINE":
            peek_pos += 1
        resume_line = self.tokens[peek_pos].line if peek_pos < len(self.tokens) else self.peek().line

        return {
            "skipped_tokens": [t.value for t in skipped if t.type != "NEWLINE"],
            "synchronization_point": (
                "End of statement (newline)" if sync_token.type == "NEWLINE" else
                "Statement terminator ';'" if sync_token.type == "SEMI" else
                "End of file"
            ),
            "resumed_at_line": resume_line,
        }

    def parse_program_with_recovery(self):
        self.skip_blank_lines()
        while self.peek().type != "EOF":
            start_token = self.peek()
            try:
                stmt = self.parse_statement()
                self.statements.append(stmt)
            except SyntaxError_ as e:
                recovery_info = self.synchronize(e.token)
                token_display = e.token.value
                if e.token.type == "NEWLINE":
                    token_display = "<end of line>"
                elif e.token.type == "EOF":
                    token_display = "<end of file>"
                self.errors.append({
                    "type": "Syntax Error",
                    "line": start_token.line,
                    "column": e.token.col,
                    "offending_token": token_display,
                    "found_token": token_display,
                    "expected_token": e.expected or "N/A",
                    "message": e.message,
                    "recovery": "Panic mode",
                    **recovery_info,
                })
            self.skip_blank_lines()
        return ASTNode("Program", children=self.statements)


def run_error_analysis(source):
    """
    Full pipeline: lexical -> syntax (panic-mode) -> semantic, collecting
    every error along the way instead of stopping at the first one.
    Returns a structured dict matching the project's required JSON shape.
    """
    errors = []

    # Phase 1: Lexical analysis, collecting errors instead of raising
    tokens, lex_errors, symbol_table = tokenize(source, collect_errors=True)
    for e in lex_errors:
        errors.append({
            "type": "Lexical Error",
            "line": e.line,
            "column": e.col,
            "offending_token": e.char,
            "message": e.message,
            "recovery": "Skipped invalid character",
        })

    # Phase 2: Syntax analysis with panic-mode recovery
    parser = PanicModeParser(tokens)
    ast = parser.parse_program_with_recovery()
    errors.extend(parser.errors)

    # Phase 3: Semantic analysis, collecting errors, only on statements
    # that successfully parsed
    semantic_info, sem_errors = analyze_semantics(ast, collect_errors=True)
    for e in sem_errors:
        errors.append({
            "type": "Semantic Error",
            "line": e.line,
            "message": e.message,
            "recovery": "None (statement still counted, value may be undefined)",
        })

    errors.sort(key=lambda e: e["line"])
    for i, e in enumerate(errors, start=1):
        e["error_number"] = i

    lexical_count = sum(1 for e in errors if e["type"] == "Lexical Error")
    syntax_count = sum(1 for e in errors if e["type"] == "Syntax Error")
    semantic_count = sum(1 for e in errors if e["type"] == "Semantic Error")

    summary = {
        "total_errors": len(errors),
        "lexical_errors": lexical_count,
        "syntax_errors": syntax_count,
        "semantic_errors": semantic_count,
        "statements_successfully_parsed": len(parser.statements),
        "recovery_successful": True if len(errors) > 0 else None,
    }

    # Addition: list the source text of every statement that WAS parsed
    # successfully, so the report can show "Valid Statements: line 2, line 4"
    # the way a real compiler's error summary would.
    source_lines = source.split("\n")
    valid_statements = []
    for stmt in parser.statements:
        line_no = stmt.line
        text = source_lines[line_no - 1].strip() if 0 < line_no <= len(source_lines) else ""
        valid_statements.append({"line_number": line_no, "source_line": text})

    return {
        "success": len(errors) == 0,
        "source": source,
        "errors": errors,
        "summary": summary,
        "valid_statements": valid_statements,
        "partial_semantic_analysis": semantic_info if parser.statements else None,
    }


# ---------------------------------------------------------------------------
# Manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    test_source = "x = a +\ny = b * 10\nz = (a + b\nw = c + d\n"
    result = run_error_analysis(test_source)
    print(json.dumps(result, indent=2))