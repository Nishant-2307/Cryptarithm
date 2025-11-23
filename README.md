# Search Tree Visualization Feature

## Overview
A new interactive **search tree visualization** has been added to the Cryptarithm CSP solver that shows the DFS (Depth-First Search) traversal of the solution space. This is a proper graph that can be solved topologically using DFS/BFS algorithms.

## Features

### Visual Elements
1. **Nodes**: Each node represents a **state** in the search space (a partial assignment)
   - **Root node**: Empty assignment `{}`
   - **Child nodes**: States after making an assignment decision
   - Each node shows all assignments made up to that point (e.g., `C=6\nR=4\nD=1`)

2. **Edges**: Directed edges show assignment decisions
   - Edge labels show the variable and value assigned (e.g., `C=6`)
   - Arrows point from parent state to child state

3. **Node Colors**:
   - **Gray **: Root node
   - **Light Gray **: Explored nodes (visited but not on current path)
   - **Light Green **: Nodes on the current path from root to current node
   - **Yellow **: Current node being explored
   - **Pink **: Dead ends (nodes that led to backtracking)
   - **Green **: Solution path (when solution is found)

### Tree Structure
- **Hierarchical Layout**: Top-down tree showing parent-child relationships
- **DFS Traversal**: The tree shows how DFS explores the search space
- **Backtracking**: When backtracking occurs, we move back up the tree to the parent node
- **Solution Path**: The path from root to solution is highlighted in green

### Interactive Features
- **Pan**: Click and drag the background to move the view
- **Zoom**: Use mouse wheel to zoom in/out
- **Auto-focus**: The view automatically centers on the current node being explored

### Animation
The tree updates in real-time as the solver progresses:
1. **ASSIGN events**: Create new child nodes and move down the tree
2. **UNASSIGN events**: Mark nodes as dead ends (pink) and move back up to parent
3. **Current path**: Highlighted in light green from root to current node
4. **Current node**: Highlighted in yellow with auto-focus
5. **Solution found**: Entire solution path turns green

## How It Works

### Building the Search Tree
1. **Parse trace events**: Read ASSIGN/UNASSIGN events from the trace
2. **Track state stack**: Maintain a stack of nodes representing the current DFS path
3. **Create nodes**: Each ASSIGN creates a new child node with updated assignment
4. **Create edges**: Connect parent to child with labeled edge showing the decision
5. **Handle backtracking**: UNASSIGN pops from stack and marks node as dead end

### DFS Traversal Visualization
- The tree structure naturally shows DFS traversal order
- Each level represents the depth of the search
- Siblings at the same level show different value choices for the same variable
- The animation shows the DFS exploration in real-time

### Topological Properties
- **DAG (Directed Acyclic Graph)**: The tree is a DAG with root at top
- **Can be solved with DFS**: The tree structure itself represents DFS traversal
- **Can be solved with BFS**: Could traverse level-by-level (breadth-first)
- **Solution path**: A path from root to a leaf node where all constraints are satisfied

## Usage

1. **Start the solver**: Enter your cryptarithm puzzle and click "Solve"
2. **Wait for completion**: The status will show "Done — Trace Ready!"
3. **Start animation**: Click "Start Animation" to begin the visualization
4. **Watch the search tree**: Observe how the DFS algorithm:
   - Explores down the tree (making assignments)
   - Backtracks when hitting dead ends
   - Eventually finds the solution path (or exhausts all possibilities)

The search tree visualization appears above the assignment/domain panels and provides a complete view of the search space exploration.

## Technical Details

### Libraries Used
- **vis-network**: A powerful JavaScript library for network/graph visualization
- Loaded via CDN: `https://unpkg.com/vis-network/standalone/umd/vis-network.min.js`

### Key Functions
- `buildSearchTreeFromEvents(events)`: Parses trace events and builds the tree structure
- `initializeSearchTree()`: Creates and renders the search tree using vis.js
- `highlightCurrentNode(eventIndex)`: Updates node colors to show current state
- Tree updates are integrated into the existing `renderEvent()` function

### Layout
- The page now uses a wider container (1400px) to accommodate the tree
- Assignment/domains and trace log are displayed side-by-side in a two-column layout
- Search tree takes full width above these panels
- Hierarchical layout with root at top, growing downward

## Understanding the Search Tree

### Example
For a simple puzzle like `A + B = C`:
```
                    ROOT {}
                      |
        +-------------+-------------+
        |             |             |
      A=1           A=2           A=3
        |             |             |
    +---+---+     +---+---+     +---+---+
    |   |   |     |   |   |     |   |   |
  B=0 B=2 B=3   B=0 B=1 B=3   B=0 B=1 B=2
    |   |   |     |   |   |     |   |   |
   ...  ✓  ...   ...  ✓  ...   ...  ✓  ...
```

- Each level represents a variable assignment decision
- Branches show different value choices
- Dead ends (✗) are marked in pink
- Solution paths (✓) are marked in green

### DFS vs BFS
- **Current implementation**: Shows DFS traversal (depth-first)
- **DFS**: Explores one branch completely before trying another
- **BFS**: Would explore all nodes at one level before going deeper
- The tree structure supports both traversal methods

## Future Enhancements
Possible improvements:
- Add BFS traversal mode (level-by-level exploration)
- Show node visit order numbers
- Highlight pruned branches (AC-3 pruning)
- Show domain sizes at each node
- Add tree statistics (total nodes, max depth, branching factor)
- Export tree as image or DOT format
- Collapsible subtrees for large search spaces
- Side-by-side comparison of different heuristics
