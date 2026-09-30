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
├── run_maze_generator.bat        # Interactive Windows launcher (presets, custom dims, batch, style/layout/page settings)
├── run_maze_generator.command    # Same launcher for macOS / Linux (double-clickable in Finder)
├── generate_maze_script.py       # The generator: all styles, layouts, loops (--loops braids a maze), rendering, PDF books
├── .gitignore                    # Keeps __pycache__ and generated sheets out of git
└── AGENTS.md                     # Agent developer guide & specifications (this file)
```

Generated sheets (`maze_NNN.png` + `maze_NNN_solution.png`, `*_book.pdf`) are written to
`--outdir` and are not tracked.

```text
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
1. **Pocket-Free Primary Path Carving:** A self-avoiding random walk with anti-greedy heuristics carves a winding path covering 28%–48% of total grid cells from START to FINISH. It never seals off a pocket too small to hold a $\ge 5$-step decoy (`min_comp_size`, 6 cells): at the old 3-cell floor, such pockets produced most sub-5-step decoys. For its first quarter the walk also shies away from cells touching its own path, so it doesn't coil tightly in the START corner and leave no room for an early decision.
2. **Reserved End Forks:** One fork is tried just after START (first 12% of the path) and one just before the no-branch zone (70%–85%), *before* the lures claim the space around FINISH. Without this the first decision came ~11 steps in and the last ~27% of the path was fork-free, so tracing backwards from FINISH was a free shortcut.
3. **Near-Miss Exit Lures:** Sprouted in the mid-path ($25\%-70\%$), deceptive lures aggressively race toward the FINISH and terminate $\le 2$ cells away against the outer/partition wall.
4. **Capacity-Checked Decoy Sprouting:** Decoy branches sprout only where there is room for a deep decoy, never in the final $15\%$ of the path. Until one 4-way fork exists (two on grids of 300+ cells), a path cell that gets a decoy also tries its opposite free side, giving the solution a genuine three-way choice. Decoys keep mild directional momentum (1.6x): enough to avoid $2 \times 2$ coils, not so much that they become straight corridors whose dead end is visible from the fork.
5. **Decoy Absorption:** Residual empty spaces are absorbed into existing decoy paths. A pocket walled in by the solution path alone is first absorbed *into* the solution as a detour (a route covering every pocket cell replaces one path step), and only hangs off the path as a short fork when no such route exists.
6. **Stub Rewiring:** 1-cell dead ends (a leaf hanging straight off a junction) are removed by tree edge swaps: open a wall next to the stub, then remove another edge of the cycle this creates. A swap is kept only if it strictly reduces the stub count. Edges touching the solution path are never added or removed, except that a 1-step decoy hanging off the path (itself a stub) may be re-hung elsewhere. This roughly halves the 1-cell notches.
7. **Boundary Openings:** By default (`--layout corners`) the left wall of cell `(0, 0)` is opened for **START**, and the right wall of cell `(R-1, C-1)` is opened for **FINISH**. Other layouts put the openings on any pair of opposite walls; the whole pipeline works from `self.start` / `self.goal`, never hard-coded corners.

The walk's reachability test is a goal-directed depth-first search over precomputed
neighbour tables: it answers the same yes/no as a full flood fill, but touches roughly
one corridor of cells instead of the whole board (~2x faster at 12x10, ~7x at 30x30).

**Seed compatibility:** a seed always rebuilds the same maze *within* a version, but the
design changes above (pocket floor, reserved end forks, 4-way forks, detours, stub rewiring)
consume randomness differently, so seeds printed by earlier versions produce different
mazes now.

### Generation Styles (`--style`)

| Style | Character |
| :--- | :--- |
| `deceptive` (default) | The pipeline above: deep decoys, anti-greedy forks, near-miss exit lures |
| `backtracker` | Recursive backtracker: long twisting corridors, few dead ends |
| `prim` | Randomized Prim: many short branches, busy look |
| `kruskal` | Randomized Kruskal: even mix of short and medium dead ends |
| `wilson` | Wilson's algorithm: unbiased uniform spanning tree |
| `hunt-kill` | Hunt-and-kill: long winding passages, straighter runs |

Every style yields a perfect maze (spanning tree, exactly one solution). `--loops N`
then knocks through up to N dead ends to braid the maze: this deliberately creates
cycles (multiple routes), the solution key shows the shortest one, and the spec
printout says so instead of claiming a tree.

### Layouts (`--layout`)

`corners` (default; consumes no randomness), `sides`
(left wall to right wall, random rows), `top-bottom` (top wall to bottom wall,
random columns) and `random` (a random pair of opposite walls, possibly reversed).
Positions come from the seeded RNG, so `--seed` still pins the whole sheet.

---

## 4. Verification & Quality Metrics

When generating or modifying mazes, agents must evaluate and report the following metrics:

`design_metrics()` computes all of these in one place, and both the seed scorer and the
printed spec sheet use it. A candidate "meets spec" when it hits every hard target
below; 4-way forks and 1-cell dead ends only move the score.

Measured over 15 default search runs per size (earlier version → current):

| Grid | Winners meeting spec | Candidates scored | First decision | 1-cell dead ends | 4-way forks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 12x10 | 6/15 → **15/15** | 589 → 272 | step 10.7 → 2.3 | 6.0 → 1.9 | 0.07 → 0.47 |
| 16x12 | 12/15 → **15/15** | 192 → 61 | step 12.2 → 4.9 | 8.6 → 2.5 | 0 → 0.53 |
| 20x15 | 14/15 → **15/15** | 125 → 58 | step 17.1 → 6.4 | 11.6 → 4.3 | 0.07 → 0.73 |

The "current" column is measured against the stricter targets (early decision and
decoy turns included).

| Metric | Target / Standard | Description |
| :--- | :--- | :--- |
| **Solvability** | Exactly $1$ unique path | Verified via BFS pathfinder. |
| **Solution Length** | $35 \le \text{steps} \le 55$ | Ensures engaging navigation without overwhelming young kids. |
| **Decision Points** | $5 \le \text{forks} \le 9$ | High-impact decision forks on the solution path. Enforced by the seed scorer on grids of $\ge 100$ cells; see *Fork Band vs. Decoy Depth* below. |
| **Min Decoy Depth** | $\ge 5$ steps | Eliminates visually obvious 1-step/2-step short dead ends. |
| **Max Decoy Depth** | $\ge 15$ steps | Deepest false branch to prevent visual elimination shortcuts. |
| **Anti-Greedy Forks** | $\ge 2$ junctions | Forks where false paths move closer to goal than the true path. |
| **Near-Miss Exit Lures** | $\ge 1$ lure | Decoy reaching within $\le 2$ cells of the FINISH opening. |
| **Branches Near End** | $0$ branches | Zero distracting/useless branches in the final $15\%$ of the path (the scorer checks the full 15%, not just the last few steps). |
| **Early Decision** | first fork within the first $15\%$ | No long choice-free run from START. |
| **Min Decoy Turns** | $\ge 2$ turns | Every decoy bends at least twice, so its dead end can't be seen from the fork. Depth counts steps; turns count how hard a decoy is to rule out by eye. |
| **4-Way Forks** | $\ge 1$ preferred | Scored bonus, not a hard target: about half of all sheets get one. |
| **1-Cell Dead Ends** | as few as possible | Scored penalty for 1-cell notches anywhere in the maze, including inside decoys. |
| **Resolution** | $1800 \times 2400\text{ px}$ | 3:4 portrait aspect ratio (standard 300 DPI for Letter/A4 printing). |
| **Print-Safe Margin** | $\ge 0.2\text{ in}$ | Arrows, labels and title stay $\ge 0.2$ in (60 px at 300 DPI) from the page edge, where home printers clip. Long labels shrink to fit. |
| **Cell Shape** | within $10\%$ of square | Grids that don't match the page (e.g. $8 \times 8$ on 3:4) are centred instead of stretched. |
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

# Variety: classic algorithm, openings on random opposite walls, 3 extra loops
python generate_maze_script.py --style prim --layout random --loops 3 --outdir .

# Puzzle book: 20 sheets on US Letter, numbered titles, one print-ready PDF
python generate_maze_script.py -n 20 --page letter --title "Maze {n}" --pdf --outdir ./book

# Themed sheet: custom labels and colours, square cells, landscape A4
python generate_maze_script.py --page a4 --landscape --square-cells \
    --start-label "Bunny" --finish-label "Carrot" --wall-color "#1e3a8a" --solution-color "#e11d48"
```

Run `python generate_maze_script.py --help` for the full list. Appearance flags:
`--page {sheet,letter,a4,square}`, `--size WxH`, `--landscape`, `--dpi`,
`--wall-thickness`, `--wall-color`, `--solution-color`, `--background`,
`--start-label`, `--finish-label`, `--no-labels`, `--title` (`{n}` = sheet number)
and `--square-cells`. All sizes scale from the 1800 x 2400 design. Cells are kept within
10% of square (`--square-cells` makes them exact), and the top and bottom margins shrink
from 360 to 300 px when neither opening is on those walls, so the grid gets the height.
Arrows, labels and the title keep a 0.2 in print-safe margin; labels shrink to fit
rather than cross it. The default `sheet` page is still 1800 x 2400 px at 300 DPI.

Labels use a bold TrueType font found on Windows (Arial), macOS (Arial) or Linux
(DejaVu / Liberation / FreeSans), falling back to Pillow's scalable default font.

`--pdf` combines a run into `<name>_book.pdf`: all puzzles first, then all answer
keys. Pages are appended one at a time, so memory stays flat for large batches.

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
satisfied both at once (1 of 400 in the current version). Because *Zero Short Dead Ends* is the project's first
design rule, `score_seed` applies the fork-band bonus only when
`total_cells >= 100`; smaller sheets (the Junior $8 \times 8$ preset) keep deep
decoys and settle for ~4 forks. Grids at or above $10 \times 10$ hit both targets.

Branch carving is budgeted for the same reason: an unbudgeted DFS lets the first
decoy flood every free cell, which caps the solution at 2-4 forks. Each branch is
now limited to roughly `free_cells / (target + 1)` until enough distinct junctions
exist, after which leftover cells are absorbed back into existing decoys.


### Seed Selection

Without `--seed`, the generator samples up to `--max-search` candidate seeds at random
from a 10,000,000-wide space (default 800 below 200 cells, 350 below 900, else 120),
scores them in fixed rounds of 48, and picks at random among the `--top-k`
(default 3) highest scorers. The search **stops early** after the first round in
which `max(2 x top-k, 4)` candidates meet every Section 4 target; that usually
takes 100-350 candidates instead of 800. The round size never depends on the worker
count, so a `--pool-seed` replay is identical on any machine. `--exhaustive` scores
the whole pool, and `--deterministic` always does (same maze for a given size, every run).
Candidates that meet **every** Section 4 target always outrank those that don't; the
weighted score only orders candidates within each group, and the top-k pick never
reaches past the spec-meeting ones when any exist. (Ranking by score alone used to pick
a maze that missed a target in 9 of 15 default runs, even though spec-meeting
candidates had been found every time.) A single worker pool is shared by every sheet in a `--count` batch. Two runs at the same dimensions therefore
produce different sheets of comparable quality. Every run prints the seed it used
plus a ready-to-paste `--seed` command, so any sheet can be reproduced exactly.

### Python API Integration

```python
from generate_maze_script import HighJunctionSingleSolutionMaze

# 1. Initialize maze (algorithm/layout/loops are optional; defaults shown)
maze = HighJunctionSingleSolutionMaze(rows=12, cols=10, seed=232,
                                      algorithm="deceptive", layout="corners", loops=0)

# 2. Solve and analyze
solution, junctions = maze.solve()
print(f"Solution steps: {len(solution)}, Decision forks: {len(junctions)}")

# 3. Render printable sheet and solution
maze.render("output_maze.png", draw_solution=False, wall_thickness=14)
maze.render("output_solution.png", draw_solution=True, wall_thickness=14)

# Optional appearance keywords: image_size, wall_color, solution_color, background,
# start_label, finish_label, title, square_cells, dpi, quiet
```

---

## 6. Guidelines for Future AI Agents

When interacting with this codebase or extending its features:
1. **Preserve Graph Integrity:** Never manually alter wall arrays without re-running BFS solvability and cycle checks.
2. **Maintain Clean Aesthetics:** Do not inject decorative cartoon illustrations, clip art, or grayscale shading into the maze canvas unless explicitly requested by the user.
3. **Respect Print Ratios:** Standard output canvases should maintain a 3:4 aspect ratio (e.g. $1800 \times 2400\text{ px}$) to match standard A4/US Letter coloring books.
4. **Always Render Both Files:** Whenever a new maze is generated, produce both the clean printable maze (`.png`) and the corresponding verified solution key (`_solution.png`).
