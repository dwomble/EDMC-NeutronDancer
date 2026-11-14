import heapq, math
from dataclasses import dataclass
from operator import itemgetter

from ..ship import Ship
from .index import Index, Combined

COARSE:int = 10      # 100 Ly cells per density-map cell edge
STEP:float = 250.0   # sampling step along the line to the destination
WEIGHTS:tuple = (1.15, 1.3, 1.6, 2.0)
HORIZON:float = 2500.0  # how far ahead a replan from a fuel star reaches before rejoining the route

@dataclass
class Step:
    """One jump of a filled-in route."""
    name:str
    kind:str        # 'boost', 'plain' or 'fail'
    dist:float
    fuel:float      # fuel left after landing, and after any refuel
    refuel:bool = False
    pos:tuple = ()
    scoop:bool = False
    id64:int|None = None  # system address; None for the destination, which the caller knows

class Stuck(Exception):
    """The route cannot continue from here."""

class Planner:
    """
    Fewest-jump neutron routes using local star data, guided by a coarse map of neutron density, flown with fuel and scoop stops.
    """

    def __init__(self, neu:Index|Combined, sc:Index|Combined) -> None:
        self.neu:Index|Combined = neu
        self.sc:Index|Combined = sc
        self.counts:dict = {}
        for idx in (neu.base, neu.add) if isinstance(neu, Combined) else (neu,):
            for j, k in enumerate(idx.ukeys):
                c:tuple = (((k >> 22) - 1024) // COARSE, (((k >> 11) & 2047) - 1024) // COARSE, ((k & 2047) - 1024) // COARSE)
                self.counts[c] = self.counts.get(c, 0) + idx.starts[j + 1] - idx.starts[j]

    @staticmethod
    def jumps(dist:float, rng:float, mult:float, boosted:bool) -> int:
        """Jumps for a leg: one boosted jump then plain jumps, or plain jumps only."""
        if not boosted: return math.ceil(dist / rng)
        return 1 + math.ceil(max(0.0, dist - mult * rng) / rng)

    def plot(self, ship:Ship, src:tuple, dest:tuple, fuel:float, cargo:float = 0, reserve:float = 0) -> list[Step]:
        """Real jumps from src to dest for this ship and starting fuel, refuelling on scoopable stars."""
        # Settings for this plot, shared by the searches, their estimates and the jumps
        self.ship, self.cargo, self.dest = ship, cargo, dest
        self.rng:float = ship.jump_range(ship.tank_size, cargo)  # full-tank range: the heaviest, so always reachable
        self.plain:float = self.rng * 0.999  # 0.999 keeps a jump exactly at the limit from failing on rounding
        self.mult:float = ship.supercharge_multiplier
        self.boost:float = self.mult * self.rng  # longest supercharged jump

        # Refuel below one full jump, or the reserve if larger; a full jump left can usually reach a scoopable star
        self.low:float = max(ship.max_fuel_per_jump, reserve)

        # Fuel a typical boost burns, for counting the refuel stops still to come
        self.burn:float = ship.fuel_cost(self.boost * 0.999, ship.tank_size, cargo, True)

        # Turn each density cell's neutron count into jumps per Ly at this range.
        # n neutrons spread evenly through a 1000 Ly cube sit about gap = cube root of (volume / n) apart.
        # One boosted jump covers min(gap, boost) at best; any gap beyond boost has to be crossed in plain jumps.
        self.rates:dict = {}
        for c, n in self.counts.items():
            gap:float = (1e9 / n) ** (1 / 3)
            self.rates[c] = (1 + max(0.0, gap - self.boost) / self.rng) / max(gap, self.boost)

        # Full-tank range, per-node range, and per-node with extra fuel stops, each flown topping up or not
        best:list[Step] = []
        for pernode, stops in ((False, False), (True, False), (True, True)):
            self.pernode, self.stops, self.fuel = pernode, stops, fuel
            path:list = self._route(src, dest)
            for topup in (False, True):
                self.topup:bool = topup
                steps:list[Step] = self._fly(src, dest, fuel, path)
                if not best or (steps[-1].kind == 'fail', len(steps)) < (best[-1].kind == 'fail', len(best)): best = steps
        return best

    def _fly(self, src:tuple, dest:tuple, fuel:float, path:list) -> list[Step]:
        """Fly the planned path; each refuel replans only to a horizon ahead and rejoins it."""
        self.here:tuple = src
        self.fuel:float = fuel
        self.steps:list[Step] = []
        self.start, self.goal = src, dest
        self.path:list = path
        self.k:int = 0
        self.saved:list = []
        self.tried:set = set()

        while self.k < len(self.path) - 1:
            # Each leg's starting state is saved so a failure can rewind to it
            self.saved.append((len(self.steps), self.here, self.fuel, self.start, self.path, self.k))
            self.refuelled:bool = False
            try:
                self._fly_leg(self.path[self.k], self.path[self.k + 1])
            except Stuck as e:
                if not self._rewind():
                    # Nowhere left to refuel: keep the jumps so far, so the caller can show where it got stuck
                    self.steps.append(Step(str(e), 'fail', 0.0, self.fuel))
                    return self.steps

            if not self.refuelled:
                self.k += 1
                continue

            # Refuelling on landing at the leg's end finishes it, or the replan jumps 0 Ly back onto it
            if self.here == self._node_pos(self.path[self.k + 1]): self.k += 1
            self._replan()

        return self.steps

    def _replan(self) -> None:
        """Just refuelled, maybe off the planned line: plan afresh to the first node a horizon away, then rejoin."""
        ahead:list = self.path[self.k + 1:]
        here:tuple = self.here
        w:int = next((i for i, n in enumerate(ahead) if math.dist(here, self._node_pos(n)) >= HORIZON), len(ahead) - 1)
        m:int = ahead[w]
        old:list = [self._node_pos(n) for n in ahead[:w + 1]]
        new:list = self._route(here, old[-1])
        self.goal, self.k = self.dest, 0

        # Switch when the fresh plan is at least as good as carrying on, both counted the same way
        stay:int = 0
        fuel:float = self.fuel
        p:tuple = here
        boosted:bool = self._at_neutron(here)
        for n, q in zip(ahead, old):
            hops, fuel = self._leg_cost(math.dist(p, q), fuel, boosted, self._stop(n))
            stay += hops
            p, boosted = q, n >= 0
        joins:bool = m >= 0 and new[-2] == m
        if self.found - joins > stay:
            self.path = [-1] + ahead
            return

        # The new plan ends at m's position as its own destination; swap that for m itself and the old route beyond
        self.path = new if m == -2 else new[:-1] + (ahead[w + 1:] if joins else ahead[w:])

    def _rewind(self) -> bool:
        """Back up to an earlier leg start, at most four, and land on the nearest scoopable star from there."""
        for _ in range(4):
            if not self.saved: return False
            n, self.here, self.fuel, self.start, self.path, self.k = self.saved.pop()
            self.goal = self.dest
            del self.steps[n:]

            # Each place gets one detour, so a hopeless region can't loop
            spot:tuple = tuple(round(v) for v in self.here)
            if spot in self.tried: continue
            self.tried.add(spot)

            near:list = [h for h in self.sc.near(self.here, self.plain) if h[1] > 1]
            if not near: continue
            s:int = min(near, key=itemgetter(1))[0]
            try:
                self._jump_to(self.sc.pos(s), self.sc.name(s), self.sc.id64(s), 'plain', False, True, True)
                return True
            except Stuck:
                continue
        return False

    def _node_pos(self, n:int) -> tuple:
        """Coordinates of a path node: a neutron index, or -1 for the plan's start and -2 for its goal."""
        return self.start if n == -1 else self.goal if n == -2 else self.neu.pos(n)

    def _route(self, start:tuple, goal:tuple) -> list:
        """Shorter of the flat and density-guided neutron paths from start to goal; sets found to its jumps."""
        self.start, self.goal = start, goal
        self.memo:dict = {}

        # The final leg must start at a neutron, and the closest one to the goal is `nearest` Ly out.
        # Probe outward from the goal, doubling the radius, until a neutron turns up.
        probe:float = self.boost
        while not (ring := self.neu.near(goal, probe)) and probe < 8000: probe *= 2
        self.nearest:float = min((dm for _, dm in ring), default=0.0)

        # No route can finish in fewer jumps than that final leg, so it seeds every estimate
        self.final_jumps:int = self.jumps(self.nearest, self.rng, self.mult, True) if ring else 0

        # Each estimate tries the most careful weight that finishes within budget
        found:list = []
        for dense in (False, True):
            for w in WEIGHTS:
                res:tuple|None = self._search(w, 3000, dense)
                if res: break
            else:
                res = self._search(WEIGHTS[-1] * 2, 0, dense)
            if res: found.append(res)

        path, self.found = min(found, key=itemgetter(1))
        return path

    def _search(self, w:float, limit:int, dense:bool) -> tuple|None:
        """Weighted A* from start to goal as (path, jumps); None if it expands more than limit nodes."""
        neu:Index|Combined = self.neu
        goal:tuple = self.goal

        start_boost:bool = self._at_neutron(self.start)

        # g: fewest jumps found to each node; fuel: what that path leaves there; prev: the node it came from
        g:dict = {-1: 0}
        fuel:dict = {-1: self.fuel}
        prev:dict = {}

        # Queue entries are (priority, distance left, node); distance left breaks ties toward nodes nearer the goal
        openq:list = [(0.0, math.dist(self.start, goal), -1)]
        done:set = set()

        while openq:
            _, _, n = heapq.heappop(openq)

            # A node can be queued several times as better costs are found; only its first pop counts
            if n in done: continue
            if n == -2: break
            done.add(n)

            # Over budget means this weight is too careful for the region; _route() retries with a greedier one
            if limit and len(done) > limit: return None

            # Only a jump leaving a neutron is supercharged, so the start's first leg is plain unless it starts at one
            p:tuple = self._node_pos(n)
            here:float = math.dist(p, goal)
            boosted:bool = n >= 0 or start_boost

            # Range grows as the tank empties, so each node jumps with the fuel its best path leaves there
            rng:float = self.ship.jump_range(fuel[n], self.cargo) * 0.999 if self.pernode else self.rng

            # Start by looking one boosted jump plus one plain jump out, and only at neutrons that get closer
            rad:float = (self.mult + 1) * rng if boosted else max(self.mult * rng, 2 * rng)
            ahead = lambda rr: [(m, dm, left) for m, dm in neu.near(p, rr)
                                if m not in done and (left := math.dist(neu.pos(m), goal)) < here]

            # Sparse regions need a wider net, or the search dead-ends without trying a longer plain-jump leg
            cands:list = ahead(rad)
            while len(cands) < 3 and rad < 4000:
                rad *= 1.5
                cands = ahead(rad)

            # Dense regions offer thousands; keep the 40 covering most distance per jump, plus the boost each gives
            nxt:float = self.mult * rng
            rate = lambda c: (here - c[2] + nxt) / (self.jumps(c[1], rng, self.mult, boosted) + 1)
            best:list = heapq.nlargest(40, cands, key=rate)

            # Fuel stops rarely rank there, yet landing on one when low saves a refuel jump, which per-node plans count
            if self.stops: best +=heapq.nlargest(10, [c for c in cands if self._stop(c[0]) and c not in best], key=rate)
            cands = best

            # Always offer flying straight to the goal, so a route exists even with no neutrons ahead
            cands.append((-2, here, 0.0))

            for m, dm, left in cands:
                hops, after = self._leg_cost(dm, fuel[n], boosted, self._stop(m))
                cost:int = g[n] + hops
                if cost >= g.get(m, 1 << 30): continue
                g[m], fuel[m] = cost, after
                prev[m] = n

                # Priority is jumps so far plus w times the estimated jumps still to go; w > 1 searches faster
                rest:float = 0.0 if m == -2 else self._density_estimate(self._node_pos(m), left) if dense else self._flat_estimate(left)

                # Each refuel stop is a whole extra jump, so count the ones this node's fuel can't cover
                if self.pernode: rest += max(0.0, rest * self.burn - (after - self.low)) / (self.ship.tank_size - self.low)
                heapq.heappush(openq, (cost + w * rest, left, m))

        if -2 not in prev: return None
        path:list = [-2]
        while path[-1] != -1: path.append(prev[path[-1]])
        return path[::-1], g[-2]

    def _at_neutron(self, p:tuple) -> bool:
        """Whether p is a neutron's system, like a fuel stop just refuelled at, so it can boost from there."""
        return any(d < 0.01 for _, d in self.neu.near(p, 0.01))

    def _stop(self, n:int) -> bool:
        """Whether path node n is a neutron that's also a fuel stop."""
        return n >= 0 and self.neu.fuel(n)

    def _leg_cost(self, dist:float, fuel:float, boosted:bool, stop:bool) -> tuple:
        """Jumps and fuel left for a leg; running low refuels, costing a jump unless the leg ends at a stop."""
        ship, cargo = self.ship, self.cargo
        if not self.pernode: return self.jumps(dist, self.rng, self.mult, boosted), ship.tank_size
        rng:float = ship.jump_range(fuel, cargo) * 0.999
        n:int = self.jumps(dist, rng, self.mult, boosted)
        first:float = min(dist, self.mult * rng if boosted else rng)
        fuel -= ship.fuel_cost(first, fuel, cargo, boosted)
        if n > 1: fuel -= (n - 1) * ship.fuel_cost((dist - first) / (n - 1), fuel, cargo)
        if fuel >= self.low: return n, fuel
        return (n if stop and fuel >= 0 else n + 1), ship.tank_size

    def _flat_estimate(self, left:float) -> float:
        """Jumps-to-go estimate assuming every jump left is a full boost."""
        return self.final_jumps + max(0.0, left - self.nearest) / self.boost

    def _cell_rate(self, p:tuple) -> float:
        """Jumps per Ly in p's density cell; a cell with no neutrons means plain jumps all the way through it."""
        size:float = 100.0 * COARSE
        return self.rates.get((int(p[0] // size), int(p[1] // size), int(p[2] // size)), 1 / self.rng)

    def _density_estimate(self, p:tuple, left:float) -> float:
        """Jumps-to-go estimate from per-cell jump rates along the line to the goal, plus the final leg."""
        # Already inside the final leg's radius: only that leg remains
        if left <= self.nearest: return float(self.final_jumps)

        # Integrating the line is the costly part, and the search asks for it on every queued node.
        # Nodes in the same STEP-sized block share one integral, taken from the block's centre.
        q:tuple = (int(p[0] // STEP), int(p[1] // STEP), int(p[2] // STEP))
        if q not in self.memo:
            c:tuple = tuple((v + 0.5) * STEP for v in q)
            cl:float = math.dist(c, self.goal)
            self.memo[q] = (self._line_jumps(c, cl) if cl > self.nearest else 0.0, cl)
        base, cl = self.memo[q]

        # Blocks share a cached estimate, so correct for where p sits or every node in a block ties
        return self.final_jumps + max(0.0, base + (left - cl) * self._cell_rate(p))

    def _line_jumps(self, p:tuple, left:float) -> float:
        """Jumps to cross from p to the start of the final leg, sampling cell rates along the straight line."""
        span:float = left - self.nearest
        steps:int = max(1, math.ceil(span / STEP))
        d:tuple = tuple((self.goal[i] - p[i]) / left * span / steps for i in range(3))

        # Each sample is the midpoint of its step, so a step that straddles two cells isn't biased to either
        return sum(self._cell_rate(tuple(p[i] + d[i] * (s + 0.5) for i in range(3))) for s in range(steps)) * span / steps

    def _fly_leg(self, a:int, b:int) -> None:
        """Jumps from path node a toward b, stopping early at a refuel so the route can be replanned."""
        ship, sc, goal = self.ship, self.sc, self._node_pos(b)
        name:str = '<dest>' if b == -2 else self.neu.name(b)
        addr:int|None = None if b == -2 else self.neu.id64(b)
        stop:bool = self._stop(b)

        # From a neutron: boost straight to the next one, or land short on a scoop star when fuel is tight
        if a >= 0 or (a == -1 and self._at_neutron(self.here)):
            boost:float = self.mult * ship.jump_range(self.fuel, self.cargo) * 0.999
            gap:float = math.dist(self.here, goal)

            # Neutrons can't be scooped, so only boost straight in if enough is left to move on, or it's a fuel stop
            left:float = self.fuel - ship.fuel_cost(gap, self.fuel, self.cargo, True)
            if gap <= boost and left >= (0 if stop else self.low):
                self._jump_to(goal, name, addr, 'boost', True, stop, stop and self._short(goal, left))
                return

            # Otherwise boost onto a scoopable star instead: the one nearest the next neutron
            hits:list = [(math.dist(sc.pos(i), goal), i) for i, _ in sc.near(self.here, boost)]
            if not hits: raise Stuck('no scoopable star in boost reach')
            s:int = min(hits)[1]
            self._jump_to(sc.pos(s), sc.name(s), sc.id64(s), 'boost', True, True)
            if self.refuelled: return

        # Plain jumps for the rest of the leg, via scoopable stars
        if self.here == goal: return
        for i in self._scoop_hops(goal):
            self._jump_to(sc.pos(i), sc.name(i), sc.id64(i), 'plain', False, True)
            if self.refuelled: return
        left = self.fuel - ship.fuel_cost(math.dist(self.here, goal), self.fuel, self.cargo)
        self._jump_to(goal, name, addr, 'plain', False, stop, stop and left >= 0 and self._short(goal, left))

    def _short(self, p:tuple, fuel:float) -> bool:
        """Whether landing at p with this fuel runs low before the route's next fuel stop."""
        if not self.topup: return False

        for n in self.path[self.k + 2:]:
            q:tuple = self._node_pos(n)
            dist:float = math.dist(p, q)

            # A leg beyond one boost goes via scoopable stars, which refuel on the way
            if dist > self.mult * self.ship.jump_range(fuel, self.cargo) * 0.999: return False
            fuel -= self.ship.fuel_cost(dist, fuel, self.cargo, True)
            if fuel < (0 if self._stop(n) else self.low): return True
            if self._stop(n): return False
            p = q
        return False

    def _jump_to(self, q:tuple, name:str, addr:int|None, kind:str, charged:bool, scoopable:bool, force:bool = False) -> None:
        """Jump to q, spending fuel for the current mass, and refuel to full if it's scoopable and low or forced."""
        dist:float = math.dist(self.here, q)
        used:float = self.ship.fuel_cost(dist, self.fuel, self.cargo, charged)
        if used == math.inf: raise Stuck(f'out of fuel before {name}')
        self.fuel -= used

        topped:bool = scoopable and (force or self.fuel < self.low)
        if topped: self.fuel, self.refuelled = self.ship.tank_size, True
        self.steps.append(Step(name, kind, dist, self.fuel, topped, q, scoopable, addr))
        self.here = q

    def _scoop_hops(self, goal:tuple) -> list:
        """Fewest scoopable stops, each a plain jump apart, until goal is one jump away."""
        # A small A* over scoopable stars only; greedy "closest to goal" stalls where stars sit off the direct line
        sc, r, here = self.sc, self.plain, self.here
        at = lambda i: here if i == -1 else sc.pos(i)
        g:dict = {-1: 0}
        prev:dict = {}
        openq:list = [(0.0, math.dist(here, goal), -1)]
        done:set = set()

        # The cap stops a hopeless gap from searching the whole arm; Stuck reports it instead
        while openq and len(done) < 5000:
            _, left, i = heapq.heappop(openq)
            if i in done: continue
            done.add(i)

            # Close enough to jump straight onto the goal: walk prev back to here for the stops in between
            if left <= r:
                path:list = []
                while i != -1: path.append(i); i = prev[i]
                return path[::-1]

            # Every hop is one jump; the 1.2 weight leans toward the goal so dense regions finish quickly
            for j, _ in sc.near(at(i), r):
                if j in done or g[i] + 1 >= g.get(j, math.inf): continue
                g[j] = g[i] + 1
                prev[j] = i
                d:float = math.dist(sc.pos(j), goal)
                heapq.heappush(openq, (g[j] + 1.2 * d / r, d, j))
        raise Stuck('no scoopable path to next waypoint')
