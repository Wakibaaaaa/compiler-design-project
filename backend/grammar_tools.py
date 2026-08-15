"""
grammar_tools.py
Part B of the toolkit: Leftmost Derivation (LMD), Rightmost Derivation (RMD),
Parse Tree construction, and Ambiguity Detection for a user-typed grammar.

This is a direct port of the user's own console tool (Part B of their
combined script). The only real changes:
  1. Functions that used to print() now RETURN plain data (dicts/strings),
     since a Flask API needs to hand data to a browser, not a terminal.
  2. The interactive "type lines until you enter 'end'" input loop is
     replaced by parse_grammar_text(), which parses a grammar that was
     typed into a <textarea> and submitted all at once.
  3. Everything raises GrammarError with a clear message on bad input,
     instead of silently printing "! ..." warnings to a console.

Grammar format (typed by the user, one rule per line):
    E -> E+E | a | b | c
    S -> aA
    A -> b | bB
Use 'e' or 'epsilon' for an empty (epsilon) production.
Symbols must be SINGLE characters (this matches the original console tool;
FIRST/FOLLOW, in first_follow.py, is the one that supports multi-character
symbols like E' or id).
"""

MAX_DERIVATION_DEPTH = 25
MAX_TREE_SEARCH_DEPTH = 20


class GrammarError(Exception):
    """Raised for anything wrong with the grammar or target string the user typed."""
    pass


# ------------------------------------------------------------
# GRAMMAR
# ------------------------------------------------------------
class Grammar:
    def __init__(self):
        self.productions = {}       # head -> list of bodies (each body is a list of single-char symbols)
        self.start_symbol = None
        self.non_terminals = set()
        self.terminals = set()

    def add_production(self, head, body_list):
        if self.start_symbol is None:
            self.start_symbol = head
        self.non_terminals.add(head)
        if head not in self.productions:
            self.productions[head] = []
        for body in body_list:
            self.productions[head].append(body)

    def finalize(self):
        self.terminals = set()
        for head in self.productions:
            for body in self.productions[head]:
                for symbol in body:
                    if symbol not in self.non_terminals and symbol != 'e':
                        self.terminals.add(symbol)

    def is_non_terminal(self, symbol):
        return symbol in self.non_terminals

    def is_terminal(self, symbol):
        return not self.is_non_terminal(symbol)

    def to_dict(self):
        return {
            "rules": [
                f"{head} -> " + " | ".join("".join(body) for body in self.productions[head])
                for head in self.productions
            ],
            "start_symbol": self.start_symbol,
            "non_terminals": sorted(self.non_terminals),
            "terminals": sorted(self.terminals),
        }


def parse_grammar_text(text):
    """
    Parses grammar text typed by the user into a Grammar object.
    Each non-blank line must look like: HEAD -> body1 | body2
    Symbols are single characters; 'e' / 'epsilon' means the empty string.
    Raises GrammarError with a message that points at the bad line.
    """
    grammar = Grammar()
    any_line = False

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        any_line = True
        if '->' not in line:
            raise GrammarError(f"Line {line_num}: missing '->'. Use format: HEAD -> body1 | body2")
        head_part, body_part = line.split('->', 1)
        head = head_part.strip()
        body_part = body_part.strip()
        if not head:
            raise GrammarError(f"Line {line_num}: no head (left-hand side) symbol found.")
        if len(head) != 1:
            raise GrammarError(
                f"Line {line_num}: head symbol '{head}' must be a single character "
                f"(this tool uses single-character grammar symbols)."
            )
        if not body_part:
            raise GrammarError(f"Line {line_num}: '{head} ->' has no right-hand side.")

        body_list = []
        for prod in body_part.split('|'):
            prod = prod.strip()
            if prod in ('e', 'epsilon'):
                body_list.append(['e'])
            else:
                if ' ' in prod:
                    raise GrammarError(
                        f"Line {line_num}: symbols must be single characters with no spaces "
                        f"(got '{prod}')."
                    )
                body_list.append(list(prod))
        grammar.add_production(head, body_list)

    if not any_line:
        raise GrammarError("No grammar rules were entered.")

    grammar.finalize()
    return grammar


# ------------------------------------------------------------
# PARSE TREE NODE
# ------------------------------------------------------------
class TreeNode:
    def __init__(self, symbol):
        self.symbol = symbol
        self.children = []

    def add_child(self, child):
        self.children.append(child)


def trees_are_equal(t1, t2):
    if t1 is None and t2 is None:
        return True
    if t1 is None or t2 is None:
        return False
    if t1.symbol != t2.symbol or len(t1.children) != len(t2.children):
        return False
    return all(trees_are_equal(a, b) for a, b in zip(t1.children, t2.children))


def get_unique_trees(trees):
    unique = []
    for t in trees:
        if not any(trees_are_equal(t, u) for u in unique):
            unique.append(t)
    return unique


# ------------------------------------------------------------
# ASCII PARSE TREE RENDERER (compact / | \ branches) -- unchanged logic,
# now returns a string instead of printing
# ------------------------------------------------------------
def render_tree_ascii(node):
    lines, _, _ = _render_tree(node)
    return "\n".join(lines)


def _render_tree(node):
    label = str(node.symbol)
    label_len = len(label)

    if not node.children:
        return [label], label_len // 2, label_len

    child_data = []
    for child in node.children:
        c_lines, c_center, c_width = _render_tree(child)
        child_data.append([c_lines, c_center, c_width])

    n = len(child_data)
    gap = 3

    child_starts = []
    pos = 0
    for i, (_, _, cw) in enumerate(child_data):
        child_starts.append(pos)
        pos += cw
        if i < n - 1:
            pos += gap
    total_width = pos

    child_centers = [child_starts[i] + child_data[i][1] for i in range(n)]

    if n == 1:
        parent_center = child_centers[0]
    else:
        parent_center = (child_centers[0] + child_centers[-1]) // 2

    label_start = parent_center - label_len // 2
    shift = 0
    if label_start < 0:
        shift = -label_start
    if shift > 0:
        child_starts = [s + shift for s in child_starts]
        child_centers = [c + shift for c in child_centers]
        parent_center += shift
        total_width += shift
        label_start += shift

    total_width = max(total_width, label_start + label_len)
    buf = total_width + 5

    result = []

    row = [' '] * buf
    for k, ch in enumerate(label):
        p = label_start + k
        if 0 <= p < buf:
            row[p] = ch
    result.append(''.join(row).rstrip())

    row = [' '] * buf
    for c in child_centers:
        if c < parent_center:
            ch = '/'
        elif c > parent_center:
            ch = '\\'
        else:
            ch = '|'
        if 0 <= c < buf:
            row[c] = ch
    result.append(''.join(row).rstrip())

    max_h = max(len(cd[0]) for cd in child_data)
    for r in range(max_h):
        row = [' '] * buf
        for i, (c_lines, _, c_width) in enumerate(child_data):
            start = child_starts[i]
            if r < len(c_lines):
                line = c_lines[r]
                for k, ch in enumerate(line):
                    p = start + k
                    if 0 <= p < buf and ch != ' ':
                        row[p] = ch
        result.append(''.join(row).rstrip())

    return result, parent_center, total_width


# ------------------------------------------------------------
# DERIVATION SEARCH (brute-force, backtracking) -- unchanged logic
# ------------------------------------------------------------
def leftmost_derive_all(grammar, target, max_depth=MAX_DERIVATION_DEPTH):
    """Return list of (steps, rules) tuples for every successful LMD path found."""
    results = []

    def helper(current, steps, rules, depth):
        if depth > max_depth:
            return
        cur_str = ''.join(current)
        if cur_str == target:
            results.append((list(steps), list(rules)))
            return
        term_len = sum(len(s) for s in current if grammar.is_terminal(s))
        if term_len > len(target):
            return
        idx = -1
        for i, s in enumerate(current):
            if grammar.is_non_terminal(s):
                idx = i
                break
        if idx == -1:
            return
        nt = current[idx]
        for prod in grammar.productions[nt]:
            replacement = [] if prod == ['e'] else list(prod)
            new_current = current[:idx] + replacement + current[idx + 1:]
            rhs = 'e' if prod == ['e'] else ''.join(prod)
            rule = f"{nt} -> {rhs}"
            steps.append(''.join(new_current))
            rules.append(rule)
            helper(new_current, steps, rules, depth + 1)
            steps.pop()
            rules.pop()

    helper([grammar.start_symbol], [grammar.start_symbol], [""], 0)
    return results


def rightmost_derive_all(grammar, target, max_depth=MAX_DERIVATION_DEPTH):
    """Return list of (steps, rules) tuples for every successful RMD path found."""
    results = []

    def helper(current, steps, rules, depth):
        if depth > max_depth:
            return
        cur_str = ''.join(current)
        if cur_str == target:
            results.append((list(steps), list(rules)))
            return
        term_len = sum(len(s) for s in current if grammar.is_terminal(s))
        if term_len > len(target):
            return
        idx = -1
        for i in range(len(current) - 1, -1, -1):
            if grammar.is_non_terminal(current[i]):
                idx = i
                break
        if idx == -1:
            return
        nt = current[idx]
        for prod in grammar.productions[nt]:
            replacement = [] if prod == ['e'] else list(prod)
            new_current = current[:idx] + replacement + current[idx + 1:]
            rhs = 'e' if prod == ['e'] else ''.join(prod)
            rule = f"{nt} -> {rhs}"
            steps.append(''.join(new_current))
            rules.append(rule)
            helper(new_current, steps, rules, depth + 1)
            steps.pop()
            rules.pop()

    helper([grammar.start_symbol], [grammar.start_symbol], [""], 0)
    return results


def build_tree_from_steps(grammar, steps, use_leftmost=True):
    root = TreeNode(grammar.start_symbol)
    _expand_node(root, grammar, steps, [1], use_leftmost)
    return root


def _expand_node(node, grammar, steps, step_ref, use_leftmost):
    if step_ref[0] >= len(steps):
        return
    if not grammar.is_non_terminal(node.symbol):
        return

    prev = steps[step_ref[0] - 1]
    curr = steps[step_ref[0]]

    for prod in grammar.productions[node.symbol]:
        prod_str = '' if prod == ['e'] else ''.join(prod)
        if prev.replace(node.symbol, prod_str, 1) == curr:
            if prod == ['e']:
                node.add_child(TreeNode('e'))
            else:
                for s in prod:
                    node.add_child(TreeNode(s))
            step_ref[0] += 1
            kids = node.children if use_leftmost else list(reversed(node.children))
            for child in kids:
                if grammar.is_non_terminal(child.symbol):
                    if step_ref[0] < len(steps):
                        _expand_node(child, grammar, steps, step_ref, use_leftmost)
            return


def build_all_parse_trees(grammar, target, max_depth=MAX_TREE_SEARCH_DEPTH):
    """Exhaustively finds every structurally distinct parse tree for target."""

    def try_derive(symbol, string, depth):
        if depth > max_depth:
            return []
        if grammar.is_terminal(symbol):
            if string == symbol:
                return [TreeNode(symbol)]
            return []
        trees = []
        if symbol not in grammar.productions:
            return []
        for prod in grammar.productions[symbol]:
            if prod == ['e']:
                if string == '':
                    node = TreeNode(symbol)
                    node.add_child(TreeNode('e'))
                    trees.append(node)
            else:
                child_tree_lists = try_split(prod, string, 0, depth + 1)
                for child_trees in child_tree_lists:
                    node = TreeNode(symbol)
                    for ct in child_trees:
                        node.add_child(ct)
                    trees.append(node)
        return trees

    def try_split(symbols, string, sym_idx, depth):
        if sym_idx == len(symbols):
            return [[]] if string == '' else []
        if depth > max_depth:
            return []
        sym = symbols[sym_idx]
        results = []

        min_remaining = 0
        for k in range(sym_idx + 1, len(symbols)):
            s = symbols[k]
            if grammar.is_terminal(s):
                min_remaining += len(s)

        min_len = 0 if grammar.is_non_terminal(sym) else len(sym)
        max_len = len(string) - min_remaining

        for split in range(min_len, max_len + 1):
            prefix = string[:split]
            suffix = string[split:]

            sub_trees = try_derive(sym, prefix, depth)
            if not sub_trees:
                continue

            rest_splits = try_split(symbols, suffix, sym_idx + 1, depth)
            if not rest_splits:
                continue

            for st in sub_trees:
                for rs in rest_splits:
                    results.append([st] + rs)

        return results

    return try_derive(grammar.start_symbol, target, 0)


# ------------------------------------------------------------
# HIGH-LEVEL API FUNCTIONS (called directly by app.py)
# ------------------------------------------------------------
def _steps_to_list(steps, rules):
    out = [{"step": 1, "string": steps[0], "rule": None}]
    for i in range(1, len(steps)):
        out.append({"step": i + 1, "string": steps[i], "rule": rules[i] if i < len(rules) else None})
    return out


def run_derivation(grammar_text, target, mode="leftmost"):
    """Part B, options [1] and [2]: LMD or RMD for a target string."""
    grammar = parse_grammar_text(grammar_text)
    target = target.strip()
    if not target:
        raise GrammarError("Please enter a target string to derive.")

    derive_fn = leftmost_derive_all if mode == "leftmost" else rightmost_derive_all
    all_results = derive_fn(grammar, target)

    if not all_results:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "mode": mode,
            "message": f"The string '{target}' cannot be derived from this grammar.",
        }

    steps, rules = all_results[0]
    tree = build_tree_from_steps(grammar, steps, use_leftmost=(mode == "leftmost"))

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "mode": mode,
        "derivation_steps": _steps_to_list(steps, rules),
        "parse_tree_ascii": render_tree_ascii(tree),
        "alternate_path_count": len(all_results),
        "multiple_paths_note": (
            f"{len(all_results)} different {'LMD' if mode == 'leftmost' else 'RMD'} paths exist "
            f"for this string -- the grammar may be ambiguous (check with Ambiguity Detection)."
            if len(all_results) > 1 else None
        ),
    }


def run_parse_tree(grammar_text, target):
    """Part B, option [3]: build ALL distinct parse trees for target."""
    grammar = parse_grammar_text(grammar_text)
    target = target.strip()
    if not target:
        raise GrammarError("Please enter a target string.")

    all_trees = build_all_parse_trees(grammar, target)
    unique_trees = get_unique_trees(all_trees)

    if not unique_trees:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "message": f"The string '{target}' cannot be derived from this grammar.",
        }

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "tree_count": len(unique_trees),
        "trees_ascii": [render_tree_ascii(t) for t in unique_trees],
        "is_ambiguous": len(unique_trees) > 1,
    }


def run_ambiguity(grammar_text, target):
    """Part B, option [4]: full LMD-vs-RMD ambiguity analysis for target."""
    grammar = parse_grammar_text(grammar_text)
    target = target.strip()
    if not target:
        raise GrammarError("Please enter a target string.")

    lm_all = leftmost_derive_all(grammar, target)
    rm_all = rightmost_derive_all(grammar, target)

    if not lm_all:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "message": f"The string '{target}' cannot be derived from this grammar.",
        }

    lm_trees_all = [build_tree_from_steps(grammar, s, True) for s, _ in lm_all]
    rm_trees_all = [build_tree_from_steps(grammar, s, False) for s, _ in rm_all]

    def unique_indices(trees):
        idxs, seen = [], []
        for i, t in enumerate(trees):
            if not any(trees_are_equal(t, u) for u in seen):
                seen.append(t)
                idxs.append(i)
        return idxs

    lm_unique_idx = unique_indices(lm_trees_all)
    rm_unique_idx = unique_indices(rm_trees_all)

    lm_entries = []
    for count, i in enumerate(lm_unique_idx):
        steps, rules = lm_all[i]
        lm_entries.append({
            "label": f"LMD {count + 1}",
            "derivation_steps": _steps_to_list(steps, rules),
            "parse_tree_ascii": render_tree_ascii(lm_trees_all[i]),
        })

    rm_entries = []
    for count, i in enumerate(rm_unique_idx):
        steps, rules = rm_all[i]
        rm_entries.append({
            "label": f"RMD {count + 1}",
            "derivation_steps": _steps_to_list(steps, rules),
            "parse_tree_ascii": render_tree_ascii(rm_trees_all[i]),
        })

    lm_trees = [lm_trees_all[i] for i in lm_unique_idx]
    rm_trees = [rm_trees_all[i] for i in rm_unique_idx]

    lmd_comparisons = []
    for i in range(len(lm_trees)):
        for j in range(i + 1, len(lm_trees)):
            lmd_comparisons.append({
                "a": f"LMD {i + 1}", "b": f"LMD {j + 1}",
                "same": trees_are_equal(lm_trees[i], lm_trees[j]),
            })

    rmd_comparisons = []
    for i in range(len(rm_trees)):
        for j in range(i + 1, len(rm_trees)):
            rmd_comparisons.append({
                "a": f"RMD {i + 1}", "b": f"RMD {j + 1}",
                "same": trees_are_equal(rm_trees[i], rm_trees[j]),
            })

    cross_comparisons = []
    for i, lt in enumerate(lm_trees):
        for j, rt in enumerate(rm_trees):
            cross_comparisons.append({
                "a": f"LMD {i + 1}", "b": f"RMD {j + 1}",
                "same": trees_are_equal(lt, rt),
            })

    lmd_unique = len(lm_trees)
    rmd_unique = len(rm_trees)
    is_ambiguous = (lmd_unique > 1) or (rmd_unique > 1)

    reasons = []
    if lmd_unique > 1:
        reasons.append(f"{lmd_unique} different LMD parse trees found.")
    if rmd_unique > 1:
        reasons.append(f"{rmd_unique} different RMD parse trees found.")
    if not reasons:
        reasons.append("Only one unique parse tree exists.")

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "lmd_entries": lm_entries,
        "rmd_entries": rm_entries,
        "lmd_unique_count": lmd_unique,
        "rmd_unique_count": rmd_unique,
        "lmd_comparisons": lmd_comparisons,
        "rmd_comparisons": rmd_comparisons,
        "cross_comparisons": cross_comparisons,
        "is_ambiguous": is_ambiguous,
        "reasons": reasons,
    }
