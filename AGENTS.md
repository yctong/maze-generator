# AGENTS.md — Maze Generation & Coloring Sheet Engine

This document provides context, architectural specifications, design guidelines, and operational instructions for AI agents and developers working on this codebase.

---

## 1. Project Overview

The objective of this project is to generate **high-resolution, print-ready, mathematically guaranteed mazes** tailored for children's coloring sheets and puzzle books.

### Core Design Philosophy
- **Strictly Single Solution (Default):** Mazes are constructed as mathematical spanning trees (connected, acyclic graphs) ensuring exactly one valid path exists between **START** and **FINISH**.
- **Frequent Decision Junctions:** The true solution path repeatedly encounters multi-way intersections (T-junctions and 4-way forks) throughout early, middle, and late stages.
- **Deep Deceptive Decoys:** False paths are deep (5 to 40+ steps long) with their own twists and sub-branches, eliminating the "choose the longer corridor" visual shortcut.
- **Clean Minimalist Aesthetic:** High-contrast pure black lines on a white background with zero extraneous graphics, shading, or decorative clutter.

---

## 2. Repository Structure

```text
├── run_maze_generator.bat        # Interactive Windows launcher (presets, custom dims, batch, settings)
├── run_maze_generator.command    # Same launcher for macOS / Linux (double-clickable in Finder)
├── generate_maze_script.py       # Primary production script (High-Junction Single-Solution Generator)
├── generate_multi_path_maze.py   # Secondary script for braided/multi-route mazes (cycles enabled)
├── maze_coloring_sheet.md        # User-facing markdown artifact with interactive carousel previews
├── maze_001.png                  # Generated clean printable maze (1800 x 2400 px)
├── maze_001_solution.png         # Color-coded verified solution key for that sheet
└── AGENTS.md                     # Agent developer guide & specifications (this file)
```

---

## 3. Mathematical & Algorithmic Architecture

### Graph Representation
The maze is modeled on a 2D rectangular grid of size $R \times C$:
- **Vertices ($V$):** Grid cells $(r, c)$ where $0 \le r < R$ and $0 \le c < C$.
- **Edges ($E$):** Open passages between adjacent orthogonal cells.
- **Horizontal Walls (`h_walls`):** Array of shape $(R + 1, C)$ representing top/bottom cell boundaries.
- **Vertical Walls (`v_walls`):** Array of shape $(R, C + 1)$ representing left/right cell boundaries.

### Generator Pipeline (`HighJunctionSingleSolutionMaze`)
1. **Orphan-Free Primary Path Carving:** A self-avoiding random walk with anti-greedy heuristics carves a winding path covering 35%–45% of total grid cells from `(0, 0)` to `(R-1, C-1)` without leaving orphaned $1 \times 1$ dead pockets.
2. **Near-Miss Exit Lures:** Sprouted in the mid-path ($25\%-70\%$), deceptive lures aggressively race toward the FINISH and terminate $\le 2$ cells away against the outer/partition wall.
3. **Capacity-Checked Decoy Sprouting:** Decoy branches sprout only if they have room to grow $\ge 6$ cells deep, strictly avoiding branches in the final $18\%$ stretch before the exit.
4. **Decoy Absorption & Directional Momentum:** Residual empty spaces are absorbed into existing decoy paths rather than creating stubs on the main path, eliminating short dead ends and compact $2 \times 2$ coils.
5. **Boundary Openings:** The left wall of cell `(0, 0)` is opened for **START**, and the right wall of cell `(R-1, C-1)` is opened for **FINISH**.

---

## 4. Verification & Quality Metrics

When generating or modifying mazes, agents must evaluate and report the following metrics:

| Metric | Target / Standard | Description |
| :--- | :--- | :--- |
| **Solvability** | Exactly $1$ unique path | Verified via BFS pathfinder. |
| **Solution Length** | $35 \le \text{steps} \le 55$ | Ensures engaging navigation without overwhelming young kids. |
| **Decision Points** | $5 \le \text{forks} \le 9$ | High-impact decision forks on the solution path. Enforced by the seed scorer on grids of $\ge 100$ cells; see *Fork Band vs. Decoy Depth* below. |
| **Min Decoy Depth** | $\ge 5$ steps | Eliminates visually obvious 1-step/2-step short dead ends. |
| **Max Decoy Depth** | $\ge 15$ steps | Deepest false branch to prevent visual elimination shortcuts. |
| **Anti-Greedy Forks** | $\ge 2$ junctions | Forks where false paths move closer to goal than the true path. |
| **Near-Miss Exit Lures** | $\ge 1$ lure | Decoy reaching within $\le 2$ cells of the FINISH opening. |
| **Branches Near End** | $0$ branches | Zero distracting/useless branches in the final $15\%$ of the path. |
| **Resolution** | $1800 \times 2400\text{ px}$ | 3:4 portrait aspect ratio (standard 300 DPI for Letter/A4 printing). |
| **Wall Thickness** | $12\text{px} - 16\text{px}$ | Bold, clean lines easy for crayons and markers. |

---

## 5. Usage & CLI Reference

### Running the Generator

```powershell
# Auto-optimize and generate a deceptive maze (random candidate pool -> a
# different, comparably good maze on every run; the chosen seed is printed)
python generate_maze_script.py --rows 12 --cols 10 --outdir .

# Generate for younger kids (easier grid)
python generate_maze_script.py --rows 8 --cols 8 --outdir ./output

# Reproduce a specific maze with a known seed
python generate_maze_script.py --rows 12 --cols 10 --seed 232 --outdir .

# Replay an entire search run (same pool -> same winner)
python generate_maze_script.py --rows 12 --cols 10 --pool-seed 99 --outdir .

# Always take the single best candidate instead of one of the top 3
python generate_maze_script.py --rows 12 --cols 10 --top-k 1 --outdir .

# Legacy behaviour: scan seeds 1..max-search, same maze every time for a size
python generate_maze_script.py --rows 12 --cols 10 --deterministic --outdir .

# Generate several sheets in one run (maze_001..maze_010 plus solution keys)
python generate_maze_script.py --rows 12 --cols 10 --count 10 --outdir ./output

# Custom base name -> castle_001.png, castle_001_solution.png, ...
python generate_maze_script.py --rows 12 --cols 10 --name castle --outdir .

# Legacy fixed filenames: always rewrite single_solution_maze.png
python generate_maze_script.py --rows 12 --cols 10 --overwrite --outdir .
```

### Output Files

Each sheet is written as a numbered pair, `<name>_NNN.png` (clean) and
`<name>_NNN_solution.png` (key), where `<name>` defaults to `maze`. The counter
resumes past the highest number already present in `--outdir`, so a new run never
overwrites an earlier sheet - existing files are skipped, not replaced. `--count N`
generates N independently optimized sheets in one run; `--overwrite` restores the
old behaviour of always rewriting `single_solution_maze.png`.

`--count` is ignored (forced to 1) alongside `--seed` or `--deterministic`, since
both pin the output to one specific maze. With `--pool-seed`, only the first sheet
replays that search; the rest draw fresh pools so the batch stays varied.

### Fork Band vs. Decoy Depth

The 5-9 fork target and the "min decoy depth $\ge 5$" target compete for the same
resource: the free cells the solution path leaves behind. Below roughly 100 cells
there is not enough room for both - at $8 \times 8$, **zero of 400 sampled seeds**
satisfied both at once. Because *Zero Short Dead Ends* is the project's first
design rule, `score_seed` applies the fork-band bonus only when
`total_cells >= 100`; smaller sheets (the Junior $8 \times 8$ preset) keep deep
decoys and settle for ~4 forks. Grids at or above $10 \times 10$ hit both targets.

Branch carving is budgeted for the same reason: an unbudgeted DFS lets the first
decoy flood every free cell, which caps the solution at 2-4 forks. Each branch is
now limited to roughly `free_cells / (target + 1)` until enough distinct junctions
exist, after which leftover cells are absorbed back into existing decoys.


### Seed Selection

Without `--seed`, the generator samples `--max-search` candidate seeds at random
from a 10,000,000-wide space, scores each one, and picks at random among the
`--top-k` (default 3) highest scorers. Two runs at the same dimensions therefore
produce different sheets of comparable quality. Every run prints the seed it used
plus a ready-to-paste `--seed` command, so any sheet can be reproduced exactly.

### Python API Integration

```python
from generate_maze_script import HighJunctionSingleSolutionMaze

# 1. Initialize maze
maze = HighJunctionSingleSolutionMaze(rows=12, cols=10, seed=232)

# 2. Solve and analyze
solution, junctions = maze.solve()
print(f"Solution steps: {len(solution)}, Decision forks: {len(junctions)}")

# 3. Render printable sheet and solution
maze.render("output_maze.png", draw_solution=False, wall_thickness=14)
maze.render("output_solution.png", draw_solution=True, wall_thickness=14)
```

---

## 6. Guidelines for Future AI Agents

When interacting with this codebase or extending its features:
1. **Preserve Graph Integrity:** Never manually alter wall arrays without re-running BFS solvability and cycle checks.
2. **Maintain Clean Aesthetics:** Do not inject decorative cartoon illustrations, clip art, or grayscale shading into the maze canvas unless explicitly requested by the user.
3. **Respect Print Ratios:** Standard output canvases should maintain a 3:4 aspect ratio (e.g. $1800 \times 2400\text{ px}$) to match standard A4/US Letter coloring books.
4. **Always Render Both Files:** Whenever a new maze is generated, produce both the clean printable maze (`.png`) and the corresponding verified solution key (`_solution.png`).
