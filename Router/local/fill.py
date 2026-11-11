"""Turn a coarse neutron route into real jumps, tracking fuel and adding scoop stops."""
import heapq, math
from dataclasses import dataclass

from ..ship import Ship
from .index import Index

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

class Stuck(Exception):
    """The fill-in cannot continue from here."""

def fill(ship:Ship, neu:Index, sc:Index, path:list, src:tuple, dest:tuple, fuel:float, cargo:float = 0) -> list[Step]:
    """Real jumps along a coarse neutron path, refuelling on scoopable stars."""
    # Path nodes follow Planner's convention: neutron indexes, plus -1 for the source and -2 for the destination
    pos = lambda n: src if n == -1 else dest if n == -2 else neu.pos(n)
    label = lambda n: '<src>' if n == -1 else '<dest>' if n == -2 else neu.name(n)
    keep:float = ship.max_fuel_per_jump  # always able to make one more full jump to reach a scoopable star
    steps:list[Step] = []
    here:tuple = src

    def hops(r:float, goal:tuple) -> list:
        """Fewest scoopable stops, each within r, until goal is one jump away."""
        # A small A* over scoopable stars only; greedy "closest to goal" stalls where stars sit off the direct line
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

    def land(q:tuple, nm:str, kind:str, charged:bool, scoopable:bool) -> None:
        nonlocal here, fuel
        dist:float = math.dist(here, q)

        # Fuel use depends on current mass, so it's worked out per jump from the fuel actually aboard
        used:float = ship.fuel_cost(dist, fuel, cargo, charged)
        if used == math.inf: raise Stuck(f'out of fuel before {nm}')
        fuel -= used

        # Scooping takes time, so only stop to refuel once the tank is below half, then fill it
        topped:bool = scoopable and fuel < ship.tank_size / 2
        if topped: fuel = ship.tank_size
        steps.append(Step(nm, kind, dist, fuel, topped, q, scoopable))
        here = q

    try:
        for a, b in zip(path, path[1:]):
            goal:tuple = pos(b)

            # From a neutron: boost straight to the next one, or land short on a scoop star when fuel is tight
            if a >= 0:
                # 0.999 keeps a jump that is exactly at the limit from failing on floating-point rounding
                boost:float = ship.supercharge_multiplier * ship.jump_range(fuel, cargo) * 0.999
                gap:float = math.dist(here, goal)

                # Neutrons can't be scooped, so only boost straight in if the fuel left still covers a full jump
                if gap <= boost and fuel - ship.fuel_cost(gap, fuel, cargo, True) >= keep:
                    land(goal, label(b), 'boost', True, False)
                    continue

                # Otherwise boost onto a scoopable star instead: the one nearest the next neutron.
                # If that neutron was in reach, the star must be a plain jump from it, so one hop finishes the leg.
                within:float = ship.jump_range(ship.tank_size, cargo) * 0.999 if gap <= boost else math.inf
                hits:list = [(d, i) for i, _ in sc.near(here, boost) if (d := math.dist(sc.pos(i), goal)) <= within]
                if not hits: raise Stuck('no scoopable star in boost reach')
                hit:tuple = min(hits)
                land(sc.pos(hit[1]), sc.name(hit[1]), 'boost', True, True)

            # Plain jumps for the rest of the leg. Range is planned at a full tank, the heaviest the ship gets,
            # so every hop stays reachable whatever fuel is aboard after scooping.
            if here == goal: continue
            for i in hops(ship.jump_range(ship.tank_size, cargo) * 0.999, goal):
                land(sc.pos(i), sc.name(i), 'plain', False, True)
            land(goal, label(b), 'plain', False, False)

    # A failure ends the route but keeps the jumps so far, so the caller can show where it got stuck
    except Stuck as e:
        steps.append(Step(str(e), 'fail', 0.0, fuel))

    return steps
