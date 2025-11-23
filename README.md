


## Quick Start


**View the Visualizer**
Open your browser to: [[http://127.0.0.1:5000](http://127.0.0.1:5000)](https://bruteforcekumar.pythonanywhere.com/)


## How to Use

1.  *Input Puzzle:* Enter the two addend words (e.g., CROSS + ROADS) and the result word (e.g., DANGER) in the top input boxes.
2.  *Select Algorithm:*
      * *Standard Backtracking:* Leave the settings as is.
      * *AC-3 Optimization:* Check the *AC-3* box to enable "Arc Consistency." This performs smart logic pruning to eliminate impossible numbers early, drastically reducing the search steps.
3.  *Solve:* Click *Solve* and wait for the status to show "Ready".
4.  *Visualize:*
      * *Play/Pause:* Use the controls to watch the algorithm build the search tree in real-time.
      * *Logic Panel:* Watch the bottom panel to see the line of pseudo code executing at each step.


# Cryptarithmetic CSP Solver & Visualizer

### What is Cryptarithmetic?

Cryptarithmetic (also known as verbal arithmetic or cryptarithms) is a type of mathematical puzzle where the digits in an arithmetic equation are replaced by letters. The goal is to find a unique digit (0-9) for each letter such that the equation holds true.

Standard rules for these puzzles include:

  * Each letter represents a unique digit.
  * The leading letter of a multi-digit number cannot be zero.
  * There is exactly one solution.

### Project Overview

The primary problem addressed by this project is the combinatorial explosion inherent in solving these puzzles. A standard puzzle involving 8 unique letters creates a search space of over 1.8 million possibilities ($10!/2!$). Solving equations like `SEND + MORE = MONEY` using naive brute-force methods creates a computationally expensive process. Furthermore, standard solvers often operate as "black boxes," offering no insight into the logical steps taken to reach a solution.

### Technical Approach

#### Constraint Satisfaction Problem (CSP)

We formulated the puzzle as a CSP. Instead of random guessing, the system utilizes a recursive backtracking engine that intelligently assigns digits to letters. A key innovation in our approach is treating arithmetic "carries" as distinct variables. This allows the system to validate mathematical consistency column-by-column rather than waiting for a full assignment.

#### AC-3 Algorithm (Arc Consistency)

To optimize performance, we integrated the AC-3 (Arc Consistency Algorithm \#3). This is a constraint satisfaction algorithm used to reduce the search space before and during the backtracking process.

AC-3 works by analyzing the constraints between variables (the "arcs" in the dependency graph). If a value in the domain of variable X cannot satisfy the constraint with any value in the domain of variable Y, that value is removed from X. This "pruning" propagates through the graph, eliminating impossible values early and drastically reducing the execution time.

#### Visualization

We wrapped this logic in a Flask-based API that serializes the algorithm’s internal state into a real-time JSON trace. This enables a granular, step-by-step visualization of the AI's decision-making process on a web frontend.

### Team Contributions

  * **Nishant:** Designed the core CSP variable mapping and implemented the fundamental recursive backtracking search architecture.
  * **Nishit:** Integrated the AC-3 algorithm to enforce arc consistency, optimizing the solver by pruning invalid domains early.  
  * **Atharva:** Built the Flask REST API and the "TraceWriter" system to capture the solver's state for real-time visualization.
  * **Siddharth:** Developed the specialized column-wise constraint logic, handling carry propagation to ensure mathematical validity.
