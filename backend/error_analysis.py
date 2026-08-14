"""
error_analysis.py
A real panic-mode error-recovery system built on top of the SAME grammar
and lexer used in compiler.py (Part 1). This is NOT a simulation -- it is
an actual recursive-descent parser that:

  1. Detects lexical errors (bad characters) and keeps going.
  2. Detects syntax errors (grammar violations) and performs REAL
     panic-mode recovery: it discards tokens until it reaches a
     synchronization point, then resumes parsing from there.
  3. Runs semantic analysis (division-by-zero check) on whatever
     statements DID parse successfully.
  4. Never stops at the first error -- it keeps analyzing the whole
     program and reports everything it found.

Synchronization strategy used here:
    On a syntax error, skip tokens until the next NEWLINE (end of
    statement) or EOF. This is a natural choice for this grammar because
    every statement is exactly one line, so "end of statement" is a
    reliable, unambiguous place to resume parsing.
"""

from compiler import (
    tokenize, Parser, ASTNode, SyntaxError_,
    analyze_semantics, SemanticError_,
)


class PanicModeParser(Parser):
    """
    Extends the normal Parser (Part 1) but NEVER lets a syntax error stop
    the whole parse. Instead it records the error with full recovery
    details and resynchronizes at the next statement boundary.
    """
    def __init__(self, tokens):
        super().__init__(tokens)
        self.syntax_errors = []  # list of recovery-detail dicts

    def parse_program(self):
        statements = []
        self.skip_blank_lines()
        while self.peek().type != "EOF":
            try:
                stmt = self.parse_statement()
                statements.append(stmt)
            except SyntaxError_ as e:
                self._recover_from(e)
            self.skip_blank_lines()
        return ASTNode("Program", children=statements)

    def _recover_from(self, error):
        """
        PANIC MODE RECOVERY:
        1. The offending token is whatever self.peek() currently is
           (the parser stopped right where the grammar broke).
        2. We discard ("panic-skip") tokens one by one until we find a
           synchronization token: NEWLINE (end of statement) or EOF.
        3. We consume the synchronization token itself, so the main
           parse_program loop resumes cleanly at the start of the next
           statement.
        """
        bad_token = error.token
        skipped = []

        while self.peek().type not in ("NEWLINE", "EOF"):
            skipped.append(self.advance())

        sync_token = self.peek()
        if sync_token.type == "NEWLINE":
            sync_description = "End of statement (newline)"
            self.advance()  # consume the newline so we truly move past it
        else:
            sync_description = "End of file (EOF)"

        resumed_line = self.peek().line if self.peek().type != "EOF" else None

        readable_token = bad_token.value
        if bad_token.type == "NEWLINE":
            readable_token = "(end of line)"
        elif bad_token.type == "EOF":
            readable_token = "(end of file)"

        self.syntax_errors.append({
            "type": "Syntax Error",
            "line": bad_token.line,
            "column": bad_token.col,
            "offending_token": readable_token,
            "message": error.message,
            "recovery_method": "Panic mode",
            "skipped_tokens": [t.value for t in skipped],
            "synchronization_point": sync_description,
            "resumed_at_line": resumed_line,
        })


def run_error_analysis(source):
    """
    Runs the full error-analysis pipeline and returns a structured result
    matching the JSON shape the frontend expects.
    """
    all_errors = []

    # --- Step 1: Lexical analysis (collects errors instead of stopping) ---
    tokens, lexical_errors, symbol_table = tokenize(source, collect_errors=True)
    for err in lexical_errors:
        all_errors.append({
            "type": "Lexical Error",
            "line": err.line,
            "column": err.col,
            "offending_token": err.char,
            "message": err.message,
            "recovery_method": "Skip invalid character and continue scanning",
            "skipped_tokens": [err.char],
            "synchronization_point": "Next character",
            "resumed_at_line": err.line,
        })

    # --- Step 2: Syntax analysis WITH panic-mode recovery ---
    parser = PanicModeParser(tokens)
    ast = parser.parse_program()
    for err in parser.syntax_errors:
        all_errors.append(err)

    # --- Step 3: Semantic analysis on whatever parsed successfully ---
    semantic_info, semantic_errors = analyze_semantics(ast, collect_errors=True)
    for err in semantic_errors:
        all_errors.append({
            "type": "Semantic Error",
            "line": err.line,
            "column": None,
            "offending_token": None,
            "message": err.message,
            "recovery_method": "Reported, statement still counted",
            "skipped_tokens": [],
            "synchronization_point": None,
            "resumed_at_line": None,
        })

    # --- Sort all errors by line number for a clean chronological report ---
    all_errors.sort(key=lambda e: (e["line"] if e["line"] is not None else 0))

    # --- Number the errors and count by type ---
    for i, err in enumerate(all_errors, start=1):
        err["number"] = i

    lexical_count = sum(1 for e in all_errors if e["type"] == "Lexical Error")
    syntax_count = sum(1 for e in all_errors if e["type"] == "Syntax Error")
    semantic_count = sum(1 for e in all_errors if e["type"] == "Semantic Error")

    summary = {
        "total_errors": len(all_errors),
        "lexical_errors": lexical_count,
        "syntax_errors": syntax_count,
        "semantic_errors": semantic_count,
        # Recovery is considered successful because the parser reached
        # EOF and kept analyzing the whole program instead of aborting.
        "recovery_successful": True,
        "statements_successfully_parsed": len(ast.children),
    }

    return {
        "success": len(all_errors) == 0,
        "source": source,
        "errors": all_errors,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Quick manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json
    test_source = "x = a +\ny = b * 10\nz = (a + b\nw = c + d\n"
    result = run_error_analysis(test_source)
    print(json.dumps(result, indent=2))
