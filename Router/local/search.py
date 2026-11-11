"""Coarse neutron-boosted route search over a neutron index."""
import heapq, math

from .index import Index

COARSE:int = 10      # 100 Ly cells per density-map cell edge
STEP:float = 250.0   # sampling step along the line to the destination
WEIGHTS:tuple = (1.15, 1.3, 1.6, 2.0)

class Planner:
    """Fewest-jump neutron routes, guided by a coarse map of neutron density."""

    @staticmethod
    def jumps(dist:float, rng:float, mult:float, boosted:bool) -> int:
        """Jumps for a leg: one boosted jump then plain jumps, or plain jumps only."""
        if not boosted: return math.ceil(dist / rng)
        return 1 + math.ceil(max(0.0, dist - mult * rng) / rng)

    def __init__(self, neu:Index) -> None:
        self.neu:Index = neu
        self.counts:dict = {}
        for j, k in enumerate(neu.ukeys):
            c:tuple = (((k >> 22) - 1024) // COARSE, (((k >> 11) & 2047) - 1024) // COARSE, ((k & 2047) - 1024) // COARSE)
            self.counts[c] = self.counts.get(c, 0) + neu.starts[j + 1] - neu.starts[j]

    def route(self, src:tuple, dest:tuple, rng:float, mult:float = 4.0, budget:int = 3000) -> tuple:
        """Shorter of the flat and density-guided routes, as (path of neutron indices, jumps)."""
        found:list = []
        for dense in (False, True):
            for w in WEIGHTS:
                res:tuple|None = self._plot(src, dest, rng, mult, w, budget, dense)
                if res: break
            else:
                res = self._plot(src, dest, rng, mult, WEIGHTS[-1] * 2, 0, dense)
            if res: found.append(res)
        return min(found, key=lambda r: r[1])

    def _plot(self, src:tuple, dest:tuple, rng:float, mult:float, w:float, limit:int, dense:bool) -> tuple|None:
        """Weighted A* from src to dest; None if it expands more than limit nodes."""
        # Nodes are neutron indexes, plus -1 for the source and -2 for the destination, neither of which is in the index
        neu:Index = self.neu
        pos = lambda n: src if n == -1 else dest if n == -2 else neu.pos(n)
        boost:float = mult * rng  # longest supercharged jump

        # The final leg must start at a neutron, and the closest one to the destination is `nearest` Ly out.
        # Probe outward from the destination, doubling the radius, until a neutron turns up.
        probe:float = boost
        while not (ring := neu.near(dest, probe)) and probe < 8000: probe *= 2
        nearest:float = min((dm for _, dm in ring), default=0.0)

        # No route can finish in fewer jumps than that final leg, so it seeds every estimate
        final_jumps:int = self.jumps(nearest, rng, mult, True) if ring else 0

        # The flat estimate assumes every jump left is a full boost; the density one knows where neutrons are sparse
        flat = lambda p, left: final_jumps + max(0.0, left - nearest) / boost
        est = self._estimator(dest, rng, mult, nearest, final_jumps) if dense else flat

        # g: fewest jumps found to each node; prev: the node it came from, to rebuild the path
        g:dict = {-1: 0}
        prev:dict = {}

        # Queue entries are (priority, distance left, node); distance left breaks ties toward nodes nearer the goal
        openq:list = [(0.0, math.dist(src, dest), -1)]
        done:set = set()

        while openq:
            _, _, n = heapq.heappop(openq)

            # A node can be queued several times as better costs are found; only its first pop counts
            if n in done: continue
            if n == -2: break
            done.add(n)

            # Over budget means this weight is too careful for the region; route() retries with a greedier one
            if limit and len(done) > limit: return None

            # Only a jump leaving a neutron is supercharged, so the source's first leg is plain jumps only
            p:tuple = pos(n)
            here:float = math.dist(p, dest)
            boosted:bool = n >= 0

            # Start by looking one boosted jump plus one plain jump out, and only at neutrons that get closer
            rad:float = boost + rng if boosted else max(boost, 2 * rng)
            ahead = lambda rr: [(m, dm, left) for m, dm in neu.near(p, rr)
                                if m not in done and (left := math.dist(neu.pos(m), dest)) < here]

            # Sparse regions need a wider net, or the search dead-ends without trying a longer plain-jump leg
            cands:list = ahead(rad)
            while len(cands) < 3 and rad < 4000:
                rad *= 1.5
                cands = ahead(rad)

            # Dense regions offer thousands; keep the 40 that cover the most distance per jump
            cands = heapq.nlargest(40, cands, key=lambda c: (here - c[2]) / self.jumps(c[1], rng, mult, boosted))

            # Always offer flying straight to the destination, so a route exists even with no neutrons ahead
            cands.append((-2, here, 0.0))

            for m, dm, left in cands:
                cost:int = g[n] + self.jumps(dm, rng, mult, boosted)
                if cost >= g.get(m, 1 << 30): continue
                g[m] = cost
                prev[m] = n

                # Priority is jumps so far plus w times the estimate; w > 1 trades a few jumps for a much faster search
                heapq.heappush(openq, (cost + (w * est(pos(m), left) if m != -2 else 0), left, m))

        if -2 not in prev: return None
        path:list = [-2]
        while path[-1] != -1: path.append(prev[path[-1]])
        return path[::-1], g[-2]

    def _estimator(self, dest:tuple, rng:float, mult:float, nearest:float, final_jumps:int):
        """Jumps-to-go estimate: per-cell jump rates integrated along the line to dest, plus the final leg."""
        boost:float = mult * rng  # longest supercharged jump
        size:float = 100.0 * COARSE  # density cell edge in Ly
        rates:dict = {}

        # Turn each density cell's neutron count into jumps per Ly at this range.
        # n neutrons spread evenly through a 1000 Ly cube sit about gap = cube root of (volume / n) apart.
        # One boosted jump covers min(gap, boost) at best; any gap beyond boost has to be crossed in plain jumps.
        for c, n in self.counts.items():
            gap:float = (1e9 / n) ** (1 / 3)
            rates[c] = (1 + max(0.0, gap - boost) / rng) / max(gap, boost)

        # A cell with no neutrons at all means plain jumps all the way through it
        rate = lambda p: rates.get((int(p[0] // size), int(p[1] // size), int(p[2] // size)), 1 / rng)
        memo:dict = {}

        def line(p:tuple, left:float) -> float:
            """Jumps to cross from p to the start of the final leg, sampling cell rates along the straight line."""
            span:float = left - nearest
            steps:int = max(1, math.ceil(span / STEP))
            d:tuple = tuple((dest[i] - p[i]) / left * span / steps for i in range(3))

            # Each sample is the midpoint of its step, so a step that straddles two cells isn't biased to either
            return sum(rate(tuple(p[i] + d[i] * (s + 0.5) for i in range(3))) for s in range(steps)) * span / steps

        def est(p:tuple, left:float) -> float:
            # Already inside the final leg's radius: only that leg remains
            if left <= nearest: return float(final_jumps)

            # Integrating the line is the costly part, and the search asks for it on every queued node.
            # Nodes in the same STEP-sized block share one integral, taken from the block's centre.
            q:tuple = (int(p[0] // STEP), int(p[1] // STEP), int(p[2] // STEP))
            if q not in memo:
                c:tuple = tuple((v + 0.5) * STEP for v in q)
                cl:float = math.dist(c, dest)
                memo[q] = (line(c, cl) if cl > nearest else 0.0, cl)
            base, cl = memo[q]

            # Blocks share a cached estimate, so correct for where p sits or every node in a block ties
            return final_jumps + max(0.0, base + (left - cl) * rate(p))

        return est
