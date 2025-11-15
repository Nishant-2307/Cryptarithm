# solver.py
# Patched CSP solver for cryptarithms with optional AC-3 + carry column pruning.
# Produces trace.json (list of events) for visualization.
# - Normalizes input to uppercase
# - Emits initial CURRENT_ASSIGNMENT / CURRENT_DOMAINS snapshot
# - Performs explicit numeric equality check at completion to avoid false positives
# - Keeps AC-3 + column carry propagation and top-carry enforcement

import json
import copy
from collections import deque, defaultdict
from itertools import product

# ---------- Trace utilities ----------
class TraceWriter:
    def __init__(self, path="trace.json"):
        self.path = path
        self.events = []
        self._write_now()  # create/overwrite file

    def _write_now(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=2)

    def add(self, ev):
        self.events.append(ev)
        # write after every event so front-end can poll/update
        self._write_now()

# ---------- Main solver API ----------
def solve_cryptarithm(words, result, BUS=None, use_ac3=False, trace_path="trace.json"):
    """
    words: list of addend words (strings), e.g. ["SEND", "MORE"]
    result: result word (string), e.g. "MONEY"
    BUS: optional dict of presets {letter: digit}
    use_ac3: whether to run AC-3 + carry column pruning as propagation
    trace_path: where to write trace.json
    Returns: mapping letter->digit if solution found else None
    """
    # Normalize to uppercase so lowercase input works
    words = [w.upper() for w in words]
    result = result.upper()

    trace = TraceWriter(trace_path)
    trace.add({"type": "START", "words": words, "result": result, "use_ac3": bool(use_ac3)})

    # Build letters set (preserve order encountered)
    all_words = words + [result]
    letters = []
    for w in all_words:
        for ch in w:
            if ch not in letters:
                letters.append(ch)

    # Determine max columns (based on longest among addends and result)
    max_len = max(len(w) for w in all_words)

    # carry variables: one per column (carry-out of column i stored in C{i})
    carry_vars = [f"C{idx}" for idx in range(max_len)]

    variables = list(letters) + carry_vars

    # Domains
    domains = {}
    digits = set(range(10))
    leading_letters = set(w[0] for w in all_words if len(w) > 1)
    for v in letters:
        if v in leading_letters:
            domains[v] = set(range(1, 10))  # leading letter cannot be 0
        else:
            domains[v] = set(range(0, 10))
    # Carries domain: 0..(number of addends)
    max_carry = len(words)
    for c in carry_vars:
        domains[c] = set(range(0, max_carry + 1))

    # Apply BUS/preset assignments
    assignment = {}
    if BUS:
        # normalize BUS keys to uppercase
        BUS2 = {k.upper(): v for k, v in BUS.items()}
        for k, val in BUS2.items():
            if k in domains and val in domains[k]:
                assignment[k] = val
                domains[k] = {val}
            else:
                trace.add({"type": "END", "result": None, "reason": "inconsistent BUS/preset"})
                trace.add({"type": "SOLVER_DONE", "note": "Solver finished writing full trace."})
                return None

    # Neighbors (for all-different)
    neighbors = defaultdict(set)
    for a in letters:
        for b in letters:
            if a != b:
                neighbors[a].add(b)

    # Utility: get current domains snapshot
    def snapshot_domains(d):
        return {k: set(v) for k, v in d.items()}

    # ---------- Utility: evaluate numeric sum when fully assigned ----------
    def evaluate_full_assignment(assign):
        """Return True iff numeric sum(words) == numeric result given assign for all letters."""
        # build numbers by concatenating digits; if any leading letter is assigned 0 (shouldn't happen), reject
        def word_value(w):
            s = "".join(str(assign[ch]) for ch in w)
            return int(s)
        try:
            addends = [word_value(w) for w in words]
            resval = word_value(result)
            return sum(addends) == resval
        except Exception:
            # any missing mapping -> not fully evaluatable
            return False

    # ---------- Constraint checks ----------
    def all_different_consistent(var, val, cur_assign):
        # var assigned val should not conflict with already assigned neighbors
        for n in neighbors[var]:
            if n in cur_assign and cur_assign[n] == val:
                return False
        return True

    def carries_consistent_partial(cur_assign, cur_domains):
        """
        Check full-column feasibility given current domains/assignments.
        This function scans all columns and checks whether there exists at least one supporting tuple
        for each column's variables (operands, result letter, carry_in, carry_out). If some column
        has zero supporting tuples for the current domains and assignments -> inconsistency.

        Additionally enforces that the topmost carry is zero when the result has no extra leading digit.
        """
        # Build reversed words with proper padding (None for missing letters)
        rev_words = []
        for w in words:
            rev = list(w[::-1]) + [None] * (max_len - len(w))
            rev_words.append(rev)
        rev_result = list(result[::-1]) + [None] * (max_len - len(result))

        # For each column index
        for col in range(max_len):
            op_letters = [rev_words[a][col] for a in range(len(words))]  # maybe None
            res_letter = rev_result[col]  # maybe None
            cin_var = f"C{col-1}" if col-1 >= 0 else None
            cout_var = f"C{col}"

            # Variables involved: any non-None letters + carry in/out
            involved = []
            for L in op_letters:
                if L is not None:
                    involved.append(L)
            if res_letter is not None:
                involved.append(res_letter)
            if cin_var:
                involved.append(cin_var)
            involved.append(cout_var)

            # Build domain lists for each involved (respecting current assignments)
            doms = []
            keys = []
            for v in involved:
                keys.append(v)
                if v in cur_assign:
                    doms.append([cur_assign[v]])
                else:
                    # if domain missing (shouldn't happen) treat as empty
                    doms.append(sorted(cur_domains.get(v, [])))

            # Now brute force search small space (digits 0-9 and small carry)
            found_support = False
            # iterate over cartesian product (may be heavy but columns/domains small typically)
            for prod_vals in product(*doms):
                mapping = dict(zip(keys, prod_vals))

                # Check all-different among letters (if two different letter variables have same digit it's invalid)
                violated = False
                seen_digits = {}
                for k, v in mapping.items():
                    if k in letters:
                        if v in seen_digits and seen_digits[v] != k:
                            violated = True
                            break
                        seen_digits[v] = k
                if violated:
                    continue

                # Compute column sum:
                s = 0
                for widx in range(len(words)):
                    ch = rev_words[widx][col]
                    if ch is None:
                        s += 0
                    else:
                        val = mapping.get(ch, None)
                        if val is None:
                            s = None
                            break
                        s += val
                if s is None:
                    continue

                cin = mapping.get(cin_var, 0) if cin_var else 0
                s += cin
                expected_digit = s % 10
                cout_expected = s // 10

                # result letter value:
                if res_letter is None:
                    # If there's no result letter in this column, expected_digit must be 0
                    if expected_digit != 0:
                        continue
                else:
                    if mapping.get(res_letter, None) != expected_digit:
                        continue

                # carry out must match
                if mapping.get(cout_var, None) != cout_expected:
                    continue

                # supported tuple found
                found_support = True
                break

            if not found_support:
                return False

        # Enforce final/top carry = 0 when result doesn't have extra leading digit
        top_c = f"C{max_len-1}"
        # If result's length is <= max_len (i.e., no extra digit beyond column range), top carry must be zero.
        # (Note: max_len already is max length among addends and result; this check ensures no leftover carry.)
        if len(result) <= max_len:
            if top_c in cur_assign:
                if cur_assign[top_c] != 0:
                    return False
            else:
                if 0 not in cur_domains.get(top_c, set()):
                    return False

        return True

    # ---------- AC-3 for all-different + column pruning ----------
    def revise_all_diff(Xi, Xj, doms):
        """
        Revise domain of Xi wrt Xj for all-different.
        Remove a value a from doms[Xi] if for every b in doms[Xj], constraint Xi != Xj is violated
        i.e., if doms[Xj] == {a} then Xi cannot be a.
        """
        removed = set()
        Dj = doms[Xj]
        for a in list(doms[Xi]):
            if len(Dj) == 1 and a in Dj:
                removed.add(a)
        if removed:
            doms[Xi] -= removed
        return removed

    def prune_column_columnwise(doms):
        """
        For each column, compute the set of supported values for each involved variable
        by enumerating possible tuples. Remove unsupported values.
        Returns a dict var->set(removed_values)
        """
        removed_map = defaultdict(set)

        rev_words = []
        for w in words:
            rev = list(w[::-1]) + [None] * (max_len - len(w))
            rev_words.append(rev)
        rev_result = list(result[::-1]) + [None] * (max_len - len(result))

        for col in range(max_len):
            op_letters = [rev_words[a][col] for a in range(len(words))]
            res_letter = rev_result[col]
            cin_var = f"C{col-1}" if col-1 >= 0 else None
            cout_var = f"C{col}"

            involved = []
            for L in op_letters:
                if L is not None:
                    involved.append(L)
            if res_letter is not None:
                involved.append(res_letter)
            if cin_var:
                involved.append(cin_var)
            involved.append(cout_var)

            # build domain lists
            dom_lists = []
            keys = []
            for v in involved:
                keys.append(v)
                dom_lists.append(sorted(doms.get(v, [])))

            # For each variable, track supported values
            supported = {v: set() for v in involved}
            # iterate cartesian product
            for prod_vals in product(*dom_lists):
                mapping = dict(zip(keys, prod_vals))
                # all-different among letters
                violate = False
                seen = {}
                for k, val in mapping.items():
                    if k in letters:
                        if val in seen and seen[val] != k:
                            violate = True
                            break
                        seen[val] = k
                if violate:
                    continue
                # compute column arithmetic
                s = 0
                skip = False
                for widx in range(len(words)):
                    ch = rev_words[widx][col]
                    if ch is None:
                        s += 0
                    else:
                        # mapping should have ch
                        if ch not in mapping:
                            skip = True
                            break
                        s += mapping[ch]
                if skip:
                    continue
                cin = mapping.get(cin_var, 0) if cin_var else 0
                s += cin
                digit = s % 10
                cout_expected = s // 10
                # check result digit
                if res_letter is None:
                    if digit != 0:
                        continue
                else:
                    if mapping.get(res_letter) != digit:
                        continue
                if mapping.get(cout_var) != cout_expected:
                    continue
                # supported tuple -> mark values supported
                for k, v in mapping.items():
                    supported[k].add(v)

            # Now remove unsupported values
            for v in involved:
                to_remove = set(doms.get(v, set())) - supported[v]
                if to_remove:
                    doms[v] = set(doms.get(v, set())) - to_remove
                    removed_map[v].update(to_remove)

        # After pruning, ensure top carry domain contains 0 when required
        top_c = f"C{max_len-1}"
        if len(result) <= max_len:
            if 0 not in doms.get(top_c, set()):
                # make top carry domain empty to indicate inconsistency
                removed_map[top_c].update(set(doms.get(top_c, set())))
                doms[top_c] = set()

        return removed_map

    def run_ac3_propagation(doms, cur_assign):
        """
        Run AC-3 style propagation:
        - binary all-different revise passes until fixpoint
        - column-wise carry pruning (n-ary) to remove unsupported values
        Returns tuple (consistent: bool, removed_events: list)
        """
        removed_events = []

        # All-different AC-3 using queue of binary arcs
        queue = deque()
        for Xi in letters:
            for Xj in neighbors[Xi]:
                queue.append((Xi, Xj))
        while queue:
            Xi, Xj = queue.popleft()
            removed = revise_all_diff(Xi, Xj, doms)
            if removed:
                removed_events.append({"type": "AC3_PRUNE", "var": Xi, "removed": sorted(list(removed))})
                if not doms[Xi]:
                    return False, removed_events
                for Xk in neighbors[Xi]:
                    if Xk != Xj:
                        queue.append((Xk, Xi))

        # Column-wise carry pruning (n-ary)
        removed_map = prune_column_columnwise(doms)
        for v, removed in removed_map.items():
            if removed:
                removed_events.append({"type": "AC3_PRUNE", "var": v, "removed": sorted(list(removed))})
                if not doms.get(v, set()):
                    return False, removed_events

        # Finally, quick feasibility check of carries/columns using assignment + doms
        if not carries_consistent_partial(cur_assign, doms):
            return False, removed_events

        return True, removed_events

    # ---------- Backtracking search ----------
    # keep order of variables: letters first (we'll pick MRV), then carries
    var_list = list(letters) + carry_vars

    # emit initial snapshot so front-end sees starting domains/assignment
    trace.add({"type": "CURRENT_ASSIGNMENT", "assignment": {k: v for k, v in assignment.items()}})
    trace.add({"type": "CURRENT_DOMAINS", "domains": {k: sorted(list(domains[k])) for k in domains}})

    # initial propagation if needed
    if use_ac3:
        ok, events = run_ac3_propagation(domains, assignment)
        for ev in events:
            trace.add(ev)
        if not ok:
            trace.add({"type": "END", "result": None, "reason": "AC3 inconsistency at start"})
            trace.add({"type": "SOLVER_DONE", "note": "Solver finished writing full trace."})
            return None

    # helper: choose unassigned variable (MRV then degree)
    def select_unassigned_var(cur_assign, doms):
        unassigned = [v for v in var_list if v not in cur_assign]
        # MRV then degree heuristic
        unassigned.sort(key=lambda v: (len(doms.get(v, set())), -len(neighbors[v]) if v in neighbors else 0))
        return unassigned[0] if unassigned else None

    steps = 0
    def backtrack(cur_assign, doms):
        nonlocal steps
        steps += 1
        # report current assignment and domains (front-end expects to see progress)
        trace.add({"type": "CURRENT_ASSIGNMENT", "assignment": {k: v for k, v in cur_assign.items()}})
        trace.add({"type": "CURRENT_DOMAINS", "domains": {k: sorted(list(doms.get(k, set()))) for k in doms}})

        # check if complete
        if len(cur_assign) == len(var_list):
            # final check: full arithmetic correctness (numeric equality)
            # first ensure per-column carry consistency
            if not carries_consistent_partial(cur_assign, doms):
                return None
            # then evaluate the full numeric equality
            # build mapping for letters only
            letter_map = {k: cur_assign[k] for k in letters if k in cur_assign}
            if set(letter_map.keys()) == set(letters):
                if evaluate_full_assignment(letter_map):
                    trace.add({"type": "END", "result": {k: cur_assign[k] for k in letters}})
                    return {k: cur_assign[k] for k in letters}
                else:
                    # numeric mismatch; treat as failure and continue search
                    return None
            else:
                # not all letter values assigned (shouldn't happen here) -> fail
                return None

        var = select_unassigned_var(cur_assign, doms)
        if var is None:
            return None

        # iterate values (order small->large)
        domain_vals = sorted(doms.get(var, []))
        for val in domain_vals:
            # quick all-different conflict check for letter variables
            if var in letters and not all_different_consistent(var, val, cur_assign):
                continue

            # make assignment
            cur_assign[var] = val
            trace.add({"type": "ASSIGN", "var": var, "value": val})
            # snapshot domains and then reduce
            doms_snapshot = snapshot_domains(doms)

            # forward checking: remove val from other letter domains (all-different)
            if var in letters:
                for other in neighbors[var]:
                    if other not in cur_assign and val in doms.get(other, set()):
                        doms[other] = set(doms.get(other, set())) - {val}

            # run AC3 or lightweight check
            consistent = True
            if use_ac3:
                ok, evs = run_ac3_propagation(doms, cur_assign)
                for e in evs:
                    trace.add(e)
                consistent = ok
            else:
                consistent = carries_consistent_partial(cur_assign, doms)

            if consistent:
                result = backtrack(cur_assign, doms)
                if result:
                    return result

            # failure -> undo
            trace.add({"type": "UNASSIGN", "var": var})
            del cur_assign[var]
            # restore domains (deep restore)
            restored = snapshot_domains(doms_snapshot)
            for k in doms:
                doms[k] = set(restored.get(k, set()))

        return None

    sol = backtrack(dict(assignment), snapshot_domains(domains))
    if sol is None:
        trace.add({
            "type": "END",
            "result": None,
            "reason": "no solution found",
            "steps": steps
        })
    else:
        trace.add({
            "type": "END",
            "result": sol,
            "reason": "solution found",
            "steps": steps
        })

    # Mark solver completion explicitly so /trace can detect it
    trace.add({
        "type": "SOLVER_DONE",
        "note": "Solver finished writing full trace."
    })

    return sol
