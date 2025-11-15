# solver_csp.py

import json
from itertools import permutations

class CryptarithmSolver:
    def __init__(self, words, result):
        self.words = words
        self.result = result
        self.letters = sorted(set("".join(words) + result))
        self.trace = []  # to store steps

    def log(self, type, data):
        self.trace.append({"type": type, **data})

    def is_valid(self, assignment):
        # Check unique values (all-different)
        if len(set(assignment.values())) < len(assignment):
            return False

        # Check leading zero rule
        for word in self.words + [self.result]:
            if word[0] in assignment and assignment[word[0]] == 0:
                return False

        # Partial cryptarithm check only if enough is assigned
        try:
            send_sum = sum(
                int("".join(str(assignment[c]) for c in word))
                for word in self.words
                if all(c in assignment for c in word)
            )
            if all(c in assignment for c in self.result):
                res_num = int("".join(str(assignment[c]) for c in self.result))
                if send_sum != res_num:
                    return False
        except KeyError:
            pass

        return True

    def solve(self):
        self.backtrack({})
        return self.trace

    def backtrack(self, assignment):
        if len(assignment) == len(self.letters):
            # Check final equality
            total = sum(int("".join(str(assignment[c]) for c in word)) for word in self.words)
            result_val = int("".join(str(assignment[c]) for c in self.result))
            if total == result_val:
                self.log("solution", {"assignment": assignment.copy()})
                return True
            return False

        unassigned = [l for l in self.letters if l not in assignment]
        var = unassigned[0]  # no MRV yet (keep simple first)

        for digit in range(10):
            self.log("try", {"letter": var, "value": digit})
            assignment[var] = digit

            if self.is_valid(assignment):
                if self.backtrack(assignment):
                    return True

            self.log("backtrack", {"letter": var, "value": digit})
            del assignment[var]

        return False
