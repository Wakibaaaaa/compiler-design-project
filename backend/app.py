from flask import Flask, jsonify, request
from flask_cors import CORS

from compiler import compile_program, LexicalError, SyntaxError_, SemanticError_
from error_analysis import run_error_analysis
from grammar_tools import (
    run_derivation, run_parse_tree, run_ambiguity, GrammarError as GrammarErrorB,
)
from first_follow import run_first_follow, GrammarError as GrammarErrorC

# Serve the frontend folder directly, so this one Flask app is both the
# API and the website -- one URL, one thing to deploy, no CORS headaches.
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)  # harmless to keep even on a single origin; useful if you ever split them again


@app.route("/")
def home():
    return app.send_static_file("index.html")


@app.route("/debug-files")
def debug_files():
    import os
    try:
        files = os.listdir(app.static_folder)
    except Exception as e:
        files = [f"ERROR: {e}"]
    return jsonify({
        "static_folder_path": app.static_folder,
        "files_found": files,
        "cwd": os.getcwd(),
    })


@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"message": "Backend is alive!"})


@app.route("/api/compile", methods=["POST"])
def api_compile():
    """
    Runs the full 6-phase pipeline on the submitted source code.
    Expects JSON body: { "source": "x = a + b\\ny = x * 10" }
    On success: returns the full phase-by-phase breakdown.
    On failure: returns a clean single-error report (this endpoint is for
    demonstrating a CORRECT compilation; use /api/error-analysis for
    programs you expect to contain multiple errors).
    """
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")

    if not source.strip():
        return jsonify({"success": False, "error": {
            "type": "Input Error",
            "message": "No source code was provided. Please enter a program first.",
        }}), 400

    try:
        result = compile_program(source)
        return jsonify(result)

    except LexicalError as e:
        return jsonify({
            "success": False,
            "source": source,
            "error": {
                "type": "Lexical Error",
                "line": e.line,
                "column": e.col,
                "offending_token": e.char,
                "message": e.message,
            },
        }), 200

    except SyntaxError_ as e:
        token_display = e.token.value
        if e.token.type == "NEWLINE":
            token_display = "<end of line>"
        elif e.token.type == "EOF":
            token_display = "<end of file>"
        return jsonify({
            "success": False,
            "source": source,
            "error": {
                "type": "Syntax Error",
                "line": e.token.line,
                "column": e.token.col,
                "offending_token": token_display,
                "message": e.message,
            },
        }), 200

    except SemanticError_ as e:
        return jsonify({
            "success": False,
            "source": source,
            "error": {
                "type": "Semantic Error",
                "line": e.line,
                "message": e.message,
            },
        }), 200


@app.route("/api/error-analysis", methods=["POST"])
def api_error_analysis():
    """
    Runs the panic-mode error analysis pipeline: collects ALL lexical,
    syntax, and semantic errors instead of stopping at the first one.
    Expects JSON body: { "source": "x = a +\\ny = b * 10" }
    """
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")

    if not source.strip():
        return jsonify({"success": False, "error": {
            "type": "Input Error",
            "message": "No source code was provided. Please enter a program first.",
        }}), 400

    result = run_error_analysis(source)
    return jsonify(result)


# ---------------------------------------------------------------------------
# PART B: LMD / RMD / PARSE TREE / AMBIGUITY DETECTION
# ---------------------------------------------------------------------------
# All three endpoints expect JSON body:
#   { "grammar": "E -> E+E | a | b | c", "target": "a+b" }
# "grammar" is the raw text typed into the grammar textarea (one rule per
# line). "target" is the string to derive/analyze. Errors in the grammar
# or target (bad format, undefined symbols, etc.) come back as a normal
# 200 response with "success": false and a "message", the same pattern
# used by /api/compile above -- that way the frontend can just show the
# message instead of treating it as a network failure.

@app.route("/api/grammar/derive", methods=["POST"])
def api_grammar_derive():
    data = request.get_json(silent=True) or {}
    grammar_text = data.get("grammar", "")
    target = data.get("target", "")
    mode = data.get("mode", "leftmost")  # "leftmost" or "rightmost"

    try:
        result = run_derivation(grammar_text, target, mode=mode)
        return jsonify(result)
    except GrammarErrorB as e:
        return jsonify({"success": False, "message": str(e)}), 200


@app.route("/api/grammar/parse-tree", methods=["POST"])
def api_grammar_parse_tree():
    data = request.get_json(silent=True) or {}
    grammar_text = data.get("grammar", "")
    target = data.get("target", "")

    try:
        result = run_parse_tree(grammar_text, target)
        return jsonify(result)
    except GrammarErrorB as e:
        return jsonify({"success": False, "message": str(e)}), 200


@app.route("/api/grammar/ambiguity", methods=["POST"])
def api_grammar_ambiguity():
    data = request.get_json(silent=True) or {}
    grammar_text = data.get("grammar", "")
    target = data.get("target", "")

    try:
        result = run_ambiguity(grammar_text, target)
        return jsonify(result)
    except GrammarErrorB as e:
        return jsonify({"success": False, "message": str(e)}), 200


# ---------------------------------------------------------------------------
# PART C: FIRST & FOLLOW SET COMPUTATION
# ---------------------------------------------------------------------------
# Expects JSON body: { "grammar": "E -> T E'\nE' -> + T E' | eps\n..." }

@app.route("/api/first-follow", methods=["POST"])
def api_first_follow():
    data = request.get_json(silent=True) or {}
    grammar_text = data.get("grammar", "")

    try:
        result = run_first_follow(grammar_text)
        return jsonify(result)
    except GrammarErrorC as e:
        return jsonify({"success": False, "message": str(e)}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)