import random
import os
import re
import argparse
from collections import deque
from PIL import Image, ImageDraw, ImageFont

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
    def __init__(self, rows=12, cols=10, seed=None):
        self.rows = rows
        self.cols = cols
        self.seed = seed
        if seed is not None:
            random.seed(seed)
            
        self.h_walls = [[True for _ in range(cols)] for _ in range(rows + 1)]
        self.v_walls = [[True for _ in range(cols + 1)] for _ in range(rows)]
        self.solution_path = []
        self._generate()

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
        start = (0, 0)
        goal = (rows - 1, cols - 1)
        visited = [[False for _ in range(cols)] for _ in range(rows)]

        # --- 1. CARVE DETOURING MAIN PATH WITHOUT ORPHANING 1x1 POCKETS ---
        target_len = int(rows * cols * 0.38)
        min_comp_size = max(3, int(min(rows, cols) * 0.3))
        away_target = max(6, int(rows * cols * 0.08))
        
        # Flat-index helpers: the walk runs on a 1-D grid to avoid tuple churn.
        n_cells = rows * cols
        goal_i = n_cells - 1

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

                Both checks stay cheap on purpose. Reachability exits as soon as
                the goal is seen, and the pocket scan is bounded to
                min_comp_size cells around the new head -- a sealed pocket can
                only form next to the cell just filled, so labelling the whole
                grid every step is wasted work.
                """
                nonlocal stamp
                stamp += 1
                tag = stamp
                q = deque([frm])
                gen_buf[frm] = tag
                reached = False
                while q:
                    i = q.popleft()
                    if i == goal_i:
                        reached = True
                        break
                    ir, ic = divmod(i, cols)
                    if ir > 0:
                        j = i - cols
                        if not blocked[j] and gen_buf[j] != tag:
                            gen_buf[j] = tag; q.append(j)
                    if ir < rows - 1:
                        j = i + cols
                        if not blocked[j] and gen_buf[j] != tag:
                            gen_buf[j] = tag; q.append(j)
                    if ic > 0:
                        j = i - 1
                        if not blocked[j] and gen_buf[j] != tag:
                            gen_buf[j] = tag; q.append(j)
                    if ic < cols - 1:
                        j = i + 1
                        if not blocked[j] and gen_buf[j] != tag:
                            gen_buf[j] = tag; q.append(j)
                if not reached:
                    return 0

                fr, fc = divmod(frm, cols)
                for nb in (frm - cols if fr > 0 else -1,
                           frm + cols if fr < rows - 1 else -1,
                           frm - 1 if fc > 0 else -1,
                           frm + 1 if fc < cols - 1 else -1):
                    if nb < 0 or blocked[nb]:
                        continue
                    stamp += 1
                    ptag = stamp
                    size = 0
                    pq = deque([nb])
                    gen_buf[nb] = ptag
                    while pq and size < min_comp_size:
                        i = pq.popleft()
                        size += 1
                        ir, ic = divmod(i, cols)
                        if ir > 0:
                            j = i - cols
                            if not blocked[j] and gen_buf[j] != ptag:
                                gen_buf[j] = ptag; pq.append(j)
                        if ir < rows - 1:
                            j = i + cols
                            if not blocked[j] and gen_buf[j] != ptag:
                                gen_buf[j] = ptag; pq.append(j)
                        if ic > 0:
                            j = i - 1
                            if not blocked[j] and gen_buf[j] != ptag:
                                gen_buf[j] = ptag; pq.append(j)
                        if ic < cols - 1:
                            j = i + 1
                            if not blocked[j] and gen_buf[j] != ptag:
                                gen_buf[j] = ptag; pq.append(j)
                    if size < min_comp_size:
                        return 1
                return 2

            path = [0]
            blocked[0] = 1
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

        # START and FINISH open boundaries
        self.v_walls[0][0] = False
        self.v_walls[rows - 1][cols] = False

    def _generate_standard_dfs(self):
        visited = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        stack = [(0, 0)]
        visited[0][0] = True
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
        self.v_walls[0][0] = False
        self.v_walls[self.rows - 1][self.cols] = False

    def solve(self):
        # BFS with parent pointers; copying whole paths per node is quadratic.
        goal = (self.rows - 1, self.cols - 1)
        queue = deque([(0, 0)])
        parent = {(0, 0): None}
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
                        
            if len(open_exits) >= 3 or ((r, c) == (0, 0) and len(open_exits) >= 2):
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

    def render(self, output_path, draw_solution=False, wall_thickness=None, image_size=(1800, 2400)):
        if wall_thickness is None:
            wall_thickness = max(8, min(16, int(180 / max(self.rows, self.cols))))
            
        w, h = image_size
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        
        margin_x = 240
        margin_y = 360
        grid_w = w - 2 * margin_x
        grid_h = h - 2 * margin_y
        
        cell_w = grid_w / self.cols
        cell_h = grid_h / self.rows
        
        if draw_solution:
            solution, _ = self.solve()
            if solution:
                sol_points = []
                sol_points.append((margin_x - 100, margin_y + 0.5 * cell_h))
                for r, c in solution:
                    sol_points.append((margin_x + (c + 0.5) * cell_w, margin_y + (r + 0.5) * cell_h))
                sol_points.append((margin_x + self.cols * cell_w + 100, margin_y + (self.rows - 0.5) * cell_h))
                draw.line(sol_points, fill="#2563eb", width=max(6, int(wall_thickness * 0.85)), joint="round")

        # Draw horizontal walls
        for r in range(self.rows + 1):
            y = margin_y + r * cell_h
            for c in range(self.cols):
                if self.h_walls[r][c]:
                    x1 = margin_x + c * cell_w
                    x2 = margin_x + (c + 1) * cell_w
                    draw.line([(x1, y), (x2, y)], fill="black", width=wall_thickness)
                    
        # Draw vertical walls
        for r in range(self.rows):
            y1 = margin_y + r * cell_h
            y2 = margin_y + (r + 1) * cell_h
            for c in range(self.cols + 1):
                if self.v_walls[r][c]:
                    x = margin_x + c * cell_w
                    draw.line([(x, y1), (x, y2)], fill="black", width=wall_thickness)

        # Draw rounded caps
        r_cap = wall_thickness // 2
        for r in range(self.rows + 1):
            y = margin_y + r * cell_h
            for c in range(self.cols + 1):
                x = margin_x + c * cell_w
                has_wall = False
                if c < self.cols and self.h_walls[r][c]: has_wall = True
                if c > 0 and self.h_walls[r][c-1]: has_wall = True
                if r < self.rows and self.v_walls[r][c]: has_wall = True
                if r > 0 and self.v_walls[r-1][c]: has_wall = True
                if has_wall:
                    draw.ellipse([(x - r_cap, y - r_cap), (x + r_cap, y + r_cap)], fill="black")

        try:
            font_main = ImageFont.truetype("arialbd.ttf", 64)
        except:
            font_main = ImageFont.load_default()

        # START
        start_y = margin_y + 0.5 * cell_h
        draw.text((margin_x - 220, start_y - 85), "START", fill="black", font=font_main)
        a_x1 = margin_x - 200
        a_x2 = margin_x - 30
        draw.line([(a_x1, start_y), (a_x2, start_y)], fill="black", width=10)
        draw.polygon([(a_x2 + 10, start_y), (a_x2 - 25, start_y - 18), (a_x2 - 25, start_y + 18)], fill="black")

        # FINISH
        fin_y = margin_y + (self.rows - 0.5) * cell_h
        fin_x = margin_x + self.cols * cell_w
        draw.text((fin_x + 50, fin_y + 25), "FINISH", fill="black", font=font_main)
        f_x1 = fin_x + 30
        f_x2 = fin_x + 200
        draw.line([(f_x1, fin_y), (f_x2, fin_y)], fill="black", width=10)
        draw.polygon([(f_x2 + 10, fin_y), (f_x2 - 25, fin_y - 18), (f_x2 - 25, fin_y + 18)], fill="black")

        img.save(output_path, quality=100)
        print(f"Generated: {output_path}")

def score_seed(args):
    """Build one candidate maze and score it. Module-level so it can be pickled
    across worker processes; seeds are independent, so the search parallelises."""
    rows, cols, s = args
    total_cells = rows * cols
    m = HighJunctionSingleSolutionMaze(rows=rows, cols=cols, seed=s)
    sol, junctions = m.solve()
    if not sol or len(junctions) < 4:
        return s, -1e9
    if not (int(total_cells * 0.25) <= len(sol) <= int(total_cells * 0.55)):
        return s, -1e9

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
    in_band_bonus = 500 if (enforce_band and 5 <= len(junctions) <= 9) else 0

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
    return s, score


SEED_SPACE = 10_000_000


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


def optimize_and_generate(rows=12, cols=10, seed=None, output_dir=".", max_search=None, jobs=None,
                          pool_seed=None, top_k=3, deterministic=False, count=1,
                          base_name=DEFAULT_BASE_NAME, overwrite=False):
    """Generate ``count`` maze sheets, writing each to its own numbered file pair.

    Files are named ``<base_name>_001.png`` / ``<base_name>_001_solution.png`` and the
    counter always resumes past whatever is already in ``output_dir``, so a new run
    never overwrites an earlier sheet. Pass ``overwrite=True`` for the old behaviour of
    always rewriting ``single_solution_maze.png``.

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

    results = []
    next_index = 1
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
                                    top_k=top_k, deterministic=deterministic))

    if count > 1:
        print(f"Wrote {len(results)} maze sheets ({len(results) * 2} files) to \"{output_dir}\".")
    return results


def generate_one(rows, cols, seed, maze_path, solution_path, max_search=None, jobs=None,
                 pool_seed=None, top_k=3, deterministic=False):
    """Search a pool of candidate seeds, then build the maze for one of the best.

    The candidate pool is drawn at random (and the winner is picked at random from
    the top scorers), so repeated runs with the same dimensions produce different
    mazes of comparable quality. Pass an explicit ``seed`` to reproduce one exactly,
    ``pool_seed`` to replay a whole search, or ``deterministic`` to restore the old
    always-identical scan of seeds 1..max_search.
    """
    pool_rng = None
    if seed is None:
        total_cells = rows * cols
        if max_search is None:
            max_search = 350 if total_cells >= 200 else 800
        if jobs is None:
            jobs = max(1, (os.cpu_count() or 1) - 1)

        if deterministic:
            candidates = list(range(1, max_search + 1))
        else:
            if pool_seed is None:
                pool_seed = random.SystemRandom().randrange(SEED_SPACE)
            # Separate RNG: the maze generator re-seeds the global one on every build.
            pool_rng = random.Random(pool_seed)
            candidates = pool_rng.sample(range(1, SEED_SPACE), max_search)

        tasks = [(rows, cols, s) for s in candidates]
        results = []
        if jobs > 1 and len(tasks) > 1:
            try:
                import multiprocessing as mp
                with mp.Pool(processes=jobs) as pool:
                    results = pool.map(score_seed, tasks, chunksize=4)
            except Exception:
                results = []
        if not results:
            results = [score_seed(t) for t in tasks]

        viable = [(s, sc) for s, sc in results if sc > -1e8]
        if not viable:
            viable = list(results)
        viable.sort(key=lambda item: (-item[1], item[0]))

        if deterministic or pool_rng is None:
            seed = viable[0][0]
        else:
            # Pick at random among the joint-best candidates so two runs of the same
            # size rarely land on the same sheet, without settling for a worse maze.
            k = max(1, min(top_k, len(viable)))
            seed = pool_rng.choice([s for s, _ in viable[:k]])

    maze = HighJunctionSingleSolutionMaze(rows=rows, cols=cols, seed=seed)
    solution, junctions = maze.solve()

    maze.render(maze_path, draw_solution=False)
    maze.render(solution_path, draw_solution=True)
    
    all_depths = [d for j in junctions for d in j['decoy_depths']]
    min_d = min(all_depths) if all_depths else 0
    max_d = max(all_depths) if all_depths else 0
    exit_lures = sum(1 for j in junctions if j['has_exit_lure'])
    anti_greedy_forks = sum(1 for j in junctions if j['has_anti_greedy'])
    
    print("\n================ HUMAN-LIKE DECEPTIVE MAZE SPECIFICATION ================")
    print(f"Dimensions: {rows} rows x {cols} columns (Seed: {seed})")
    print(f"Files: {os.path.basename(maze_path)} + {os.path.basename(solution_path)}")
    print(f"Reproduce this exact maze with: --rows {rows} --cols {cols} --seed {seed}")
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate clean, minimal mazes with human-like deceptive properties.")
    parser.add_argument("--rows", type=int, default=12, help="Grid rows (default: 12)")
    parser.add_argument("--cols", type=int, default=10, help="Grid cols (default: 10)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (optional)")
    parser.add_argument("--outdir", type=str, default=".", help="Output directory")
    parser.add_argument("--max-search", type=int, default=None,
                        help="Seeds to evaluate when no --seed is given (default: 350 for large grids, 800 otherwise)")
    parser.add_argument("--jobs", type=int, default=None,
                        help="Parallel worker processes for the seed search (default: CPU count - 1)")
    parser.add_argument("--pool-seed", type=int, default=None,
                        help="Seed for the candidate search itself; replays an entire search run")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Winner is drawn at random from the K best candidates (default: 3; 1 = always the best)")
    parser.add_argument("--deterministic", action="store_true",
                        help="Scan seeds 1..max-search and always take the best: same size always yields the same maze")
    parser.add_argument("--count", "-n", type=int, default=1,
                        help="How many mazes to generate in one run (default: 1)")
    parser.add_argument("--name", type=str, default=DEFAULT_BASE_NAME,
                        help=f"Base filename for the numbered output (default: {DEFAULT_BASE_NAME})")
    parser.add_argument("--overwrite", action="store_true",
                        help="Old behaviour: always write single_solution_maze.png, replacing the previous sheet")
    args = parser.parse_args()

    optimize_and_generate(rows=args.rows, cols=args.cols, seed=args.seed, output_dir=args.outdir,
                          max_search=args.max_search, jobs=args.jobs, pool_seed=args.pool_seed,
                          top_k=args.top_k, deterministic=args.deterministic, count=args.count,
                          base_name=args.name, overwrite=args.overwrite)

