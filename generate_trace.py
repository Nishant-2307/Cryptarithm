# generate_trace.py

import json
from solver_csp import CryptarithmSolver

if __name__ == "__main__":
    solver = CryptarithmSolver(["SEND", "MORE"], "MONEY")
    trace = solver.solve()

    with open("trace.json", "w") as f:
        json.dump(trace, f, indent=2)

    print("Trace saved to trace.json")
