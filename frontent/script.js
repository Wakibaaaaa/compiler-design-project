// ============================================================
// CONFIG
// ============================================================
const API_BASE = "http://127.0.0.1:5000";

const PHASE_EXPLANATIONS = {
  lexical: "Converts the raw source text into a stream of tokens and classifies each one into its own table: identifiers, operators, constants, and punctuation — the classic textbook token-numbering scheme (<id,1>, <op,1>, etc.).",
  syntax: "Checks whether each statement follows the grammar and builds an Abstract Syntax Tree for it, rendered here as a real branching tree just like a compiler design textbook.",
  semantic: "Performs a real semantic transformation: any integer constant used in an expression is wrapped in an inttofloat() node, since arithmetic in this language is carried out in floating point.",
  intermediate: "Generates Three Address Code (3AC) using a bottom-up, post-order walk of the semantic tree — each subtree reduction produces one new instruction, shown here step by step.",
  optimization: "Improves the intermediate code by folding inttofloat(constant) directly into a floating-point literal (e.g. inttofloat(60) becomes 60.0), removing an unnecessary instruction.",
  target: "Converts the optimized code into register-based assembly instructions (LDF, STF, ADDF, SUBF, MULF, DIVF), allocating registers as it goes.",
};

const EXAMPLE_VALID = "position = initial + rate * 60";
const EXAMPLE_ERRORS = "x = a +\ny = b * 10\nz = (a + b\nw = c + d";

// ============================================================
// NAVIGATION
// ============================================================
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  window.scrollTo(0, 0);
}

document.getElementById("btn-go-phases").addEventListener("click", () => showScreen("phases-screen"));
document.getElementById("btn-go-errors").addEventListener("click", () => showScreen("errors-screen"));
document.querySelectorAll(".back-btn").forEach(btn => {
  btn.addEventListener("click", () => showScreen(btn.dataset.target));
});

// ============================================================
// TOAST
// ============================================================
let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
}

// ============================================================
// SMALL HELPERS
// ============================================================
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function codeBlock(text, copyable = true) {
  const id = "cb_" + Math.random().toString(36).slice(2, 9);
  const copyBtn = copyable ? `<button class="copy-btn" data-copy-target="${id}">Copy</button>` : "";
  return `<div class="code-block-wrap">${copyBtn}<div class="code-block" id="${id}">${escapeHtml(text)}</div></div>`;
}

// Copy-button handling (event delegation, works for dynamically added buttons)
document.addEventListener("click", (e) => {
  if (e.target.matches(".copy-btn")) {
    const targetId = e.target.dataset.copyTarget;
    const el = document.getElementById(targetId);
    if (el) {
      navigator.clipboard.writeText(el.textContent).then(() => showToast("Copied to clipboard"));
    }
  }
});

function renderTokenStream(streamStr) {
  if (!streamStr) return "<div class='empty-state'>No tokens.</div>";
  const chips = streamStr.split(" ").filter(Boolean);
  return `<div class="token-list">${chips.map(t => `<span class="token-chip">${escapeHtml(t)}</span>`).join("")}</div>`;
}

function renderSymbolTable(table, kind) {
  const headerNames = { id: "Identifier", op: "Operator", c: "Constant", p: "Symbol" };
  const entries = Object.entries(table || {});
  if (entries.length === 0) return "<div class='empty-state' style='padding:24px;'>(none)</div>";
  const rows = entries.map(([name, num]) => {
    const tokenText = `<${kind},${num}>`;
    return `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(tokenText)}</td></tr>`;
  }).join("");
  return `<table class="symbol-table">
    <thead><tr><th>${headerNames[kind] || "Symbol"}</th><th>Token</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderNotesList(notes) {
  if (!notes || notes.length === 0) return "";
  return `<ul class="notes-list">${notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>`;
}

// ============================================================
// PHASE CARD BUILDER
// ============================================================
function phaseCard(number, title, explanation, contentHtml) {
  return `
    <div class="phase-card">
      <div class="phase-header">
        <span class="phase-number">${number}</span>
        <span class="phase-title">${escapeHtml(title)}</span>
      </div>
      <div class="phase-explain">${escapeHtml(explanation)}</div>
      <div class="phase-content">${contentHtml}</div>
    </div>`;
}

function renderCompileResult(data) {
  let html = "";
  const lex = data.lexical_analysis;

  // Phase 1 -- shown once, covers the whole program
  html += phaseCard(1, "Lexical Analysis", PHASE_EXPLANATIONS.lexical, `
    <div class="subsection-label">Token Stream (whole program)</div>
    ${renderTokenStream(lex.token_stream)}
    <div class="subsection-label">Identifier Table</div>
    ${renderSymbolTable(lex.identifier_table, "id")}
    <div class="subsection-label">Operator Table</div>
    ${renderSymbolTable(lex.operator_table, "op")}
    <div class="subsection-label">Constant Table</div>
    ${renderSymbolTable(lex.constant_table, "c")}
    ${Object.keys(lex.punctuation_table || {}).length ? `<div class="subsection-label">Punctuation Table</div>${renderSymbolTable(lex.punctuation_table, "p")}` : ""}
  `);

  // Phases 2-6 -- shown once per statement, since each assignment produces
  // its own tree, 3AC sequence, and target code
  data.statements.forEach((stmt, i) => {
    const tag = `<div class="subsection-label" style="margin-top:0;">Statement ${i + 1}: <code>${escapeHtml(stmt.source_line)}</code> (line ${stmt.line_number})</div>`;

    html += phaseCard(2, `Syntax Analysis`, PHASE_EXPLANATIONS.syntax, `
      ${tag}
      ${codeBlock(stmt.syntax_tree_ascii)}
    `);

    html += phaseCard(3, `Semantic Analysis`, PHASE_EXPLANATIONS.semantic, `
      ${tag}
      ${codeBlock(stmt.semantic_tree_ascii)}
    `);

    html += phaseCard(4, `Intermediate Code (Three Address Code)`, PHASE_EXPLANATIONS.intermediate, `
      ${tag}
      <div class="subsection-label">Step-by-Step Bottom-Up Reduction</div>
      ${renderNotesList(stmt.tac_steps.map(s => `${s.description}  →  ${s.line}`))}
      <div class="subsection-label">Final 3AC</div>
      ${codeBlock(stmt.tac_code.join("\n"))}
    `);

    html += phaseCard(5, `Code Optimization`, PHASE_EXPLANATIONS.optimization, `
      ${tag}
      <div class="subsection-label">Original 3AC</div>
      ${codeBlock(stmt.tac_code.join("\n"))}
      <div class="subsection-label">Optimized Code</div>
      ${codeBlock(stmt.optimized_code.join("\n"))}
    `);

    html += phaseCard(6, `Target Code Generation`, PHASE_EXPLANATIONS.target, `
      ${tag}
      ${codeBlock(stmt.target_code.join("\n"))}
    `);
  });

  return html;
}

function renderCompileError(payload) {
  const err = payload.error;
  return `
    <div class="error-card">
      <div class="error-head">
        <span class="error-type-badge">${escapeHtml(err.type)}</span>
        ${err.line ? `<span class="error-line-tag">Line ${escapeHtml(err.line)}</span>` : ""}
      </div>
      <div class="error-body">
        <div class="error-message">${escapeHtml(err.message)}</div>
        <div class="error-detail-grid">
          ${err.offending_token !== undefined ? `<div><div class="detail-key">Offending token</div><div class="detail-val">${escapeHtml(err.offending_token)}</div></div>` : ""}
          ${err.column !== undefined ? `<div><div class="detail-key">Column</div><div class="detail-val">${escapeHtml(err.column)}</div></div>` : ""}
        </div>
      </div>
    </div>
    <p style="color: var(--text-muted); font-size: 13px; margin-top: 16px;">
      This module stops at the first error to demonstrate normal compilation.
      To see the compiler detect and recover from <em>multiple</em> errors, use
      the "Error Analysis — Panic Mode Recovery" workspace instead.
    </p>
  `;
}

// ============================================================
// ERROR ANALYSIS RENDERING
// ============================================================
function errorTypeClass(type) {
  if (type === "Lexical Error") return "type-lexical";
  if (type === "Semantic Error") return "type-semantic";
  return "type-syntax";
}

function renderErrorCard(err) {
  const detailRows = [];
  if (err.offending_token !== undefined) detailRows.push(["Offending token", err.offending_token]);
  if (err.column !== undefined) detailRows.push(["Column", err.column]);
  if (err.recovery !== undefined) detailRows.push(["Recovery", err.recovery]);
  if (err.synchronization_point !== undefined) detailRows.push(["Synchronization point", err.synchronization_point]);
  if (err.resumed_at_line !== undefined) detailRows.push(["Parser resumed at line", err.resumed_at_line]);
  if (err.skipped_tokens !== undefined) detailRows.push(["Skipped tokens", err.skipped_tokens.length ? err.skipped_tokens.join(", ") : "(none)"]);

  return `
    <div class="error-card ${errorTypeClass(err.type)}">
      <div class="error-head">
        <span class="error-num">#${err.error_number}</span>
        <span class="error-type-badge">${escapeHtml(err.type)}</span>
        <span class="error-line-tag">Line ${escapeHtml(err.line)}</span>
      </div>
      <div class="error-body">
        <div class="error-message">${escapeHtml(err.message)}</div>
        <div class="error-detail-grid">
          ${detailRows.map(([k, v]) => `<div><div class="detail-key">${escapeHtml(k)}</div><div class="detail-val">${escapeHtml(v)}</div></div>`).join("")}
        </div>
      </div>
    </div>
  `;
}

function renderErrorAnalysisResult(data) {
  const s = data.summary;
  let html = "";

  if (s.total_errors === 0) {
    html += `<div class="recovery-banner recovery-clean">✓ No errors found — this program is completely valid.</div>`;
  } else {
    html += `
      <div class="summary-bar">
        <div class="summary-stat stat-total"><div class="stat-num">${s.total_errors}</div><div class="stat-label">Total Errors</div></div>
        <div class="summary-stat stat-lex"><div class="stat-num">${s.lexical_errors}</div><div class="stat-label">Lexical</div></div>
        <div class="summary-stat stat-syntax"><div class="stat-num">${s.syntax_errors}</div><div class="stat-label">Syntax</div></div>
        <div class="summary-stat stat-semantic"><div class="stat-num">${s.semantic_errors}</div><div class="stat-label">Semantic</div></div>
      </div>
      <div class="recovery-banner recovery-success">
        ✓ Recovery successful — the parser continued past every error and finished analyzing all ${s.statements_successfully_parsed} valid statement(s).
      </div>
    `;
    html += data.errors.map(renderErrorCard).join("");
  }

  return html;
}

// ============================================================
// API CALL WRAPPER
// ============================================================
async function callApi(endpoint, source) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source }),
  });
  const data = await response.json();
  return { ok: response.ok, status: response.status, data };
}

// ============================================================
// 6 PHASES WORKSPACE WIRING
// ============================================================
const phasesInput = document.getElementById("phases-input");
const phasesOutput = document.getElementById("phases-output");
const phasesStatus = document.getElementById("phases-status");
const phasesRunBtn = document.getElementById("phases-run");

document.getElementById("phases-example").addEventListener("click", () => {
  phasesInput.value = EXAMPLE_VALID;
});
document.getElementById("phases-clear").addEventListener("click", () => {
  phasesInput.value = "";
  phasesOutput.innerHTML = `<div class="empty-state">Run a program to see the six phases appear here, one by one.</div>`;
  phasesStatus.textContent = "";
  phasesStatus.className = "status-line";
});

phasesRunBtn.addEventListener("click", async () => {
  const source = phasesInput.value;
  if (!source.trim()) {
    showToast("Please enter a program first");
    return;
  }

  phasesRunBtn.disabled = true;
  phasesStatus.textContent = "Compiling...";
  phasesStatus.className = "status-line status-loading";

  try {
    const { data } = await callApi("/api/compile", source);
    if (data.success) {
      phasesOutput.innerHTML = renderCompileResult(data);
      phasesStatus.textContent = "✓ Compilation successful — all 6 phases completed";
      phasesStatus.className = "status-line status-success";
    } else {
      phasesOutput.innerHTML = renderCompileError(data);
      phasesStatus.textContent = `✗ ${data.error.type}`;
      phasesStatus.className = "status-line status-error";
    }
  } catch (err) {
    phasesStatus.textContent = "✗ Could not reach the backend. Is app.py running?";
    phasesStatus.className = "status-line status-error";
    phasesOutput.innerHTML = `<div class="empty-state">Could not connect to http://127.0.0.1:5000. Make sure the Flask server is running (python app.py).</div>`;
  } finally {
    phasesRunBtn.disabled = false;
  }
});

// ============================================================
// ERROR ANALYSIS WORKSPACE WIRING
// ============================================================
const errorsInput = document.getElementById("errors-input");
const errorsOutput = document.getElementById("errors-output");
const errorsStatus = document.getElementById("errors-status");
const errorsRunBtn = document.getElementById("errors-run");

document.getElementById("errors-example").addEventListener("click", () => {
  errorsInput.value = EXAMPLE_ERRORS;
});
document.getElementById("errors-clear").addEventListener("click", () => {
  errorsInput.value = "";
  errorsOutput.innerHTML = `<div class="empty-state">Run a program with mistakes in it to watch panic-mode recovery in action.</div>`;
  errorsStatus.textContent = "";
  errorsStatus.className = "status-line";
});

errorsRunBtn.addEventListener("click", async () => {
  const source = errorsInput.value;
  if (!source.trim()) {
    showToast("Please enter a program first");
    return;
  }

  errorsRunBtn.disabled = true;
  errorsStatus.textContent = "Analyzing...";
  errorsStatus.className = "status-line status-loading";

  try {
    const { data } = await callApi("/api/error-analysis", source);
    errorsOutput.innerHTML = renderErrorAnalysisResult(data);
    if (data.summary.total_errors === 0) {
      errorsStatus.textContent = "✓ No errors found";
      errorsStatus.className = "status-line status-success";
    } else {
      errorsStatus.textContent = `⚠ ${data.summary.total_errors} error(s) found — recovery successful`;
      errorsStatus.className = "status-line status-error";
    }
  } catch (err) {
    errorsStatus.textContent = "✗ Could not reach the backend. Is app.py running?";
    errorsStatus.className = "status-line status-error";
    errorsOutput.innerHTML = `<div class="empty-state">Could not connect to http://127.0.0.1:5000. Make sure the Flask server is running (python app.py).</div>`;
  } finally {
    errorsRunBtn.disabled = false;
  }
});