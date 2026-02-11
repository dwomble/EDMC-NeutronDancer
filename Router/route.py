from time import time
from utils.debug import Debug
from .constants import HEADER_MAP, tts

class Route:
    """
        Class to store, maintain, and return current route information
    """
    def __init__(self, hdrs:list = [], cols:list = [], offset:int = 0, jumps:list = []) -> None:
        self.hdrs:list = hdrs
        self.route:list = cols
        self.jumps:list = jumps
        self.offset:int = offset
        self.fleetcarrier:bool = False

        if hdrs == [] or cols == []: return

        # Detect if this route appears to be a fleet carrier loadout (tritium column)
        self.fleetcarrier = any('tritium' in h.lower() for h in hdrs)

        self.sc:int|None = self.colind()
        self.jc:int|None = self.colind('Jumps')
        self.dc:int|None = self.colind('Distance Remaining' if 'Distance remaining' in self.hdrs else 'Distance Rem')

        # If necessary calculate jumps or waypoints remaining and insert into the headers & the route
        if 'Jumps Rem' not in hdrs and 'Waypoints Rem' not in hdrs and self.fleetcarrier == False:
            jr:int = len(hdrs)
            if self.jc != None: jr = self.jc+1

            self.hdrs.insert(jr, 'Jumps Rem' if self.jc != None else 'Waypoints Rem')
            for i in range(0, len(cols)):
                self.route[i].insert(jr, self.jumps_remaining(i))

            # Recalc, they may have moved.
            self.sc:int|None = self.colind()
            self.dc:int|None = self.colind('Distance Remaining' if 'Distance remaining' in self.hdrs else 'Distance Rem')

    def source(self) -> str:
        if self.route == []: return ''
        return self.route[0][self.sc]


    def destination(self) -> str:
        if self.route == []: return ''
        return self.route[-1][self.sc]


    def jumps_to_system(self, offset:int|None = None) -> int:
        """ How many jumps to reach this system? """
        if self.route == []: return -1
        if offset == None: offset = self.offset
        if offset >= len(self.route) or self.jc == None: return -1
        return self.route[offset][self.jc]


    def next_stop(self) -> str:
        """ Return system name or body name of the next waypoint """
        if self.route == []: return ''
        Debug.logger.debug(f"Next stop: {self.sc} {self.route[self.offset][self.sc]}")
        return self.route[self.offset][self.sc]


    def jumps_to_wp(self) -> int:
        """ Return the number of jumps to the next waypoint """
        if self.route == [] or self.jc == None: return 0
        return self.route[self.offset][self.jc]


    def total_jumps(self) -> int:
        """ Jumps remaining from start of route """
        return self.jumps_remaining(0)


    def jumps_remaining(self, offset:int|None = None) -> int:
        """ Jumps remaining from this point. Either just rows left or sum of jumps column """
        if self.route == []: return -1
        if offset == None: offset = self.offset
        if offset >= len(self.route)-1: return 0

        # No jump count column
        if self.jc == None: return len(self.route[offset:])
        return sum([j[self.jc] for i, j in enumerate(self.route[offset:]) if i == 0 or self.route[i-1][self.sc] != j[self.sc]])


    def perc_jumps_rem(self, offset:int|None = None) -> float:
        """ Percentage of jumps remaining """
        if self.route == []: return 0
        return (self.total_jumps() - self.jumps_remaining()) * 100 / self.total_jumps()


    def total_dist(self) -> int:
        """ Total distance of the route """
        return self.dist_remaining(0)


    def jumps_per_hour(self) -> float:
        """ Jumps per hour on this route """
        if self.jumps == []: return 0
        td:float = (int(self.jumps[-1][0]) - int(self.jumps[0][0])) / 3600
        return len(self.jumps) / td if td > 0 else 0


    def dist_per_hour(self) -> float:
        """ Ly per hour on this route """
        if self.jumps == []: return 0
        td:float = (int(self.jumps[-1][0]) - int(self.jumps[0][0])) / 3600
        return sum([j[2] for j in self.jumps]) / td if td > 0 else 0


    def dist_remaining(self, offset:int|None = None) -> int:
        """ Distance remaining if we know it """
        if self.route == [] or self.dc == None: return 0
        if offset == None: offset = self.offset
        return self.route[offset][self.dc]


    def perc_dist_rem(self, offset:int|None = None) -> float:
        """ Percentage of distance remaining """
        if self.route == [] or self.total_dist() == 0: return 0
        return (self.total_dist() - self.dist_remaining(offset)) * 100 / self.total_dist()


    def colind(self, which:str = '') -> int|None:
        """ Return the index of a given column, by default the system name column """
        if self.hdrs == []: return None

        Debug.logger.debug(f"{self.hdrs}")
        if which == '':
            for h in ['Body Name', 'body', 'System Name', 'system', 'name']:
                if h in self.hdrs:
                    Debug.logger.debug(f"{h} {self.hdrs.index(h)}")
                    return self.hdrs.index(h)
            return 0

        for w in [which, which.lower()]:
            if w in self.hdrs:
                return self.hdrs.index(w)

            if w in HEADER_MAP.keys() and HEADER_MAP[w] in self.hdrs:
                return self.hdrs.index(HEADER_MAP[w])
        return None


    def get_waypoint(self, inc:int = 0) -> str:
        """ Return the system of a waypoint relative to our current offset """
        if self.route == [] or self.offset + inc > len(self.route)-1 or self.offset+inc < 0: return tts["none"]

        return self.route[self.offset+inc][self.sc]


    def refuel(self) -> bool:
        """ Return whether we need to refuel at this waypoint """
        ind:int|None = self.colind('Refuel') or self.colind('Restock')
        if ind == None: return False
        return self.route[self.offset][ind] in [True, 'True', 'true', 'YES', 'Yes', 'yes', 1, '1']


    def update_route(self, direction:int = 0, system:str = '') -> int:
        """
        Step forwards or backwards through the route.
        If no direction is given pickup from wherever we are on the route
        """
        if self.route == []: return -1

        if direction == 0: # Figure out if we're on the route
            for i, r in enumerate(self.route):
                if r[self.sc] == system:
                    self.offset = i
                    break

            # We aren't on the route so just return
            if self.route[self.offset][self.sc] != system:
                Debug.logger.debug(f"We aren't on the route")
                return -1
            direction = 1  # Default to moving forwards
            Debug.logger.debug(f"New offset {self.offset} {direction} {self.route[self.offset][self.sc]}")

        # Are we at one end or the other?
        if self.offset + direction < 0:
            return 0

        if self.offset + direction >= len(self.route):
            return self.offset

        self.offset += direction
        return self.offset


    def record_jump(self, dest:str, dist:float) -> None:
        """ Add details of an FSD jump """
        Debug.logger.debug(f"Jump added")
        self.jumps.append([time(), dest, dist])


    def __repr__(self) -> str:
        if self.route == []: return "No route"
        return f"{self.route[0][self.sc]} to {self.route[-1][self.sc]}"

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self) -> list:
        return [self.hdrs, self.route, self.offset, self.jumps]
