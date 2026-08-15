"""
grammar_tools.py

Adapted from the user's own "Part B" (LMD / RMD / Parse Tree / Ambiguity
Detection) and "Part C" (FIRST & FOLLOW Set Computation) code. The
algorithms are unchanged; every function that used to print() its output
now RETURNS structured data instead, since a Flask API needs data, not
console text.
"""

import re
from collections import OrderedDict


# =============================================================================
# PART B -- GRAMMAR (single-character symbols, used by LMD/RMD/Parse Tree/Ambiguity)
# =============================================================================

class Grammar:
    def __init__(self):
        self.productions = {}
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
            "productions": {
                head: [''.join(body) for body in bodies]
                for head, bodies in self.productions.items()
            },
            "start_symbol": self.start_symbol,
            "non_terminals": sorted(self.non_terminals),
            "terminals": sorted(self.terminals),
        }


class GrammarParseError(Exception):
    """Raised when the grammar text the user typed can't be parsed."""
    pass


def parse_grammar_text(text):
    """
    Parses grammar rules written one-per-line as "HEAD -> body1 | body2",
    using single-character symbols (as the original tool required), with
    'e' or 'eps' meaning epsilon. Raises GrammarParseError with a helpful
    message on bad input instead of silently producing an empty grammar.
    """
    grammar = Grammar()
    line_num = 0
    any_rule = False
    for raw_line in text.split("\n"):
        line_num += 1
        line = raw_line.strip()
        if not line:
            continue
        if '->' not in line:
            raise GrammarParseError(f"Line {line_num}: expected format 'HEAD -> body1 | body2', got: '{line}'")
        head_part, body_part = line.split('->', 1)
        head = head_part.strip()
        if not head or len(head) != 1:
            raise GrammarParseError(f"Line {line_num}: head symbol must be a single character, got: '{head}'")
        body_list = []
        for prod in body_part.split('|'):
            prod = prod.strip()
            if prod in ('e', 'eps', 'epsilon', ''):
                body_list.append(['e'])
            else:
                body_list.append(list(prod))
        grammar.add_production(head, body_list)
        any_rule = True
    if not any_rule:
        raise GrammarParseError("No grammar rules were entered.")
    grammar.finalize()
    return grammar


# ------------------------------------------------------------
# N-ARY ASCII TREE RENDERER (Part B's version -- any number of children)
# ------------------------------------------------------------
class TreeNode:
    def __init__(self, symbol):
        self.symbol = symbol
        self.children = []

    def add_child(self, child):
        self.children.append(child)


def render_tree(node):
    label = str(node.symbol)
    label_len = len(label)

    if not node.children:
        return [label], label_len // 2, label_len

    child_data = []
    for child in node.children:
        c_lines, c_center, c_width = render_tree(child)
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


def render_tree_ascii(node):
    lines, _, _ = render_tree(node)
    return "\n".join(lines)


# ------------------------------------------------------------
# DERIVATIONS (unchanged algorithm)
# ------------------------------------------------------------
def leftmost_derive_all(grammar, target, max_depth=25):
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


def rightmost_derive_all(grammar, target, max_depth=25):
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


# ------------------------------------------------------------
# ALL PARSE TREES (unchanged algorithm)
# ------------------------------------------------------------
def build_all_parse_trees(grammar, target, max_depth=20):
    def try_derive(symbol, string, depth):
        if depth > max_depth:
            return []
        if grammar.is_terminal(symbol):
            if string == symbol:
                return [TreeNode(symbol)]
            else:
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
            if string == '':
                return [[]]
            else:
                return []
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


# =============================================================================
# PART C -- FIRST & FOLLOW (multi-character symbols)
# =============================================================================

class FirstFollowGrammar:
    def __init__(self):
        self.productions = OrderedDict()
        self.non_terminals = []
        self.eps = 'eps'

    def is_non_terminal(self, sym):
        return sym in self.productions

    def add_production(self, lhs, rhs):
        if lhs not in self.productions:
            self.productions[lhs] = []
            self.non_terminals.append(lhs)
        self.productions[lhs].append(rhs)

    def compute_first(self):
        first = {nt: set() for nt in self.non_terminals}
        changed = True
        while changed:
            changed = False
            for lhs in self.non_terminals:
                for prod in self.productions[lhs]:
                    if prod == [self.eps]:
                        if self.eps not in first[lhs]:
                            first[lhs].add(self.eps)
                            changed = True
                        continue
                    for sym in prod:
                        if sym == self.eps:
                            if self.eps not in first[lhs]:
                                first[lhs].add(self.eps)
                                changed = True
                            break
                        if not self.is_non_terminal(sym):
                            if sym not in first[lhs]:
                                first[lhs].add(sym)
                                changed = True
                            break
                        else:
                            before = len(first[lhs])
                            first[lhs].update(first[sym] - {self.eps})
                            if len(first[lhs]) != before:
                                changed = True
                            if self.eps not in first[sym]:
                                break
                    else:
                        if self.eps not in first[lhs]:
                            first[lhs].add(self.eps)
                            changed = True
        return first

    def first_of_string(self, symbols, first):
        res = set()
        if not symbols:
            res.add(self.eps)
            return res
        for sym in symbols:
            if sym == self.eps:
                res.add(self.eps)
                break
            if not self.is_non_terminal(sym):
                res.add(sym)
                break
            res.update(first[sym] - {self.eps})
            if self.eps not in first[sym]:
                break
        else:
            res.add(self.eps)
        return res

    def compute_follow(self, first):
        follow = {nt: set() for nt in self.non_terminals}
        follow[self.non_terminals[0]].add('$')
        changed = True
        while changed:
            changed = False
            for lhs in self.non_terminals:
                for prod in self.productions[lhs]:
                    if prod == [self.eps]:
                        continue
                    for i, sym in enumerate(prod):
                        if not self.is_non_terminal(sym):
                            continue
                        beta = prod[i + 1:]
                        if beta:
                            fb = self.first_of_string(beta, first)
                            before = len(follow[sym])
                            follow[sym].update(fb - {self.eps})
                            if len(follow[sym]) != before:
                                changed = True
                            if self.eps in fb:
                                before = len(follow[sym])
                                follow[sym].update(follow[lhs])
                                if len(follow[sym]) != before:
                                    changed = True
                        else:
                            before = len(follow[sym])
                            follow[sym].update(follow[lhs])
                            if len(follow[sym]) != before:
                                changed = True
        return follow


def ff_tokenize_no_space(s):
    res = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "'":
            if res:
                res[-1] += "'"
            i += 1
        elif c.isupper():
            tok = c
            i += 1
            while i < len(s) and s[i] in "'0123456789":
                tok += s[i]
                i += 1
            res.append(tok)
        elif c.islower():
            j = i
            while j < len(s) and s[j].islower():
                j += 1
            word = s[i:j]
            if word in ('eps', 'epsilon', 'null') or word == '\u03b5':
                res.append('eps')
            elif word == 'id':
                res.append('id')
            else:
                for ch in word:
                    res.append(ch)
            i = j
        elif c == '\u03b5':
            res.append('eps')
            i += 1
        elif c in ('|', '-', '>', '\u2192'):
            i += 1
        else:
            res.append(c)
            i += 1
    return [t for t in res if t not in ('', '-', '>')]


def ff_tokenize_rhs(rhs_str):
    rhs_str = rhs_str.strip()
    if not rhs_str:
        return []
    tokens = []
    if ' ' in rhs_str:
        for part in rhs_str.split():
            tokens.extend(ff_tokenize_no_space(part))
    else:
        tokens.extend(ff_tokenize_no_space(rhs_str))
    return tokens


class FirstFollowParseError(Exception):
    pass


def parse_first_follow_grammar_text(text):
    """
    Parses "LHS -> RHS1 | RHS2" rules (multi-char symbols allowed) from a
    block of text, one rule per line. Raises FirstFollowParseError with a
    helpful message on malformed input.
    """
    g = FirstFollowGrammar()
    lhs_order = []
    raw_rules = []
    line_num = 0
    for raw_line in text.split("\n"):
        line_num += 1
        line = raw_line.strip()
        if not line:
            continue
        if '->' not in line:
            raise FirstFollowParseError(f"Line {line_num}: expected format 'LHS -> RHS1 | RHS2', got: '{line}'")
        lhs_part, rhs_part = line.split('->', 1)
        lhs_tokens = ff_tokenize_no_space(lhs_part.strip())
        if not lhs_tokens:
            raise FirstFollowParseError(f"Line {line_num}: missing left-hand side symbol.")
        lhs = lhs_tokens[0]
        raw_rules.append((lhs, rhs_part))
        if lhs not in lhs_order:
            lhs_order.append(lhs)

    if not lhs_order:
        raise FirstFollowParseError("No grammar rules were entered.")

    for lhs in lhs_order:
        if lhs not in g.productions:
            g.productions[lhs] = []
            g.non_terminals.append(lhs)

    for lhs, rhs_part in raw_rules:
        for alt in rhs_part.split('|'):
            alt = alt.strip()
            if not alt:
                continue
            toks = ff_tokenize_rhs(alt)
            if not toks:
                toks = ['eps']
            g.productions[lhs].append(toks)

    return g


# =============================================================================
# HIGH-LEVEL API FUNCTIONS (new -- these assemble the JSON responses)
# =============================================================================

def run_derivation(grammar_text, target, mode):
    """mode: 'leftmost' or 'rightmost'"""
    grammar = parse_grammar_text(grammar_text)
    derive_fn = leftmost_derive_all if mode == "leftmost" else rightmost_derive_all
    all_results = derive_fn(grammar, target)

    if not all_results:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "message": f"String '{target}' cannot be derived from this grammar.",
        }

    steps, rules = all_results[0]
    tree = build_tree_from_steps(grammar, steps, use_leftmost=(mode == "leftmost"))

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "mode": mode,
        "steps": steps,
        "rules": rules[1:],  # first entry is always "" (the starting state)
        "tree_ascii": render_tree_ascii(tree),
        "alternate_path_count": len(all_results),
        "possibly_ambiguous": len(all_results) > 1,
    }


def run_parse_trees(grammar_text, target):
    grammar = parse_grammar_text(grammar_text)
    all_trees = build_all_parse_trees(grammar, target)
    unique_trees = get_unique_trees(all_trees)

    if not unique_trees:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "message": f"String '{target}' cannot be derived from this grammar.",
        }

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "tree_count": len(unique_trees),
        "trees_ascii": [render_tree_ascii(t) for t in unique_trees],
        "is_ambiguous": len(unique_trees) > 1,
    }


def run_ambiguity_check(grammar_text, target):
    grammar = parse_grammar_text(grammar_text)
    lm_all = leftmost_derive_all(grammar, target)
    rm_all = rightmost_derive_all(grammar, target)

    if not lm_all:
        return {
            "success": False,
            "grammar": grammar.to_dict(),
            "target": target,
            "message": f"String '{target}' cannot be derived from this grammar.",
        }

    lm_trees_all = [build_tree_from_steps(grammar, s, True) for s, _ in lm_all]
    rm_trees_all = [build_tree_from_steps(grammar, s, False) for s, _ in rm_all]

    def unique_indices(trees_all):
        idxs, seen = [], []
        for i, t in enumerate(trees_all):
            if not any(trees_are_equal(t, u) for u in seen):
                seen.append(t)
                idxs.append(i)
        return idxs

    lm_idx = unique_indices(lm_trees_all)
    rm_idx = unique_indices(rm_trees_all)

    lmd_entries = []
    for count, i in enumerate(lm_idx):
        steps, rules = lm_all[i]
        lmd_entries.append({
            "steps": steps,
            "rules": rules[1:],
            "tree_ascii": render_tree_ascii(lm_trees_all[i]),
        })

    rmd_entries = []
    for count, i in enumerate(rm_idx):
        steps, rules = rm_all[i]
        rmd_entries.append({
            "steps": steps,
            "rules": rules[1:],
            "tree_ascii": render_tree_ascii(rm_trees_all[i]),
        })

    lm_trees = [lm_trees_all[i] for i in lm_idx]
    rm_trees = [rm_trees_all[i] for i in rm_idx]

    is_ambiguous = (len(lm_trees) > 1) or (len(rm_trees) > 1)

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "target": target,
        "lmd_entries": lmd_entries,
        "rmd_entries": rmd_entries,
        "unique_lmd_count": len(lm_trees),
        "unique_rmd_count": len(rm_trees),
        "is_ambiguous": is_ambiguous,
        "verdict": (
            f"Grammar IS AMBIGUOUS for string '{target}' -- more than one distinct parse tree exists."
            if is_ambiguous else
            f"Grammar is NOT AMBIGUOUS for string '{target}' -- only one unique parse tree exists."
        ),
    }


def run_first_follow(grammar_text):
    grammar = parse_first_follow_grammar_text(grammar_text)
    first = grammar.compute_first()
    follow = grammar.compute_follow(first)

    return {
        "success": True,
        "non_terminals": grammar.non_terminals,
        "productions": {
            nt: [' '.join(p) for p in grammar.productions[nt]]
            for nt in grammar.non_terminals
        },
        "first_sets": {nt: sorted(first[nt]) for nt in grammar.non_terminals},
        "follow_sets": {nt: sorted(follow[nt]) for nt in grammar.non_terminals},
    }


if __name__ == "__main__":
    import json
    print("--- LMD test ---")
    print(json.dumps(run_derivation("E -> E+E | a | b | c", "a+b", "leftmost"), indent=2))
    print("--- Ambiguity test ---")
    print(json.dumps(run_ambiguity_check("E -> E+E | a | b | c", "a+b+c")["is_ambiguous"]))
    print("--- FIRST/FOLLOW test ---")
    print(json.dumps(run_first_follow("E -> T E'\nE' -> + T E' | eps\nT -> F\nF -> ( E ) | id"), indent=2))