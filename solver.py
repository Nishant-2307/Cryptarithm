# solver.py
# Complete CSP solver for cryptarithms with optional AC-3 + carry column pruning.
# Produces trace.json (list of events) for visualization.

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
    trace = TraceWriter(trace_path)
    trace.add({"type": "START", "words": words, "result": result, "use_ac3": bool(use_ac3)})

    # Build letters set
    all_words = words + [result]
    letters = []
    for w in all_words:
        for ch in w:
            if ch not in letters:
                letters.append(ch)

    # carry variables: one per column (plus final), index 0 is least significant column carry-in (0)
    max_len = max(len(w) for w in all_words)
    # We'll index columns 0..max_len-1 from right (LSB)
    carry_vars = [f"C{idx}" for idx in range(max_len)]  # carry for column idx -> carry-out to next col
    # We'll treat carry for column -1 (incoming to LSB) as implicit zero, and last carry result must match any leading
    # Actually we create carries length = max_len (carry out of last column must be 0 or maybe equals leading letter)
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
    # Carries domain: 0..(number of addends) because sum could produce larger carry (but carry out per column is at most len(words))
    max_carry = len(words)
    for c in carry_vars:
        domains[c] = set(range(0, max_carry + 1))

    # Apply BUS/preset assignments
    assignment = {}
    if BUS:
        for k, val in BUS.items():
            if k in domains and val in domains[k]:
                assignment[k] = val
                domains[k] = {val}
            else:
                # inconsistent preset -> immediate fail
                trace.add({"type": "END", "result": None, "reason": "inconsistent BUS/preset"})
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
        """
        # Build reversed words with proper padding with ' ' for missing letters (treated as 0)
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
                    doms.append(sorted(cur_domains[v]))

            # Now brute force search small space (digits 0-9 and small carry)
            # For missing word letter (None) treat as 0 (i.e., contributes 0)
            found_support = False
            # We'll iterate over cartesian product of domains (pruned by trivial all-different)
            for prod_vals in product(*doms):
                mapping = dict(zip(keys, prod_vals))
                # map None letters -> 0 not present here since we didn't include None
                # Check all-different among letters (if two different letter variables have same digit it's invalid)
                violated = False
                seen_digits = {}
                for k, v in mapping.items():
                    if k in letters:  # only enforce all-different on letter variables
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
                        s += mapping.get(ch, None)
                        if mapping.get(ch, None) is None:
                            s = None
                            break
                if s is None:
                    continue
                cin = mapping.get(cin_var, 0) if cin_var else 0
                s += cin
                expected_digit = s % 10
                cout_expected = s // 10
                # result letter value:
                if res_letter is None:
                    # If there's no result letter, expected_digit must be 0
                    if expected_digit != 0:
                        continue
                else:
                    if mapping.get(res_letter, None) != expected_digit:
                        continue
                # carry out must match
                if mapping.get(cout_var, None) != cout_expected:
                    continue

                # if reached here, tuple is supported
                found_support = True
                break

            if not found_support:
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
            # a is supported if there exists b in Dj such that b != a
            # Equivalent: a is unsupported only if Dj == {a}
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
                dom_lists.append(sorted(doms[v]))

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
                for widx in range(len(words)):
                    ch = rev_words[widx][col]
                    if ch is None:
                        s += 0
                    else:
                        s += mapping[ch]
                cin = mapping.get(cin_var, 0) if cin_var else 0
                s += cin
                digit = s % 10
                cout_expected = s // 10
                # check result digit
                if res_letter is None:
                    if digit != 0:
                        continue
                else:
                    if mapping[res_letter] != digit:
                        continue
                if mapping[cout_var] != cout_expected:
                    continue
                # supported tuple -> mark values supported
                for k, v in mapping.items():
                    supported[k].add(v)

            # Now remove unsupported values
            for v in involved:
                to_remove = set(doms[v]) - supported[v]
                if to_remove:
                    doms[v] -= to_remove
                    removed_map[v].update(to_remove)

        return removed_map

    def run_ac3_propagation(doms, cur_assign):
        """
        Run AC-3 style propagation:
        - First, binary all-different revise passes until fixpoint
        - Then, column-wise carry pruning (n-ary) to remove unsupported values
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
                # if domain becomes empty -> inconsistent
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
                if not doms[v]:
                    return False, removed_events

        # Finally, quick feasibility check of carries/columns using assignment + doms
        if not carries_consistent_partial(cur_assign, doms):
            return False, removed_events

        return True, removed_events

    # ---------- Backtracking search ----------
    # keep order of variables: letters first (we'll pick MRV), then carries
    var_list = list(letters) + carry_vars

    # initial propagation if needed
    if use_ac3:
        ok, events = run_ac3_propagation(domains, assignment)
        for ev in events:
            trace.add(ev)
        if not ok:
            trace.add({"type": "END", "result": None, "reason": "AC3 inconsistency at start"})
            return None

    # helper: choose unassigned variable (MRV then degree)
    def select_unassigned_var(cur_assign, doms):
        unassigned = [v for v in var_list if v not in cur_assign]
        # MRV
        unassigned.sort(key=lambda v: (len(doms[v]), -len(neighbors[v]) if v in neighbors else 0))
        return unassigned[0] if unassigned else None

    steps = 0
    def backtrack(cur_assign, doms):
        nonlocal steps
        steps += 1
        # report current assignment and domains occasionally (front-end expects)
        trace.add({"type": "CURRENT_ASSIGNMENT", "assignment": {k: v for k, v in cur_assign.items()}})
        trace.add({"type": "CURRENT_DOMAINS", "domains": {k: sorted(list(doms[k])) for k in doms}})

        # check if complete
        if len(cur_assign) == len(var_list):
            # final check: full arithmetic correctness
            if carries_consistent_partial(cur_assign, doms):
                trace.add({"type": "END", "result": {k: cur_assign[k] for k in letters}})
                return {k: cur_assign[k] for k in letters}
            else:
                return None

        var = select_unassigned_var(cur_assign, doms)
        if var is None:
            return None

        # iterate values (order small->large)
        domain_vals = sorted(doms[var])
        for val in domain_vals:
            # check all-different conflict quickly
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
                    if other not in cur_assign and val in doms[other]:
                        doms[other].remove(val)

            # if var is carry or letter may affect domain by arithmetic - optionally run AC3
            consistent = True
            if use_ac3:
                ok, evs = run_ac3_propagation(doms, cur_assign)
                for e in evs:
                    trace.add(e)
                consistent = ok
            else:
                # light-weight partial-check to avoid obvious contradictions
                consistent = carries_consistent_partial(cur_assign, doms)

            if consistent:
                result = backtrack(cur_assign, doms)
                if result:
                    return result

            # failure -> undo
            trace.add({"type": "UNASSIGN", "var": var})
            del cur_assign[var]
            doms = doms_snapshot  # restore
            # make sure to sync the doms reference the caller expects by copying keys back
            for k in doms_snapshot:
                doms[k] = set(doms_snapshot[k])

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

    # ✅ Mark solver completion explicitly so /trace can detect it
    trace.add({
        "type": "SOLVER_DONE",
        "note": "Solver finished writing full trace."
    })

    return sol

