// ============================================================
// CONFIG
// ============================================================
// Empty string = "call this same server" -- works both locally (single
// Flask server now serves the frontend too) and once deployed online,
// with no URL to remember to change.
const API_BASE = "";

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

const EXAMPLE_GRAMMAR = "E -> E+E | a | b | c";
const EXAMPLE_GRAMMAR_TARGET = "a+b+c";

const EXAMPLE_FIRST_FOLLOW =
  "E -> T E'\nE' -> + T E' | eps\nT -> F T'\nT' -> * F T' | eps\nF -> ( E ) | id";

// ============================================================
// NAVIGATION
// ============================================================
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  // Force an instant jump to the very top of the new screen, run on the
  // next frame so it happens *after* the browser has laid out the newly
  // shown section (fixes the "still scrolled down" issue when the home
  // screen was scrolled before clicking a card).
  requestAnimationFrame(() => {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  });
}

document.getElementById("btn-go-phases").addEventListener("click", () => showScreen("phases-screen"));
document.getElementById("btn-go-errors").addEventListener("click", () => showScreen("errors-screen"));
document.getElementById("btn-go-grammar").addEventListener("click", () => showScreen("grammar-screen"));
document.getElementById("btn-go-firstfollow").addEventListener("click", () => showScreen("firstfollow-screen"));
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
    if (stmt.declaration_only) {
      html += `
        <div class="phase-card">
          <div class="phase-header">
            <span class="phase-number">·</span>
            <span class="phase-title">Statement ${i + 1}: <code>${escapeHtml(stmt.source_line)}</code> (line ${stmt.line_number}) — Declaration</span>
          </div>
          <div class="phase-content">
            <p style="color: var(--text-secondary); font-size: 13.5px; margin: 0;">${escapeHtml(stmt.note)}</p>
          </div>
        </div>`;
      return;
    }
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
  return callApiBody(endpoint, { source });
}

// Same idea as callApi, but takes a full JSON body instead of assuming a
// single "source" field -- the grammar/first-follow endpoints need more
// than one field (grammar text, target string, mode).
async function callApiBody(endpoint, body) {
  let response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (networkErr) {
    // fetch() itself only throws for true network-level failures: DNS
    // failure, no connection, CORS block, offline, etc.
    throw new Error(`Network error — the request never reached the server (${networkErr.message}).`);
  }

  if (!response.ok) {
    // Server responded, but with a non-2xx status. Try to read a JSON
    // error body; if the server sent back an HTML error page instead
    // (e.g. a 502/504 from Render, or an unhandled exception producing
    // Flask's default error page), fall back to the status text so the
    // user still sees something meaningful instead of a JSON parse crash.
    let detail = "";
    try {
      const errJson = await response.json();
      detail = errJson.message || errJson.error?.message || JSON.stringify(errJson);
    } catch {
      detail = await response.text().catch(() => "");
      detail = detail && detail.length < 200 ? detail : `HTTP ${response.status} ${response.statusText}`;
    }
    throw new Error(`Server returned an error (HTTP ${response.status}): ${detail}`);
  }

  let data;
  try {
    data = await response.json();
  } catch (parseErr) {
    throw new Error(`Server responded but didn't send valid JSON (${parseErr.message}). It may still be starting up — try again in a few seconds.`);
  }

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
    phasesStatus.textContent = "✗ " + err.message;
    phasesStatus.className = "status-line status-error";
    phasesOutput.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
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
    errorsStatus.textContent = "✗ " + err.message;
    errorsStatus.className = "status-line status-error";
    errorsOutput.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
  } finally {
    errorsRunBtn.disabled = false;
  }
});
// ============================================================
// GRAMMAR ANALYSIS RENDERING (LMD / RMD / Parse Tree / Ambiguity)
// ============================================================
function renderGrammarSummary(g) {
  return `
    <div class="grammar-summary">
      <span><strong>Rules:</strong> ${g.rules.map(escapeHtml).join("  |  ")}</span>
      <span><strong>Start:</strong> ${escapeHtml(g.start_symbol)}</span>
      <span><strong>Non-terminals:</strong> ${g.non_terminals.map(escapeHtml).join(", ")}</span>
      <span><strong>Terminals:</strong> ${g.terminals.map(escapeHtml).join(", ")}</span>
    </div>`;
}

function renderDerivationSteps(steps) {
  const rows = steps.map(s => `
    <div class="step-row">
      <span class="step-num">Step ${s.step}</span>
      <span class="step-string">${escapeHtml(s.string)}</span>
      <span class="step-rule">${s.rule ? "[" + escapeHtml(s.rule) + "]" : ""}</span>
    </div>`).join("");
  return `<div class="derivation-steps">${rows}</div>`;
}

function renderGrammarError(data) {
  return `
    <div class="error-card">
      <div class="error-head">
        <span class="error-type-badge">Grammar / Input Error</span>
      </div>
      <div class="error-body">
        <div class="error-message">${escapeHtml(data.message)}</div>
      </div>
    </div>`;
}

function renderDerivationResult(data, modeLabel) {
  let html = renderGrammarSummary(data.grammar);
  html += phaseCard("→", `${modeLabel} of '${escapeHtml(data.target)}'`,
    modeLabel === "LMD"
      ? "Repeatedly expands the LEFTMOST non-terminal using a matching production until the target string is produced."
      : "Repeatedly expands the RIGHTMOST non-terminal using a matching production until the target string is produced.",
    `
    <div class="subsection-label">Derivation Steps</div>
    ${renderDerivationSteps(data.derivation_steps)}
    <div class="subsection-label">Parse Tree</div>
    <div class="tree-block">${escapeHtml(data.parse_tree_ascii)}</div>
    ${data.multiple_paths_note ? `<p style="color: var(--accent-amber); font-size: 13px; margin-top: 14px;">⚠ ${escapeHtml(data.multiple_paths_note)}</p>` : ""}
  `);
  return html;
}

function renderParseTreeResult(data) {
  let html = renderGrammarSummary(data.grammar);
  html += `<div class="subsection-label" style="margin-top:18px;">Unique parse trees found: ${data.tree_count}</div>`;
  data.trees_ascii.forEach((ascii, i) => {
    html += phaseCard(i + 1, data.trees_ascii.length > 1 ? `Parse Tree ${i + 1} of ${data.trees_ascii.length}` : "Parse Tree",
      "One structurally distinct way to derive the target string from the start symbol.",
      `<div class="tree-block">${escapeHtml(ascii)}</div>`);
  });
  if (data.is_ambiguous) {
    html += `<div class="verdict-banner verdict-ambiguous">⚠ Multiple distinct parse trees exist — this grammar is AMBIGUOUS for '${escapeHtml(data.target)}'.</div>`;
  }
  return html;
}

function renderDerivationEntries(entries) {
  return entries.map((e, i) => `
    <div class="phase-card">
      <div class="phase-header">
        <span class="phase-number">${i + 1}</span>
        <span class="phase-title">${escapeHtml(e.label)}</span>
      </div>
      <div class="phase-content">
        ${renderDerivationSteps(e.derivation_steps)}
        <div class="subsection-label">Parse Tree</div>
        <div class="tree-block">${escapeHtml(e.parse_tree_ascii)}</div>
      </div>
    </div>`).join("");
}

function renderComparisonTable(title, comparisons) {
  if (!comparisons.length) return "";
  const rows = comparisons.map(c => `
    <tr>
      <td>${escapeHtml(c.a)}</td>
      <td>${escapeHtml(c.b)}</td>
      <td class="${c.same ? "compare-same" : "compare-diff"}">${c.same ? "SAME" : "DIFFERENT"}</td>
    </tr>`).join("");
  return `
    <div class="subsection-label">${escapeHtml(title)}</div>
    <table class="compare-table">
      <thead><tr><th>A</th><th>B</th><th>Result</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function renderAmbiguityResult(data) {
  let html = renderGrammarSummary(data.grammar);

  html += phaseCard("L", `Leftmost Derivations (${data.lmd_entries.length} unique)`,
    "Every structurally distinct parse tree reachable by always expanding the leftmost non-terminal.",
    renderDerivationEntries(data.lmd_entries));

  html += phaseCard("R", `Rightmost Derivations (${data.rmd_entries.length} unique)`,
    "Every structurally distinct parse tree reachable by always expanding the rightmost non-terminal.",
    renderDerivationEntries(data.rmd_entries));

  html += phaseCard("=", "Parse Tree Comparison",
    "Compares every unique LMD tree against every unique RMD tree (and against each other) to check for structural duplicates.",
    `
    ${renderComparisonTable("LMD vs LMD", data.lmd_comparisons)}
    ${renderComparisonTable("RMD vs RMD", data.rmd_comparisons)}
    ${renderComparisonTable("LMD vs RMD", data.cross_comparisons)}
  `);

  html += `
    <div class="verdict-banner ${data.is_ambiguous ? "verdict-ambiguous" : "verdict-unambiguous"}">
      ${data.is_ambiguous ? "⚠ Grammar IS AMBIGUOUS" : "✓ Grammar is NOT AMBIGUOUS"} for '${escapeHtml(data.target)}'
    </div>
    <div class="notes-list">${data.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</div>
  `;
  return html;
}

// ============================================================
// FIRST / FOLLOW RENDERING
// ============================================================
function renderFFSetList(sets, prefix) {
  const rows = sets.map(s => `
    <div class="ff-set-row">
      <span class="ff-set-name">${prefix}(${escapeHtml(s.symbol)})</span>
      <span class="ff-set-braces">=</span>
      <span class="ff-set-braces">{</span>
      <span class="ff-set-members">${s.set.map(m => `<span>${escapeHtml(m)}</span>`).join("")}</span>
      <span class="ff-set-braces">}</span>
    </div>`).join("");
  return `<div class="ff-set-list">${rows}</div>`;
}

function renderFirstFollowResult(data) {
  let html = renderGrammarSummary(data.grammar);
  html += phaseCard(1, "FIRST Sets",
    "FIRST(X) is the set of terminals that can appear as the first symbol of any string derived from X (plus 'eps' if X can derive the empty string).",
    renderFFSetList(data.first_sets, "FIRST"));
  html += phaseCard(2, "FOLLOW Sets",
    "FOLLOW(A) is the set of terminals that can appear immediately after A in some derivation from the start symbol (plus '$' for the start symbol, marking end of input).",
    renderFFSetList(data.follow_sets, "FOLLOW"));
  return html;
}

// ============================================================
// GRAMMAR WORKSPACE WIRING
// ============================================================
const grammarInput = document.getElementById("grammar-input");
const grammarTarget = document.getElementById("grammar-target");
const grammarOutput = document.getElementById("grammar-output");
const grammarStatus = document.getElementById("grammar-status");
const grammarRunBtn = document.getElementById("grammar-run");
let grammarMode = "leftmost";

document.querySelectorAll("#grammar-mode-control .segment").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#grammar-mode-control .segment").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    grammarMode = btn.dataset.mode;
  });
});

document.getElementById("grammar-example").addEventListener("click", () => {
  grammarInput.value = EXAMPLE_GRAMMAR;
  grammarTarget.value = EXAMPLE_GRAMMAR_TARGET;
});
document.getElementById("grammar-clear").addEventListener("click", () => {
  grammarInput.value = "";
  grammarTarget.value = "";
  grammarOutput.innerHTML = `<div class="empty-state">Enter a grammar and a target string, choose an analysis type above, then hit Run.</div>`;
  grammarStatus.textContent = "";
  grammarStatus.className = "status-line";
});

grammarRunBtn.addEventListener("click", async () => {
  const grammar = grammarInput.value;
  const target = grammarTarget.value;
  if (!grammar.trim()) {
    showToast("Please enter a grammar first");
    return;
  }
  if (!target.trim()) {
    showToast("Please enter a target string");
    return;
  }

  const endpointMap = {
    leftmost: "/api/grammar/derive",
    rightmost: "/api/grammar/derive",
    parsetree: "/api/grammar/parse-tree",
    ambiguity: "/api/grammar/ambiguity",
  };
  const body = { grammar, target };
  if (grammarMode === "leftmost" || grammarMode === "rightmost") body.mode = grammarMode;

  grammarRunBtn.disabled = true;
  grammarStatus.textContent = "Analyzing...";
  grammarStatus.className = "status-line status-loading";

  try {
    const { data } = await callApiBody(endpointMap[grammarMode], body);
    if (!data.success) {
      grammarOutput.innerHTML = renderGrammarError(data);
      grammarStatus.textContent = "✗ " + (data.message || "Could not complete analysis");
      grammarStatus.className = "status-line status-error";
      return;
    }

    if (grammarMode === "leftmost") {
      grammarOutput.innerHTML = renderDerivationResult(data, "LMD");
    } else if (grammarMode === "rightmost") {
      grammarOutput.innerHTML = renderDerivationResult(data, "RMD");
    } else if (grammarMode === "parsetree") {
      grammarOutput.innerHTML = renderParseTreeResult(data);
    } else if (grammarMode === "ambiguity") {
      grammarOutput.innerHTML = renderAmbiguityResult(data);
    }
    grammarStatus.textContent = "✓ Analysis complete";
    grammarStatus.className = "status-line status-success";
  } catch (err) {
    grammarStatus.textContent = "✗ " + err.message;
    grammarStatus.className = "status-line status-error";
    grammarOutput.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
  } finally {
    grammarRunBtn.disabled = false;
  }
});

// ============================================================
// FIRST / FOLLOW WORKSPACE WIRING
// ============================================================
const ffInput = document.getElementById("ff-input");
const ffOutput = document.getElementById("ff-output");
const ffStatus = document.getElementById("ff-status");
const ffRunBtn = document.getElementById("ff-run");

document.getElementById("ff-example").addEventListener("click", () => {
  ffInput.value = EXAMPLE_FIRST_FOLLOW;
});
document.getElementById("ff-clear").addEventListener("click", () => {
  ffInput.value = "";
  ffOutput.innerHTML = `<div class="empty-state">Enter a grammar and click Compute to see FIRST(X) and FOLLOW(A) for every non-terminal.</div>`;
  ffStatus.textContent = "";
  ffStatus.className = "status-line";
});

ffRunBtn.addEventListener("click", async () => {
  const grammar = ffInput.value;
  if (!grammar.trim()) {
    showToast("Please enter a grammar first");
    return;
  }

  ffRunBtn.disabled = true;
  ffStatus.textContent = "Computing...";
  ffStatus.className = "status-line status-loading";

  try {
    const { data } = await callApiBody("/api/first-follow", { grammar });
    if (!data.success) {
      ffOutput.innerHTML = renderGrammarError(data);
      ffStatus.textContent = "✗ " + (data.message || "Could not compute FIRST/FOLLOW");
      ffStatus.className = "status-line status-error";
      return;
    }
    ffOutput.innerHTML = renderFirstFollowResult(data);
    ffStatus.textContent = "✓ FIRST and FOLLOW sets computed";
    ffStatus.className = "status-line status-success";
  } catch (err) {
    ffStatus.textContent = "✗ " + err.message;
    ffStatus.className = "status-line status-error";
    ffOutput.innerHTML = `<div class="empty-state">${escapeHtml(err.message)}</div>`;
  } finally {
    ffRunBtn.disabled = false;
  }
});
