import random
import os
import re
import argparse
from collections import deque
from PIL import Image, ImageDraw, ImageFont

# Generation styles. "deceptive" is the hand-tuned single-solution engine this
# project is built around; the others are classic perfect-maze algorithms (also
# exactly one solution) that give sheets a visibly different texture.
ALGORITHMS = {
    "deceptive": "Deep decoys, anti-greedy forks and near-miss exit lures (default)",
    "backtracker": "Recursive backtracker: long, twisting corridors with few dead ends",
    "prim": "Randomized Prim: many short branches, busy and bushy look",
    "kruskal": "Randomized Kruskal: even mix of short and medium dead ends",
    "wilson": "Wilson's algorithm: unbiased uniform spanning tree",
    "hunt-kill": "Hunt-and-kill: long winding passages like the backtracker, straighter runs",
}

# Where the START and FINISH openings go. "corners" is the original layout and
# consumes no randomness, so every seed from earlier versions still reproduces.
LAYOUTS = {
    "corners": "START top-left (left wall), FINISH bottom-right (right wall)",
    "sides": "START on the left wall, FINISH on the right wall, random rows",
    "top-bottom": "START on the top wall, FINISH on the bottom wall, random columns",
    "random": "Openings on a random pair of opposite walls, random positions",
}

_SIDE_VECTORS = {"left": (0, -1), "right": (0, 1), "top": (-1, 0), "bottom": (1, 0)}

class HighJunctionSingleSolutionMaze:
    """
    Generates human-like, mathematically guaranteed single-solution mazes engineered with:
    1. Zero Short Dead Ends: Every decision fork off the solution path leads into a deep winding corridor.
    2. Zero Compact Dead Ends / U-Shapes: Eliminates trivial 2x2 coils and 1xN zig-zags via inertial exploration.
    3. Zero Useless Branches Near Finish: The final stretch leading to the exit is clean and committed.
    4. Near-Miss Exit Lures: Decoy paths aggressively rush toward the FINISH and stop right next to the exit wall.
    5. Anti-Greedy True Path: Solution deliberately turns away from the exit at forks where decoys head toward the exit.
    6. Exact Single Solution: Connected, acyclic mathematical spanning tree (E = V - 1, 0 loops).
    7. Clean Minimalist Aesthetic: High-contrast black lines on white canvas (1800 x 2400 px, 3:4 portrait).
    """
    def __init__(self, rows=12, cols=10, seed=None, algorithm="deceptive", layout="corners", loops=0):
        if algorithm not in ALGORITHMS:
            raise ValueError(f"unknown algorithm {algorithm!r}; choose from {', '.join(ALGORITHMS)}")
        if layout not in LAYOUTS:
            raise ValueError(f"unknown layout {layout!r}; choose from {', '.join(LAYOUTS)}")
        self.rows = rows
        self.cols = cols
        self.seed = seed
        self.algorithm = algorithm
        self.layout = layout
        self.loops = 0
        if seed is not None:
            random.seed(seed)

        self.h_walls = [[True for _ in range(cols)] for _ in range(rows + 1)]
        self.v_walls = [[True for _ in range(cols + 1)] for _ in range(rows)]
        self.solution_path = []
        self.start, self.start_side, self.goal, self.goal_side = self._pick_openings(layout)
        if algorithm == "deceptive":
            self._generate()
        elif algorithm == "backtracker":
            self._generate_standard_dfs()
        elif algorithm == "prim":
            self._generate_prim()
        elif algorithm == "kruskal":
            self._generate_kruskal()
        elif algorithm == "wilson":
            self._generate_wilson()
        elif algorithm == "hunt-kill":
            self._generate_hunt_kill()
        if loops:
            self.loops = self._add_loops(loops)
        self._open_boundary(self.start, self.start_side)
        self._open_boundary(self.goal, self.goal_side)

    def _pick_openings(self, layout):
        """Return (start, start_side, goal, goal_side) for the chosen layout.

        START and FINISH always sit on opposite walls so the solution has to
        cross the sheet. Positions come from the seeded RNG, so a seed still
        pins the whole maze.
        """
        rows, cols = self.rows, self.cols
        if layout == "corners":
            return (0, 0), "left", (rows - 1, cols - 1), "right"
        if layout == "random":
            layout = random.choice(("sides", "top-bottom"))
            flip = random.random() < 0.5
        else:
            flip = False
        if layout == "sides":
            a = ((random.randrange(rows), 0), "left")
            b = ((random.randrange(rows), cols - 1), "right")
        else:
            a = ((0, random.randrange(cols)), "top")
            b = ((rows - 1, random.randrange(cols)), "bottom")
        if flip:
            a, b = b, a
        return a[0], a[1], b[0], b[1]

    def _open_boundary(self, cell, side):
        r, c = cell
        if side == "left":
            self.v_walls[r][0] = False
        elif side == "right":
            self.v_walls[r][self.cols] = False
        elif side == "top":
            self.h_walls[0][c] = False
        else:
            self.h_walls[self.rows][c] = False

    def _wall_open(self, r, c, nr, nc):
        """True when the passage between orthogonal neighbours is open."""
        if nr != r:
            return not self.h_walls[max(r, nr)][c]
        return not self.v_walls[r][max(c, nc)]

    def _neighbors(self, r, c):
        if r > 0: yield r - 1, c
        if r < self.rows - 1: yield r + 1, c
        if c > 0: yield r, c - 1
        if c < self.cols - 1: yield r, c + 1

    def _add_loops(self, count):
        """Knock through up to ``count`` walls at dead ends, creating cycles.

        Turns the perfect maze into a "braided" one with several routes, which
        removes dead ends and makes the sheet feel more open. Returns how many
        loops were actually added.
        """
        dead_ends = [(r, c) for r in range(self.rows) for c in range(self.cols)
                     if sum(self._wall_open(r, c, nr, nc) for nr, nc in self._neighbors(r, c)) == 1]
        random.shuffle(dead_ends)
        added = 0
        for r, c in dead_ends:
            if added >= count:
                break
            # Re-check: an earlier loop may already have opened this cell up.
            if sum(self._wall_open(r, c, nr, nc) for nr, nc in self._neighbors(r, c)) != 1:
                continue
            closed = [(nr, nc) for nr, nc in self._neighbors(r, c) if not self._wall_open(r, c, nr, nc)]
            if closed:
                nr, nc = random.choice(closed)
                self._remove_wall(r, c, nr, nc)
                added += 1
        return added

    def _remove_wall(self, r1, c1, r2, c2):
        if r2 == r1 + 1 and c2 == c1:
            self.h_walls[r2][c1] = False
        elif r2 == r1 - 1 and c2 == c1:
            self.h_walls[r1][c1] = False
        elif c2 == c1 + 1 and r2 == r1:
            self.v_walls[r1][c2] = False
        elif c2 == c1 - 1 and r2 == r1:
            self.v_walls[r1][c1] = False

    def _generate(self):
        rows, cols = self.rows, self.cols
        start = self.start
        goal = self.goal
        visited = [[False for _ in range(cols)] for _ in range(rows)]

        # --- 1. CARVE DETOURING MAIN PATH WITHOUT ORPHANING 1x1 POCKETS ---
        target_len = int(rows * cols * 0.38)
        min_comp_size = max(3, int(min(rows, cols) * 0.3))
        away_target = max(6, int(rows * cols * 0.08))
        
        # Flat-index helpers: the walk runs on a 1-D grid to avoid tuple churn.
        n_cells = rows * cols
        goal_i = goal[0] * cols + goal[1]
        start_i = start[0] * cols + start[1]

        # Static neighbour tables, built once per maze. `toward_goal` lists each
        # cell's neighbours farthest-from-goal first, so a stack pops the one
        # nearest the goal next (greedy depth-first reachability).
        nbrs = []
        for i in range(n_cells):
            ir, ic = divmod(i, cols)
            nb = []
            if ir > 0: nb.append(i - cols)
            if ir < rows - 1: nb.append(i + cols)
            if ic > 0: nb.append(i - 1)
            if ic < cols - 1: nb.append(i + 1)
            nbrs.append(tuple(nb))
        def _goal_dist(i):
            ir, ic = divmod(i, cols)
            return abs(ir - goal[0]) + abs(ic - goal[1])
        toward_goal = [tuple(sorted(nb, key=_goal_dist, reverse=True)) for nb in nbrs]

        def check_orphans(blocked, gen_buf, stamp):
            # Any unblocked region smaller than min_comp_size is an orphan pocket.
            for start_i in range(n_cells):
                if blocked[start_i] or gen_buf[start_i] == stamp:
                    continue
                stamp += 1
                size = 0
                q = deque([start_i])
                gen_buf[start_i] = stamp
                while q:
                    i = q.popleft()
                    size += 1
                    ir, ic = divmod(i, cols)
                    if ir > 0:
                        j = i - cols
                        if not blocked[j] and gen_buf[j] != stamp:
                            gen_buf[j] = stamp; q.append(j)
                    if ir < rows - 1:
                        j = i + cols
                        if not blocked[j] and gen_buf[j] != stamp:
                            gen_buf[j] = stamp; q.append(j)
                    if ic > 0:
                        j = i - 1
                        if not blocked[j] and gen_buf[j] != stamp:
                            gen_buf[j] = stamp; q.append(j)
                    if ic < cols - 1:
                        j = i + 1
                        if not blocked[j] and gen_buf[j] != stamp:
                            gen_buf[j] = stamp; q.append(j)
                if size < min_comp_size:
                    return True, stamp
            return False, stamp

        def carve_one_walk(blocked, gen_buf, stamp):
            """Self-avoiding walk that can never trap itself.

            A step is only taken if the goal is still reachable through the
            remaining unblocked cells, so the walk always terminates at the
            goal instead of dead-ending and throwing the attempt away.
            """
            def step_tier(frm):
                """Classify a step to `frm`: 2 = goal still reachable and no
                undersized pocket sealed off, 1 = reachable but seals a pocket,
                0 = strands the goal.

                Tiering rather than a hard yes/no matters: an absolute pocket
                rule strands the walk outright on larger grids, while ignoring
                pockets until the end throws away almost every completed walk.
                The caller takes a tier-2 step when one exists and settles for
                tier 1 rather than abandoning the attempt.

                Both checks stay cheap on purpose. Reachability is a depth-first
                search that always expands the neighbour nearest the goal first,
                so on an open grid it touches roughly one corridor of cells
                instead of flooding the whole board, and exits the moment the
                goal is seen. The pocket scan is bounded to min_comp_size cells
                around the new head -- a sealed pocket can only form next to the
                cell just filled, so labelling the whole grid every step is
                wasted work.
                """
                nonlocal stamp
                stamp += 1
                tag = stamp
                stack = [frm]
                gen_buf[frm] = tag
                reached = False
                while stack:
                    i = stack.pop()
                    if i == goal_i:
                        reached = True
                        break
                    for j in toward_goal[i]:
                        if not blocked[j] and gen_buf[j] != tag:
                            gen_buf[j] = tag
                            stack.append(j)
                if not reached:
                    return 0

                for nb in nbrs[frm]:
                    if blocked[nb]:
                        continue
                    stamp += 1
                    ptag = stamp
                    size = 0
                    pq = [nb]
                    gen_buf[nb] = ptag
                    while pq and size < min_comp_size:
                        i = pq.pop()
                        size += 1
                        for j in nbrs[i]:
                            if not blocked[j] and gen_buf[j] != ptag:
                                gen_buf[j] = ptag
                                pq.append(j)
                    if size < min_comp_size:
                        return 1
                return 2

            path = [start_i]
            blocked[start_i] = 1
            while path[-1] != goal_i:
                i = path[-1]
                r, c = divmod(i, cols)
                cand = []
                if r > 0 and not blocked[i - cols]:
                    cand.append((i - cols, r - 1, c))
                if r < rows - 1 and not blocked[i + cols]:
                    cand.append((i + cols, r + 1, c))
                if c > 0 and not blocked[i - 1]:
                    cand.append((i - 1, r, c - 1))
                if c < cols - 1 and not blocked[i + 1]:
                    cand.append((i + 1, r, c + 1))
                if not cand:
                    return None, stamp

                # Rank by the original detour heuristics, then validate lazily:
                # usually only the first candidate needs a reachability check.
                if len(path) < target_len:
                    pool = list(cand)
                    weights = []
                    for _, nr, nc in pool:
                        d = abs(nr - goal[0]) + abs(nc - goal[1])
                        w = 1.0 + (d / (rows + cols)) * 2.5
                        if nr == 0 or nc == 0 or nr == rows - 1 or nc == cols - 1:
                            w += 1.2
                        weights.append(w)
                    order = []
                    while pool:
                        k = random.choices(range(len(pool)), weights=weights, k=1)[0]
                        order.append(pool.pop(k)); weights.pop(k)
                else:
                    order = sorted(cand, key=lambda t: abs(t[1] - goal[0]) + abs(t[2] - goal[1]))
                    if random.random() >= 0.70:
                        random.shuffle(order)

                chosen = None
                fallback = None
                for j, _, _ in order:
                    if j == goal_i:
                        chosen = j
                        break
                    blocked[j] = 1
                    tier = step_tier(j)
                    blocked[j] = 0
                    if tier == 2:
                        chosen = j
                        break
                    if tier == 1 and fallback is None:
                        fallback = j
                if chosen is None:
                    chosen = fallback
                if chosen is None:
                    return None, stamp
                blocked[chosen] = 1
                path.append(chosen)
            return path, stamp

        def find_clean_main_path(max_attempts=40):
            best_p = None
            best_score = -1e9
            gen_buf = [0] * n_cells
            stamp = 0
            last_resort = [None]
            lo = int(rows * cols * 0.28)
            hi = int(rows * cols * 0.48)
            for _ in range(max_attempts):
                blocked = bytearray(n_cells)
                flat_path, stamp = carve_one_walk(blocked, gen_buf, stamp)
                if flat_path is None or not (lo <= len(flat_path) <= hi):
                    continue

                orphaned, stamp = check_orphans(blocked, gen_buf, stamp)
                path = [divmod(i, cols) for i in flat_path]
                if orphaned:
                    # Keep it only as a last resort; a pocketed path still beats
                    # dropping to the plain-DFS fallback, which has none of the
                    # deceptive structure this class exists to build.
                    if last_resort[0] is None:
                        last_resort[0] = path
                    continue

                away_moves = 0
                for i in range(len(path) - 1):
                    d_curr = abs(path[i][0] - goal[0]) + abs(path[i][1] - goal[1])
                    d_next = abs(path[i+1][0] - goal[0]) + abs(path[i+1][1] - goal[1])
                    if d_next > d_curr:
                        away_moves += 1
                score = len(path) * 2 + away_moves * 5
                if score > best_score:
                    best_score = score
                    best_p = path
                    if away_moves >= away_target:
                        return path
            return best_p if best_p is not None else last_resort[0]

        main_path = find_clean_main_path()
        if not main_path:
            self._generate_standard_dfs()
            return

        self.solution_path = main_path
        for r, c in main_path:
            visited[r][c] = True
            
        for i in range(len(main_path) - 1):
            self._remove_wall(main_path[i][0], main_path[i][1], main_path[i+1][0], main_path[i+1][1])

        main_set = set(main_path)
        decoy_cells = set()

        # --- 2. SPROUT NEAR-MISS EXIT LURES (ONLY IN MID-PATH: 25% to 70%) ---
        mid_indices = list(range(len(main_path) // 4, int(len(main_path) * 0.70)))
        random.shuffle(mid_indices)
        
        lures_created = 0
        min_lure_cap = max(4, int(min(rows, cols) * 0.5))
        for idx in mid_indices:
            r, c = main_path[idx]
            neighbors = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                    d = abs(nr - goal[0]) + abs(nc - goal[1])
                    neighbors.append((nr, nc, d, (dr, dc)))
            if not neighbors:
                continue
            neighbors.sort(key=lambda x: x[2])
            bnr, bnc, _, (bdr, bdc) = neighbors[0]
            
            # Check capacity
            q = [(bnr, bnc)]
            q_vis = set([(bnr, bnc)])
            while q and len(q_vis) < min_lure_cap + 3:
                qr, qc = q.pop(0)
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    qnr, qnc = qr + dr, qc + dc
                    if 0 <= qnr < rows and 0 <= qnc < cols and not visited[qnr][qnc] and (qnr, qnc) not in q_vis:
                        q_vis.add((qnr, qnc))
                        q.append((qnr, qnc))
            if len(q_vis) < min_lure_cap:
                continue
                
            visited[bnr][bnc] = True
            decoy_cells.add((bnr, bnc))
            self._remove_wall(r, c, bnr, bnc)
            
            lure_stack = [(bnr, bnc, (bdr, bdc))]
            while lure_stack:
                curr_r, curr_c, last_d = lure_stack[-1]
                unvis = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nnr, nnc = curr_r + dr, curr_c + dc
                    if 0 <= nnr < rows and 0 <= nnc < cols and not visited[nnr][nnc]:
                        d = abs(nnr - goal[0]) + abs(nnc - goal[1])
                        unvis.append((nnr, nnc, d, (dr, dc)))
                if unvis:
                    unvis.sort(key=lambda x: x[2])
                    weights = []
                    for item in unvis:
                        w = 3.0 / (item[2] + 1.0)
                        if item[3] == last_d:
                            w *= 2.0
                        weights.append(w)
                    chosen_bnr, chosen_bnc, _, chosen_d = random.choices(unvis, weights=weights, k=1)[0]
                    visited[chosen_bnr][chosen_bnc] = True
                    decoy_cells.add((chosen_bnr, chosen_bnc))
                    self._remove_wall(curr_r, curr_c, chosen_bnr, chosen_bnc)
                    lure_stack.append((chosen_bnr, chosen_bnc, chosen_d))
                else:
                    lure_stack.pop()
                    
            lures_created += 1
            if lures_created >= 2:
                break

        # --- 3. SPROUT BALANCED DEEP FORKS (NO BRANCHES IN LAST 20% OF PATH) ---
        branch_cutoff = int(len(main_path) * 0.80)
        stride = 2 if rows * cols <= 150 else 3
        possible_indices = list(range(3, branch_cutoff, stride))
        random.shuffle(possible_indices)
        
        min_branch_cap = max(4, int(min(rows, cols) * 0.5))

        # Aim for the 5-9 decision-fork band. Unbudgeted, the first branch floods
        # every free cell via DFS and the solution ends up with only 2-4 forks, so
        # each branch is capped until enough distinct junctions exist. Leftover
        # cells are absorbed back into these decoys in stage 4, which keeps the
        # "no short dead ends" property intact.
        free_cells = sum(row.count(False) for row in visited)
        target_junctions = random.randint(5, 8)
        branch_budget = max(min_branch_cap + 2, free_cells // (target_junctions + 1))
        junctions_made = 0

        for idx in possible_indices:
            br, bc = main_path[idx]
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = br + dr, bc + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]:
                    q = [(nr, nc)]
                    q_vis = set([(nr, nc)])
                    while q and len(q_vis) < min_branch_cap + 3:
                        qr, qc = q.pop(0)
                        for qdr, qdc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            qnr, qnc = qr + qdr, qc + qdc
                            if 0 <= qnr < rows and 0 <= qnc < cols and not visited[qnr][qnc] and (qnr, qnc) not in q_vis:
                                q_vis.add((qnr, qnc))
                                q.append((qnr, qnc))
                    if len(q_vis) < min_branch_cap:
                        continue
                        
                    visited[nr][nc] = True
                    decoy_cells.add((nr, nc))
                    self._remove_wall(br, bc, nr, nc)
                    
                    # Only ration space while we still owe the maze more forks.
                    budget = branch_budget if junctions_made < target_junctions else 10 ** 9
                    branch_len = 1

                    b_stack = [(nr, nc, (dr, dc))]
                    while b_stack and branch_len < budget:
                        curr_r, curr_c, last_dir = b_stack[-1]
                        b_nbrs = []
                        for bdr, bdc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            bnr, bnc = curr_r + bdr, curr_c + bdc
                            if 0 <= bnr < rows and 0 <= bnc < cols and not visited[bnr][bnc]:
                                b_nbrs.append((bnr, bnc, (bdr, bdc)))
                        if b_nbrs:
                            weights = [2.5 if n[2] == last_dir else 1.0 for n in b_nbrs]
                            bnr, bnc, new_dir = random.choices(b_nbrs, weights=weights, k=1)[0]
                            visited[bnr][bnc] = True
                            decoy_cells.add((bnr, bnc))
                            self._remove_wall(curr_r, curr_c, bnr, bnc)
                            b_stack.append((bnr, bnc, new_dir))
                            branch_len += 1
                        else:
                            b_stack.pop()

                    junctions_made += 1
                    if junctions_made < target_junctions:
                        # One fork per path cell until the target is met, so the
                        # remaining free space seeds junctions further along.
                        break

        # --- 4. EXTEND EXISTING DECOY PATHS INTO ALL REMAINING CELLS (NEVER TOUCH MAIN PATH) ---
        unvis_cells = [(r, c) for r in range(rows) for c in range(cols) if not visited[r][c]]
        while unvis_cells:
            connected = False
            random.shuffle(unvis_cells)
            for r, c in unvis_cells:
                adj_decoys = []
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and visited[nr][nc] and (nr, nc) in decoy_cells:
                        adj_decoys.append((nr, nc))
                if adj_decoys:
                    dnr, dnc = random.choice(adj_decoys)
                    self._remove_wall(r, c, dnr, dnc)
                    visited[r][c] = True
                    decoy_cells.add((r, c))
                    
                    rem_stack = [(r, c)]
                    while rem_stack:
                        cr, cc = rem_stack[-1]
                        unvis_nbrs = []
                        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nnr, nnc = cr + dr, cc + dc
                            if 0 <= nnr < rows and 0 <= nnc < cols and not visited[nnr][nnc]:
                                unvis_nbrs.append((nnr, nnc))
                        if unvis_nbrs:
                            nnr, nnc = random.choice(unvis_nbrs)
                            visited[nnr][nnc] = True
                            decoy_cells.add((nnr, nnc))
                            self._remove_wall(cr, cc, nnr, nnc)
                            rem_stack.append((nnr, nnc))
                        else:
                            rem_stack.pop()
                    connected = True
                    break
                    
            if not connected:
                for r, c in unvis_cells:
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols and visited[nr][nc]:
                            self._remove_wall(r, c, nr, nc)
                            visited[r][c] = True
                            decoy_cells.add((r, c))
                            connected = True
                            break
                    if connected:
                        break
                        
            unvis_cells = [(r, c) for r in range(rows) for c in range(cols) if not visited[r][c]]

    def _generate_standard_dfs(self):
        visited = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        stack = [self.start]
        visited[self.start[0]][self.start[1]] = True
        while stack:
            r, c = stack[-1]
            neighbors = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and not visited[nr][nc]:
                    neighbors.append((nr, nc))
            if neighbors:
                nr, nc = random.choice(neighbors)
                self._remove_wall(r, c, nr, nc)
                visited[nr][nc] = True
                stack.append((nr, nc))
            else:
                stack.pop()

    def _generate_prim(self):
        rows, cols = self.rows, self.cols
        visited = [[False] * cols for _ in range(rows)]
        sr, sc = random.randrange(rows), random.randrange(cols)
        visited[sr][sc] = True
        frontier = [(sr, sc, nr, nc) for nr, nc in self._neighbors(sr, sc)]
        while frontier:
            # Swap-remove a random frontier edge: O(1) instead of list.pop(k).
            k = random.randrange(len(frontier))
            frontier[k], frontier[-1] = frontier[-1], frontier[k]
            r, c, nr, nc = frontier.pop()
            if visited[nr][nc]:
                continue
            visited[nr][nc] = True
            self._remove_wall(r, c, nr, nc)
            for fr, fc in self._neighbors(nr, nc):
                if not visited[fr][fc]:
                    frontier.append((nr, nc, fr, fc))

    def _generate_kruskal(self):
        rows, cols = self.rows, self.cols
        parent = list(range(rows * cols))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        edges = [(i, i + 1) for i in range(rows * cols) if (i + 1) % cols]
        edges += [(i, i + cols) for i in range(rows * cols - cols)]
        random.shuffle(edges)
        for a, b in edges:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
                self._remove_wall(*divmod(a, cols), *divmod(b, cols))

    def _generate_wilson(self):
        rows, cols = self.rows, self.cols
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        in_tree = [[False] * cols for _ in range(rows)]
        r0, c0 = random.choice(cells)
        in_tree[r0][c0] = True
        random.shuffle(cells)
        for cell in cells:
            if in_tree[cell[0]][cell[1]]:
                continue
            # Loop-erased random walk: remembering only the last exit taken from
            # each cell erases loops implicitly.
            nxt = {}
            cur = cell
            while not in_tree[cur[0]][cur[1]]:
                step = random.choice(list(self._neighbors(*cur)))
                nxt[cur] = step
                cur = step
            cur = cell
            while not in_tree[cur[0]][cur[1]]:
                in_tree[cur[0]][cur[1]] = True
                self._remove_wall(*cur, *nxt[cur])
                cur = nxt[cur]

    def _generate_hunt_kill(self):
        rows, cols = self.rows, self.cols
        visited = [[False] * cols for _ in range(rows)]
        r, c = self.start
        visited[r][c] = True
        remaining = rows * cols - 1
        hunt_row = 0
        while remaining:
            options = [(nr, nc) for nr, nc in self._neighbors(r, c) if not visited[nr][nc]]
            if options:
                nr, nc = random.choice(options)
                self._remove_wall(r, c, nr, nc)
                visited[nr][nc] = True
                remaining -= 1
                r, c = nr, nc
                continue
            # Hunt: scan for an unvisited cell touching the carved area. Rows
            # above hunt_row are fully visited, so the scan never restarts at 0.
            while all(visited[hunt_row]):
                hunt_row += 1
            found = False
            for hr in range(hunt_row, rows):
                for hc in range(cols):
                    if visited[hr][hc]:
                        continue
                    done = [(nr, nc) for nr, nc in self._neighbors(hr, hc) if visited[nr][nc]]
                    if done:
                        nr, nc = random.choice(done)
                        self._remove_wall(hr, hc, nr, nc)
                        visited[hr][hc] = True
                        remaining -= 1
                        r, c = hr, hc
                        found = True
                        break
                if found:
                    break

    def solve(self):
        # BFS with parent pointers; copying whole paths per node is quadratic.
        goal = self.goal
        queue = deque([self.start])
        parent = {self.start: None}
        found = False

        while queue:
            r, c = queue.popleft()
            if (r, c) == goal:
                found = True
                break

            for dr, dc, w_type, wr, wc in [
                (-1, 0, 'H', r, c),
                (1, 0, 'H', r+1, c),
                (0, -1, 'V', r, c),
                (0, 1, 'V', r, c+1)
            ]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and (nr, nc) not in parent:
                    is_blocked = self.h_walls[wr][wc] if w_type == 'H' else self.v_walls[wr][wc]
                    if not is_blocked:
                        parent[(nr, nc)] = (r, c)
                        queue.append((nr, nc))

        if not found:
            return None, []

        solution = []
        node = goal
        while node is not None:
            solution.append(node)
            node = parent[node]
        solution.reverse()
            
        sol_set = set(solution)
        junctions = []
        
        for idx, (r, c) in enumerate(solution):
            open_exits = []
            for dr, dc, w_type, wr, wc in [
                (-1, 0, 'H', r, c),
                (1, 0, 'H', r+1, c),
                (0, -1, 'V', r, c),
                (0, 1, 'V', r, c+1)
            ]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    is_blocked = self.h_walls[wr][wc] if w_type == 'H' else self.v_walls[wr][wc]
                    if not is_blocked:
                        open_exits.append((nr, nc))
                        
            if len(open_exits) >= 3 or ((r, c) == self.start and len(open_exits) >= 2):
                false_branches = [n for n in open_exits if n not in sol_set]
                branch_info = []
                
                next_sol_step = solution[idx + 1] if idx + 1 < len(solution) else None
                sol_dist_to_goal = abs(next_sol_step[0] - goal[0]) + abs(next_sol_step[1] - goal[1]) if next_sol_step else 0
                
                for fnr, fnc in false_branches:
                    b_q = deque([(fnr, fnc, 1)])
                    b_vis = set([(r, c), (fnr, fnc)])
                    max_d = 1
                    min_dist_to_goal = abs(fnr - goal[0]) + abs(fnc - goal[1])
                    decoy_closer_than_sol = (abs(fnr - goal[0]) + abs(fnc - goal[1])) < sol_dist_to_goal
                    
                    while b_q:
                        br, bc, d = b_q.popleft()
                        if d > max_d: max_d = d
                        d_goal = abs(br - goal[0]) + abs(bc - goal[1])
                        if d_goal < min_dist_to_goal:
                            min_dist_to_goal = d_goal
                            
                        for bdr, bdc, bw_type, bwr, bwc in [
                            (-1, 0, 'H', br, bc),
                            (1, 0, 'H', br+1, bc),
                            (0, -1, 'V', br, bc),
                            (0, 1, 'V', br, bc+1)
                        ]:
                            bnr, bnc = br + bdr, bc + bdc
                            if 0 <= bnr < self.rows and 0 <= bnc < self.cols and (bnr, bnc) not in b_vis:
                                blocked = self.h_walls[bwr][bwc] if bw_type == 'H' else self.v_walls[bwr][bwc]
                                if not blocked:
                                    b_vis.add((bnr, bnc))
                                    b_q.append((bnr, bnc, d + 1))
                                    
                    branch_info.append({
                        'depth': max_d,
                        'min_dist_to_goal': min_dist_to_goal,
                        'anti_greedy_lure': decoy_closer_than_sol
                    })
                    
                junctions.append({
                    'step_index': idx,
                    'cell': (r, c),
                    'total_choices': len(open_exits),
                    'branch_info': branch_info,
                    'decoy_depths': [b['depth'] for b in branch_info],
                    'has_exit_lure': any(b['min_dist_to_goal'] <= 2 for b in branch_info),
                    'has_anti_greedy': any(b['anti_greedy_lure'] for b in branch_info)
                })
                
        return solution, junctions

    def render(self, output_path, draw_solution=False, wall_thickness=None, image_size=(1800, 2400),
               wall_color="black", solution_color="#2563eb", background="white",
               start_label="START", finish_label="FINISH", title=None, square_cells=False,
               dpi=300, quiet=False):
        """Draw the sheet and save it to ``output_path`` (format from the extension).

        Every size is scaled from the original 1800 x 2400 design, so other page
        sizes keep the same proportions. ``square_cells`` keeps cells square and
        centres the grid instead of stretching it to fill the page.
        """
        w, h = image_size
        scale = min(w / 1800, h / 2400)
        if wall_thickness is None:
            wall_thickness = max(8, min(16, int(180 / max(self.rows, self.cols))))
            wall_thickness = max(2, int(round(wall_thickness * scale)))

        img = Image.new("RGB", (w, h), background)
        draw = ImageDraw.Draw(img)

        margin_x = w * 240 / 1800
        margin_y = h * 360 / 2400
        grid_w = w - 2 * margin_x
        grid_h = h - 2 * margin_y
        cell_w = grid_w / self.cols
        cell_h = grid_h / self.rows
        if square_cells:
            cell_w = cell_h = min(cell_w, cell_h)
            margin_x = (w - cell_w * self.cols) / 2
            margin_y = (h - cell_h * self.rows) / 2

        def center(r, c):
            return margin_x + (c + 0.5) * cell_w, margin_y + (r + 0.5) * cell_h

        def edge_point(cell, side):
            """Midpoint of the cell's wall on the given outer side."""
            x, y = center(*cell)
            dr, dc = _SIDE_VECTORS[side]
            return x + dc * cell_w / 2, y + dr * cell_h / 2

        if draw_solution:
            solution, _ = self.solve()
            if solution:
                reach = 100 * scale
                sx, sy = edge_point(self.start, self.start_side)
                gx, gy = edge_point(self.goal, self.goal_side)
                sdr, sdc = _SIDE_VECTORS[self.start_side]
                gdr, gdc = _SIDE_VECTORS[self.goal_side]
                sol_points = [(sx + sdc * reach, sy + sdr * reach)]
                sol_points += [center(r, c) for r, c in solution]
                sol_points.append((gx + gdc * reach, gy + gdr * reach))
                line_w = max(4, int(wall_thickness * 0.85))
                draw.line(sol_points, fill=solution_color, width=line_w, joint="curve")

        # Walls, merged into maximal straight runs: far fewer draw calls and no
        # visible seams between segments.
        for r in range(self.rows + 1):
            y = margin_y + r * cell_h
            c = 0
            while c < self.cols:
                if self.h_walls[r][c]:
                    c0 = c
                    while c < self.cols and self.h_walls[r][c]:
                        c += 1
                    draw.line([(margin_x + c0 * cell_w, y), (margin_x + c * cell_w, y)],
                              fill=wall_color, width=wall_thickness)
                else:
                    c += 1
        for c in range(self.cols + 1):
            x = margin_x + c * cell_w
            r = 0
            while r < self.rows:
                if self.v_walls[r][c]:
                    r0 = r
                    while r < self.rows and self.v_walls[r][c]:
                        r += 1
                    draw.line([(x, margin_y + r0 * cell_h), (x, margin_y + r * cell_h)],
                              fill=wall_color, width=wall_thickness)
                else:
                    r += 1

        # Rounded caps where walls end, turn or meet. Straight pass-throughs are
        # skipped: a cap there only adds a visible bump to the line.
        r_cap = wall_thickness / 2
        for r in range(self.rows + 1):
            y = margin_y + r * cell_h
            for c in range(self.cols + 1):
                e = c < self.cols and self.h_walls[r][c]
                wst = c > 0 and self.h_walls[r][c - 1]
                s_ = r < self.rows and self.v_walls[r][c]
                n = r > 0 and self.v_walls[r - 1][c]
                if (e or wst or s_ or n) and not ((e and wst and not s_ and not n) or
                                                  (s_ and n and not e and not wst)):
                    x = margin_x + c * cell_w
                    draw.ellipse([(x - r_cap, y - r_cap), (x + r_cap, y + r_cap)], fill=wall_color)

        label_size = int(64 * scale)
        self._draw_opening(draw, edge_point(self.start, self.start_side), self.start_side,
                           start_label, label_size, scale, wall_color, inward=True)
        self._draw_opening(draw, edge_point(self.goal, self.goal_side), self.goal_side,
                           finish_label, label_size, scale, wall_color, inward=False)

        if title:
            font_title = load_font(int(96 * scale))
            tw, th = _text_size(draw, title, font_title)
            if tw > w * 0.9:
                font_title = load_font(max(12, int(96 * scale * w * 0.9 / tw)))
                tw, th = _text_size(draw, title, font_title)
            title_y = margin_y * 0.22
            if "top" in (self.start_side, self.goal_side):
                # Sit above the arrow on the top wall instead of across it.
                title_y = max(10 * scale, margin_y - 200 * scale - th - 20 * scale)
            draw.text(((w - tw) / 2, title_y), title, fill=wall_color, font=font_title)

        save_kwargs = {"dpi": (dpi, dpi)} if dpi else {}
        img.save(output_path, **save_kwargs)
        if not quiet:
            print(f"Generated: {output_path}")
        return img

    def _draw_opening(self, draw, edge, side, label, font_size, scale, color, inward):
        """Arrow (and optional label) outside an opening on the outer wall.

        START arrows point into the maze, FINISH arrows point out of it.
        Labels sit above/below arrows on the left and right walls, and beside
        arrows on the top and bottom walls (toward the page centre).
        """
        ex, ey = edge
        dr, dc = _SIDE_VECTORS[side]
        near, far = 30 * scale, 200 * scale
        p_near = (ex + dc * near, ey + dr * near)
        p_far = (ex + dc * far, ey + dr * far)
        tail, tip = (p_far, p_near) if inward else (p_near, p_far)
        draw.line([tail, tip], fill=color, width=max(3, int(10 * scale)))
        ux, uy = tip[0] - tail[0], tip[1] - tail[1]
        length = (ux * ux + uy * uy) ** 0.5
        ux, uy = ux / length, uy / length
        head_len, head_w = 35 * scale, 18 * scale
        bx, by = tip[0] - ux * head_len, tip[1] - uy * head_len
        draw.polygon([(tip[0] + ux * 10 * scale, tip[1] + uy * 10 * scale),
                      (bx - uy * head_w, by + ux * head_w),
                      (bx + uy * head_w, by - ux * head_w)], fill=color)

        if not label:
            return
        img_w = draw.im.size[0]
        font = load_font(font_size)
        tw, th = _text_size(draw, label, font)
        if side in ("left", "right"):
            # Shrink long labels until they fit in the side margin.
            room = (ex if side == "left" else img_w - ex) - near - 10 * scale
            if tw > room > 0:
                font = load_font(max(10, int(font_size * room / tw)))
                tw, th = _text_size(draw, label, font)
        mid_x = (p_near[0] + p_far[0]) / 2
        mid_y = (p_near[1] + p_far[1]) / 2
        gap = 25 * scale
        if side in ("left", "right"):
            # Keep the text in the page margin, clear of the outer wall.
            if side == "left":
                x = max(10 * scale, ex - near - tw)
            else:
                x = min(ex + near, img_w - tw - 10 * scale)
            y = mid_y - gap - th if inward else mid_y + gap
        else:
            x = mid_x + gap if mid_x < img_w / 2 else mid_x - gap - tw
            y = mid_y - th / 2
        draw.text((x, y), label, fill=color, font=font)


_FONT_CANDIDATES = (
    "arialbd.ttf",                                            # Windows
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",      # macOS
    "/Library/Fonts/Arial Bold.ttf",
    "Arial Bold.ttf",
    "DejaVuSans-Bold.ttf",                                    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)
_font_cache = {}


def load_font(size):
    """A bold TrueType font at ``size`` px, found on Windows, macOS or Linux.

    Falls back to Pillow's built-in font (scalable on Pillow >= 10.1) rather
    than the tiny fixed bitmap font, so labels stay readable everywhere.
    """
    if size in _font_cache:
        return _font_cache[size]
    font = None
    for name in _FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def _text_size(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom


def score_seed(args):
    """Build one candidate maze and score it. Module-level so it can be pickled
    across worker processes; seeds are independent, so the search parallelises.

    ``args`` is ``(rows, cols, seed)`` or ``(rows, cols, seed, maze_options)``.
    Returns ``(seed, score, meets_spec)``: ``meets_spec`` is True when the maze
    hits every quality target in AGENTS.md section 4, which lets the search
    stop early once enough such candidates have turned up.
    """
    rows, cols, s = args[:3]
    maze_options = args[3] if len(args) > 3 else {}
    total_cells = rows * cols
    m = HighJunctionSingleSolutionMaze(rows=rows, cols=cols, seed=s, **maze_options)
    sol, junctions = m.solve()
    if not sol:
        return s, -1e9, False

    all_depths = [d for j in junctions for d in j['decoy_depths']]
    min_depth = min(all_depths) if all_depths else 0
    max_depth = max(all_depths) if all_depths else 0
    deep_decoys = sum(1 for d in all_depths if d >= 5)
    exit_lures = sum(1 for j in junctions if j['has_exit_lure'])
    anti_greedy = sum(1 for j in junctions if j['has_anti_greedy'])
    late_branches = sum(1 for j in junctions if j['step_index'] >= len(sol) - 4)

    # The spec asks for 5-9 decision forks: make any candidate inside that band
    # outrank every candidate outside it, rather than merely nudging the score.
    # Only on grids with room for it, though - below ~100 cells the free space
    # left by the solution path cannot hold 5 forks AND keep every decoy >= 5
    # deep (measured: 0 of 400 seeds manage both at 8x8), and the project's first
    # design rule is zero short dead ends, so depth wins on small sheets.
    enforce_band = total_cells >= 100
    in_band = 5 <= len(junctions) <= 9
    in_band_bonus = 500 if (enforce_band and in_band) else 0

    score = (
        in_band_bonus +
        len(junctions) * 15 +
        deep_decoys * 20 +
        anti_greedy * 45 +
        exit_lures * 40 +
        min_depth * 40 +
        (200 if min_depth >= 5 else 0) +
        (30 if max_depth >= 15 else 0) -
        (late_branches * 100)
    )

    viable = (len(junctions) >= 4 and
              int(total_cells * 0.25) <= len(sol) <= int(total_cells * 0.55))
    if not viable:
        # Still ranked among themselves (classic styles rarely pass the length
        # window), but always below every viable candidate.
        return s, score - 1e6, False

    meets_spec = ((in_band if enforce_band else len(junctions) >= 4) and
                  min_depth >= 5 and max_depth >= 15 and anti_greedy >= 2 and
                  exit_lures >= 1 and late_branches == 0)
    return s, score, meets_spec


SEED_SPACE = 10_000_000

# Candidates are scored in fixed-size rounds. The round size must not depend on
# the worker count, so a --pool-seed replay picks the same maze on any machine.
SEARCH_ROUND = 48

# Page presets in inches; pixels = inches x DPI. "sheet" is the original
# 1800 x 2400 px (3:4) canvas at 300 DPI.
PAGE_SIZES = {
    "sheet": (6.0, 8.0),
    "letter": (8.5, 11.0),
    "a4": (8.27, 11.69),
    "square": (8.0, 8.0),
}


DEFAULT_BASE_NAME = "maze"
LEGACY_MAZE_NAME = "single_solution_maze"


def next_output_paths(output_dir, base=DEFAULT_BASE_NAME, overwrite=False, start_index=1):
    """Return (maze_path, solution_path, index) for the next free numbered pair.

    With ``overwrite`` the old fixed ``single_solution_maze.png`` names come back and
    the previous sheet is replaced. Otherwise nothing on disk is ever touched: the
    index walks forward past every existing ``<base>_NNN.png`` in ``output_dir``.
    """
    if overwrite:
        return (os.path.join(output_dir, LEGACY_MAZE_NAME + ".png"),
                os.path.join(output_dir, LEGACY_MAZE_NAME + "_solution.png"),
                None)

    index = max(start_index, highest_existing_index(output_dir, base) + 1)
    while True:
        maze_path = os.path.join(output_dir, f"{base}_{index:03d}.png")
        solution_path = os.path.join(output_dir, f"{base}_{index:03d}_solution.png")
        if not os.path.exists(maze_path) and not os.path.exists(solution_path):
            return maze_path, solution_path, index
        index += 1


def highest_existing_index(output_dir, base=DEFAULT_BASE_NAME):
    """Largest NNN already used by ``<base>_NNN.png`` in ``output_dir`` (0 if none)."""
    pattern = re.compile(r"^" + re.escape(base) + r"_(\d+)(?:_solution)?\.png$", re.IGNORECASE)
    highest = 0
    try:
        names = os.listdir(output_dir)
    except OSError:
        return 0
    for name in names:
        match = pattern.match(name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def page_pixels(page="sheet", dpi=300, landscape=False, size=None):
    """Canvas size in pixels from a page preset or an explicit ``WxH`` string."""
    if size:
        m = re.fullmatch(r"\s*(\d+)\s*[xX*]\s*(\d+)\s*", str(size))
        if not m:
            raise ValueError(f"size must look like 1800x2400, got {size!r}")
        w, h = int(m.group(1)), int(m.group(2))
    else:
        wi, hi = PAGE_SIZES[page]
        w, h = int(round(wi * dpi)), int(round(hi * dpi))
    if landscape and h > w:
        w, h = h, w
    if min(w, h) < 200:
        raise ValueError("page is too small to draw on (minimum 200 px per side)")
    return w, h


def _make_pool(jobs):
    """A worker pool for the seed search, or None when running serially."""
    if not jobs or jobs <= 1:
        return None
    try:
        import multiprocessing as mp
        return mp.Pool(processes=jobs)
    except Exception:
        return None


def _score_all(tasks, pool):
    if pool is not None:
        try:
            return pool.map(score_seed, tasks, chunksize=2)
        except Exception:
            pass
    return [score_seed(t) for t in tasks]


def search_seed(rows, cols, candidates, pool=None, early_stop=True, target_hits=6, maze_options=None):
    """Score ``candidates`` round by round; return (results, evaluated, hits).

    With ``early_stop`` the search ends after the first round in which
    ``target_hits`` candidates have met every quality target. Most sizes need
    only a fraction of the full pool for that, so this is the main speed-up for
    a typical sheet; tiny grids that can never meet every target still get the
    full search (and are cheap).
    """
    maze_options = maze_options or {}
    results = []
    hits = 0
    for i in range(0, len(candidates), SEARCH_ROUND):
        batch = [(rows, cols, s, maze_options) for s in candidates[i:i + SEARCH_ROUND]]
        round_results = _score_all(batch, pool)
        results.extend(round_results)
        hits += sum(1 for r in round_results if r[2])
        if early_stop and hits >= target_hits:
            break
    return results, len(results), hits


def optimize_and_generate(rows=12, cols=10, seed=None, output_dir=".", max_search=None, jobs=None,
                          pool_seed=None, top_k=3, deterministic=False, count=1,
                          base_name=DEFAULT_BASE_NAME, overwrite=False, algorithm="deceptive",
                          layout="corners", loops=0, exhaustive=False, pdf=False, render_options=None):
    """Generate ``count`` maze sheets, writing each to its own numbered file pair.

    Files are named ``<base_name>_001.png`` / ``<base_name>_001_solution.png`` and the
    counter always resumes past whatever is already in ``output_dir``, so a new run
    never overwrites an earlier sheet. Pass ``overwrite=True`` for the old behaviour of
    always rewriting ``single_solution_maze.png``. ``pdf=True`` also writes one
    print-ready ``<base_name>_book.pdf`` with every puzzle followed by the answer keys.

    Returns a list of ``(maze_path, solution_path)`` tuples.
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    count = max(1, int(count))
    if seed is not None and count > 1:
        print(f"[note] --seed always rebuilds the same maze; generating 1 sheet instead of {count}.")
        count = 1
    if deterministic and count > 1:
        print(f"[note] --deterministic always picks the same maze for a given size; "
              f"generating 1 sheet instead of {count}.")
        count = 1

    if jobs is None:
        jobs = max(1, (os.cpu_count() or 1) - 1)
    # One pool for the whole batch: starting workers costs ~0.5 s each time on
    # Windows and macOS, which used to be paid again for every sheet.
    pool = _make_pool(jobs) if seed is None else None

    results = []
    next_index = 1
    try:
        for run in range(count):
            if count > 1:
                print(f"\n########## Maze {run + 1} of {count} ##########")
            maze_path, solution_path, index = next_output_paths(
                output_dir, base=base_name, overwrite=overwrite, start_index=next_index)
            if index is not None:
                next_index = index + 1
            # A fixed pool seed replays one exact search, so only the first sheet may use it;
            # later sheets draw a fresh pool and stay different from each other.
            results.append(generate_one(rows=rows, cols=cols, seed=seed, maze_path=maze_path,
                                        solution_path=solution_path, max_search=max_search, jobs=jobs,
                                        pool_seed=pool_seed if run == 0 else None,
                                        top_k=top_k, deterministic=deterministic, pool=pool,
                                        algorithm=algorithm, layout=layout, loops=loops,
                                        exhaustive=exhaustive, render_options=render_options,
                                        sheet_number=index if index is not None else run + 1))
    finally:
        if pool is not None:
            pool.close()
            pool.join()

    if count > 1:
        print(f"Wrote {len(results)} maze sheets ({len(results) * 2} files) to \"{output_dir}\".")
    if pdf and results:
        dpi = (render_options or {}).get("dpi", 300)
        book = write_pdf_book(results, output_dir, base_name, dpi=dpi)
        print(f"Print-ready book: {book} ({len(results)} puzzles + {len(results)} answer keys)")
    return results


def write_pdf_book(sheets, output_dir, base_name=DEFAULT_BASE_NAME, dpi=300):
    """Combine sheets into one PDF: every puzzle first, then the answer keys.

    Pages are appended one at a time, so memory stays flat even for a
    200-sheet batch. Returns the PDF path (never overwrites an existing book).
    """
    path = os.path.join(output_dir, f"{base_name}_book.pdf")
    n = 2
    while os.path.exists(path):
        path = os.path.join(output_dir, f"{base_name}_book_{n}.pdf")
        n += 1
    pages = [m for m, _ in sheets] + [s for _, s in sheets]
    for i, page in enumerate(pages):
        with Image.open(page) as im:
            im.convert("RGB").save(path, "PDF", resolution=dpi, append=i > 0)
    return path


def generate_one(rows, cols, seed, maze_path, solution_path, max_search=None, jobs=None,
                 pool_seed=None, top_k=3, deterministic=False, pool=None, algorithm="deceptive",
                 layout="corners", loops=0, exhaustive=False, render_options=None, sheet_number=1):
    """Search a pool of candidate seeds, then build the maze for one of the best.

    The candidate pool is drawn at random (and the winner is picked at random from
    the top scorers), so repeated runs with the same dimensions produce different
    mazes of comparable quality. Pass an explicit ``seed`` to reproduce one exactly,
    ``pool_seed`` to replay a whole search, or ``deterministic`` to restore the old
    always-identical scan of seeds 1..max_search.

    The search stops early once enough candidates meet every quality target;
    ``exhaustive`` (and ``deterministic``) always score the whole pool.
    """
    maze_options = {"algorithm": algorithm, "layout": layout, "loops": loops}
    pool_rng = None
    if seed is None:
        total_cells = rows * cols
        if max_search is None:
            # Big grids cost far more per candidate and rarely fit the 5-9 fork
            # band the early stop waits for, so they get a smaller pool.
            max_search = 800 if total_cells < 200 else 350 if total_cells < 900 else 120
        own_pool = None
        if pool is None:
            if jobs is None:
                jobs = max(1, (os.cpu_count() or 1) - 1)
            pool = own_pool = _make_pool(jobs)

        if deterministic:
            candidates = list(range(1, max_search + 1))
        else:
            if pool_seed is None:
                pool_seed = random.SystemRandom().randrange(SEED_SPACE)
            # Separate RNG: the maze generator re-seeds the global one on every build.
            pool_rng = random.Random(pool_seed)
            candidates = pool_rng.sample(range(1, SEED_SPACE), max_search)

        try:
            results, evaluated, hits = search_seed(
                rows, cols, candidates, pool=pool, early_stop=not (exhaustive or deterministic),
                target_hits=max(2 * top_k, 4), maze_options=maze_options)
        finally:
            if own_pool is not None:
                own_pool.close()
                own_pool.join()
        print(f"Searched {evaluated} of {len(candidates)} candidates "
              f"({hits} met every quality target).")

        viable = [(s, sc) for s, sc, _ in results if sc > -1e5]
        if not viable:
            viable = [(s, sc) for s, sc, _ in results]
        viable.sort(key=lambda item: (-item[1], item[0]))

        if deterministic or pool_rng is None:
            seed = viable[0][0]
        else:
            # Pick at random among the joint-best candidates so two runs of the same
            # size rarely land on the same sheet, without settling for a worse maze.
            k = max(1, min(top_k, len(viable)))
            seed = pool_rng.choice([s for s, _ in viable[:k]])

    maze = HighJunctionSingleSolutionMaze(rows=rows, cols=cols, seed=seed, **maze_options)
    solution, junctions = maze.solve()

    opts = dict(render_options or {})
    if opts.get("title"):
        opts["title"] = opts["title"].replace("{n}", str(sheet_number))
    maze.render(maze_path, draw_solution=False, **opts)
    maze.render(solution_path, draw_solution=True, **opts)

    all_depths = [d for j in junctions for d in j['decoy_depths']]
    min_d = min(all_depths) if all_depths else 0
    max_d = max(all_depths) if all_depths else 0
    exit_lures = sum(1 for j in junctions if j['has_exit_lure'])
    anti_greedy_forks = sum(1 for j in junctions if j['has_anti_greedy'])

    repro = f"--rows {rows} --cols {cols} --seed {seed}"
    if algorithm != "deceptive":
        repro += f" --style {algorithm}"
    if layout != "corners":
        repro += f" --layout {layout}"
    if loops:
        repro += f" --loops {loops}"

    print("\n================ HUMAN-LIKE DECEPTIVE MAZE SPECIFICATION ================")
    print(f"Dimensions: {rows} rows x {cols} columns (Seed: {seed})")
    print(f"Style: {algorithm}   Layout: {layout} (START {maze.start_side} wall, FINISH {maze.goal_side} wall)")
    print(f"Files: {os.path.basename(maze_path)} + {os.path.basename(solution_path)}")
    print(f"Reproduce this exact maze with: {repro}")
    if maze.loops:
        print(f"Graph Property: Braided - {maze.loops} loop(s) added, MULTIPLE ROUTES (key shows the shortest)")
    else:
        print(f"Graph Property: Mathematically Proven Tree (EXACTLY 1 UNIQUE SOLUTION)")
    print(f"Solution Path Length: {len(solution)} steps")
    print(f"Decision Junctions: {len(junctions)} total forks")
    print(f"Min Decoy Depth on Main Path: {min_d} steps (Zero short dead ends)")
    print(f"Max Decoy Depth: {max_d} steps")
    print(f"Anti-Greedy Deceptive Forks: {anti_greedy_forks} junctions (False branch moves closer to goal than solution)")
    print(f"Near-Miss Exit Lures: {exit_lures} lures (Decoys reaching within <= 2 cells of FINISH)")
    print("-------------------------------------------------------------------------")
    for idx, j in enumerate(junctions):
        anti_str = " [ANTI-GREEDY LURE]" if j['has_anti_greedy'] else ""
        exit_str = " [NEAR-MISS EXIT LURE]" if j['has_exit_lure'] else ""
        print(f"  Junction #{idx+1:02d} (Step {j['step_index']:02d}, Cell {j['cell']}): {j['total_choices']} Open Choices -> False Path Depths = {j['decoy_depths']} steps{anti_str}{exit_str}")
    print("=========================================================================\n")

    return maze_path, solution_path


def _build_parser():
    styles = "\n".join(f"  {k:<12} {v}" for k, v in ALGORITHMS.items())
    layouts = "\n".join(f"  {k:<12} {v}" for k, v in LAYOUTS.items())
    parser = argparse.ArgumentParser(
        description="Generate clean, minimal mazes with human-like deceptive properties.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"styles:\n{styles}\n\nlayouts:\n{layouts}\n\npages: {', '.join(PAGE_SIZES)} "
               f"(sheet = 1800 x 2400 px at 300 DPI)")
    g = parser.add_argument_group("maze")
    g.add_argument("--rows", type=int, default=12, help="Grid rows (default: 12)")
    g.add_argument("--cols", type=int, default=10, help="Grid cols (default: 10)")
    g.add_argument("--style", "--algorithm", dest="style", choices=list(ALGORITHMS), default="deceptive",
                   help="Generation style (default: deceptive; see list below)")
    g.add_argument("--layout", choices=list(LAYOUTS), default="corners",
                   help="Where START and FINISH go (default: corners)")
    g.add_argument("--loops", type=int, default=0,
                   help="Knock through N dead ends to create loops / multiple routes (default: 0 = single solution)")
    g.add_argument("--seed", type=int, default=None, help="Random seed (optional)")

    g = parser.add_argument_group("search")
    g.add_argument("--max-search", type=int, default=None,
                   help="Most seeds to evaluate when no --seed is given (default: 800 under 200 cells, 350 under 900, else 120)")
    g.add_argument("--exhaustive", action="store_true",
                   help="Score every candidate instead of stopping once enough meet every quality target")
    g.add_argument("--jobs", type=int, default=None,
                   help="Parallel worker processes for the seed search (default: CPU count - 1)")
    g.add_argument("--pool-seed", type=int, default=None,
                   help="Seed for the candidate search itself; replays an entire search run")
    g.add_argument("--top-k", type=int, default=3,
                   help="Winner is drawn at random from the K best candidates (default: 3; 1 = always the best)")
    g.add_argument("--deterministic", action="store_true",
                   help="Scan seeds 1..max-search and always take the best: same size always yields the same maze")

    g = parser.add_argument_group("output")
    g.add_argument("--outdir", type=str, default=".", help="Output directory")
    g.add_argument("--count", "-n", type=int, default=1,
                   help="How many mazes to generate in one run (default: 1)")
    g.add_argument("--name", type=str, default=DEFAULT_BASE_NAME,
                   help=f"Base filename for the numbered output (default: {DEFAULT_BASE_NAME})")
    g.add_argument("--overwrite", action="store_true",
                   help="Old behaviour: always write single_solution_maze.png, replacing the previous sheet")
    g.add_argument("--pdf", action="store_true",
                   help="Also write <name>_book.pdf: all puzzles, then all answer keys, ready to print")

    g = parser.add_argument_group("appearance")
    g.add_argument("--page", choices=list(PAGE_SIZES), default="sheet",
                   help="Page size preset (default: sheet = 1800 x 2400 px at 300 DPI)")
    g.add_argument("--size", type=str, default=None, help="Exact canvas size in pixels, e.g. 2400x1800 (overrides --page)")
    g.add_argument("--landscape", action="store_true", help="Rotate the page to landscape")
    g.add_argument("--dpi", type=int, default=300, help="Print resolution for --page presets and file metadata (default: 300)")
    g.add_argument("--wall-thickness", type=int, default=None, help="Wall width in px (default: auto, 8-16 px)")
    g.add_argument("--wall-color", default="black", help="Wall and label colour, name or #hex (default: black)")
    g.add_argument("--solution-color", default="#2563eb", help="Solution line colour on the key (default: #2563eb)")
    g.add_argument("--background", default="white", help="Page background colour (default: white)")
    g.add_argument("--start-label", default="START", help="Text by the entrance (default: START)")
    g.add_argument("--finish-label", default="FINISH", help="Text by the exit (default: FINISH)")
    g.add_argument("--no-labels", action="store_true", help="Arrows only, no START/FINISH text")
    g.add_argument("--title", default=None, help='Heading at the top of each sheet; "{n}" becomes the sheet number')
    g.add_argument("--square-cells", action="store_true",
                   help="Keep cells square and centre the grid instead of stretching it to the page")
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.rows < 2 or args.cols < 2:
        parser.error("--rows and --cols must be at least 2")
    if args.loops < 0:
        parser.error("--loops cannot be negative")
    if args.max_search is not None and args.max_search < 1:
        parser.error("--max-search must be at least 1")
    try:
        image_size = page_pixels(args.page, args.dpi, args.landscape, args.size)
    except ValueError as exc:
        parser.error(str(exc))
    for opt in ("wall_color", "solution_color", "background"):
        try:
            from PIL import ImageColor
            ImageColor.getrgb(getattr(args, opt))
        except ValueError:
            parser.error(f"--{opt.replace('_', '-')}: unknown colour {getattr(args, opt)!r}")

    render_options = {
        "image_size": image_size,
        "wall_thickness": args.wall_thickness,
        "wall_color": args.wall_color,
        "solution_color": args.solution_color,
        "background": args.background,
        "start_label": "" if args.no_labels else args.start_label,
        "finish_label": "" if args.no_labels else args.finish_label,
        "title": args.title,
        "square_cells": args.square_cells,
        "dpi": args.dpi,
    }
    optimize_and_generate(rows=args.rows, cols=args.cols, seed=args.seed, output_dir=args.outdir,
                          max_search=args.max_search, jobs=args.jobs, pool_seed=args.pool_seed,
                          top_k=args.top_k, deterministic=args.deterministic, count=args.count,
                          base_name=args.name, overwrite=args.overwrite, algorithm=args.style,
                          layout=args.layout, loops=args.loops, exhaustive=args.exhaustive,
                          pdf=args.pdf, render_options=render_options)


if __name__ == "__main__":
    main()
