"""
first_follow.py
Part C of the toolkit: FIRST(X) and FOLLOW(A) set computation for a
user-typed grammar. Supports MULTI-CHARACTER symbols (E, E', T1, id),
unlike grammar_tools.py which is restricted to single characters.

Direct port of the user's own console tool (Part C of their combined
script). The only real change: the interactive input loop is replaced by
parse_ff_grammar_text(), which parses a grammar typed into a <textarea>
and submitted all at once, and everything raises GrammarError with a
clear message instead of printing "! ..." warnings to a console.

Grammar format (spaces optional):
    E -> T E'
    E' -> + T E' | eps
    T -> F T'
    T' -> * F T' | eps
    F -> ( E ) | id
Use 'eps' (or 'epsilon') for epsilon. Non-terminals are written starting
with an uppercase letter (E, E', T1, ...); anything else (lowercase
words, symbols) is treated as a terminal, with 'id' recognized as a
single terminal token.
"""

from collections import OrderedDict


class GrammarError(Exception):
    """Raised for anything wrong with the grammar the user typed."""
    pass


# ------------------------------------------------------------
# GRAMMAR (multi-character symbols)
# ------------------------------------------------------------
class FirstFollowGrammar:
    def __init__(self):
        self.productions = OrderedDict()  # lhs -> list of rhs (each rhs a list of tokens)
        self.non_terminals = []           # insertion order
        self.eps = 'eps'

    def is_non_terminal(self, sym):
        # A symbol is non-terminal ONLY if it appears on the left of some rule.
        return sym in self.productions

    def add_production(self, lhs, rhs):
        if lhs not in self.productions:
            self.productions[lhs] = []
            self.non_terminals.append(lhs)
        self.productions[lhs].append(rhs)

    # --------- FIRST ---------
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
                        if not self.is_non_terminal(sym):  # terminal
                            if sym not in first[lhs]:
                                first[lhs].add(sym)
                                changed = True
                            break
                        else:  # non-terminal
                            before = len(first[lhs])
                            first[lhs].update(first[sym] - {self.eps})
                            if len(first[lhs]) != before:
                                changed = True
                            if self.eps not in first[sym]:
                                break
                    else:  # all symbols nullable
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

    # --------- FOLLOW ---------
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

    def to_dict(self):
        return {
            "rules": [
                f"{lhs} -> " + " | ".join(" ".join(p) for p in self.productions[lhs])
                for lhs in self.non_terminals
            ],
            "start_symbol": self.non_terminals[0] if self.non_terminals else None,
            "non_terminals": list(self.non_terminals),
        }


# ------------------------------------------------------------
# TOKENIZER that works with and without spaces
# ------------------------------------------------------------
def ff_tokenize_no_space(s):
    res = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "'":  # attach to previous token, e.g. E'
            if res:
                res[-1] += "'"
            i += 1
        elif c.isupper():  # Non-terminal E, E', T1
            tok = c
            i += 1
            while i < len(s) and s[i] in "'0123456789":
                tok += s[i]
                i += 1
            res.append(tok)
        elif c.islower():  # id, eps, a, b...
            j = i
            while j < len(s) and s[j].islower():
                j += 1
            word = s[i:j]
            if word in ('eps', 'epsilon', 'null') or word == '\u03b5':
                res.append('eps')
            elif word == 'id':
                res.append('id')
            else:
                # "ab" without space -> a b, except id/eps
                for ch in word:
                    res.append(ch)
            i = j
        elif c == '\u03b5':
            res.append('eps')
            i += 1
        elif c in ('|', '-', '>', '\u2192'):
            i += 1  # ignore arrow chars here
        else:  # + * ( ) etc
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


def parse_ff_grammar_text(text):
    """
    Parses FIRST/FOLLOW grammar text typed by the user into a
    FirstFollowGrammar object. Raises GrammarError with a message
    pointing at the bad line.
    """
    g = FirstFollowGrammar()
    lhs_order = []
    raw_rules = []  # (lhs, rhs_alts_str)
    any_line = False

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        any_line = True
        if '->' not in line:
            raise GrammarError(f"Line {line_num}: missing '->'. Use format: LHS -> RHS1 | RHS2")
        lhs_part, rhs_part = line.split('->', 1)
        lhs_tokens = ff_tokenize_no_space(lhs_part.strip())
        if not lhs_tokens:
            raise GrammarError(f"Line {line_num}: no left-hand side symbol found.")
        lhs = lhs_tokens[0]
        raw_rules.append((lhs, rhs_part))
        if lhs not in lhs_order:
            lhs_order.append(lhs)

    if not any_line:
        raise GrammarError("No grammar rules were entered.")

    # Register all LHS symbols first so multi-char non-terminals are
    # recognized correctly no matter which line they're used on.
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

    if not g.productions:
        raise GrammarError("No grammar rules were entered.")

    return g


# ------------------------------------------------------------
# HIGH-LEVEL API FUNCTION (called directly by app.py)
# ------------------------------------------------------------
def run_first_follow(grammar_text):
    grammar = parse_ff_grammar_text(grammar_text)

    first = grammar.compute_first()
    follow = grammar.compute_follow(first)

    return {
        "success": True,
        "grammar": grammar.to_dict(),
        "first_sets": [
            {"symbol": nt, "set": sorted(first[nt])} for nt in grammar.non_terminals
        ],
        "follow_sets": [
            {"symbol": nt, "set": sorted(follow[nt])} for nt in grammar.non_terminals
        ],
    }
