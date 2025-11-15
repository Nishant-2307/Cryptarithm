# solver_basic.py

from itertools import permutations

def solve_send_more_money():
    letters = ('S','E','N','D','M','O','R','Y')
    
    for perm in permutations(range(10), len(letters)):
        assign = dict(zip(letters, perm))
        
        # S and M cannot be zero (leading digits)
        if assign['S'] == 0 or assign['M'] == 0:
            continue
        
        send = 1000*assign['S'] + 100*assign['E'] + 10*assign['N'] + assign['D']
        more = 1000*assign['M'] + 100*assign['O'] + 10*assign['R'] + assign['E']
        money = 10000*assign['M'] + 1000*assign['O'] + 100*assign['N'] + 10*assign['E'] + assign['Y']
        
        if send + more == money:
            return assign  # Success
    
    return None  # No solution found

if __name__ == "__main__":
    solution = solve_send_more_money()
    if solution:
        print("Solution found:")
        for k in sorted(solution.keys()):
            print(f"{k} = {solution[k]}")
    else:
        print("No solution")