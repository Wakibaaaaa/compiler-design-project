from flask import Flask, jsonify, request
from flask_cors import CORS

from compiler import compile_program, LexicalError, SyntaxError_, SemanticError_
from error_analysis import run_error_analysis

app = Flask(__name__)
CORS(app)  # allows the frontend (opened as a file) to talk to this server


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)