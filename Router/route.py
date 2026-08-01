from time import time
from utils.debug import Debug
from utils.misc import hfplus
from .constants import HEADER_MAP, tts, lbls, TRUE

class Route:
    """
        Class to store, maintain, and return current route information
    """
    def __init__(self, hdrs:list = [], route:list = [], offset:int = -1) -> None:
        self.hdrs:list = hdrs
        self.route:list = route
        self.jumps:list = []
        self.offset:int = offset
        self.fleetcarrier:bool = False
        self.fuel_full = False

        self.sc:int|None = None # System column index
        self.nc:int|None = None # System / body column index
        self.jc:int|None = None # Jumps column index
        self.dc:int|None = None # Distance column index

        if hdrs == [] or route == []: return

        # Detect if this route appears to be a fleet carrier loadout (tritium column)
        self.fleetcarrier = any('tritium' in h.lower() for h in hdrs)

        self.jc:int|None = self.colind('Jumps')

        # If necessary calculate jumps or waypoints remaining and insert into the headers & the route
        if 'Jumps Rem' not in hdrs and 'Waypoints Rem' not in hdrs and self.fleetcarrier == False:
            jr:int = len(hdrs)
            if self.jc != None: jr = self.jc+1

            self.hdrs.insert(jr, 'Jumps Rem' if self.jc != None else 'Waypoints Rem')
            for i in range(0, len(route)):
                self.route[i].insert(jr, self.jumps_remaining(i))

        self.sc = self.colind(['System Name', 'system', 'name'])
        self.nc = self.colind()
        self.dc = self.colind('Distance Remaining' if 'Distance Remaining' in self.hdrs else 'Distance Rem')
        self.dn = self.colind('Distance')


    def source(self) -> str:
        if self.route == []: return ''
        return self.route[0][self.nc]


    def destination(self) -> str:
        if self.route == []: return ''
        return self.route[-1][self.nc]


    def next_system(self) -> str:
        """ Return systen name of next waypoint """
        if self.route == []: return ''
        if self.offset >= len(self.route)-1: return lbls['route_complete']
        return self.route[self.offset+1][self.sc]

    def next_stop(self) -> str:
        """ Return system name or body name of the next waypoint """
        if self.route == []: return ''
        if self.offset >= len(self.route)-1: return lbls['route_complete']
        return self.route[self.offset+1][self.nc]


    def next_stop_value(self, header:str) -> str|None:
        """ Return the next waypoint's value for a given header """
        if self.route == [] or self.offset >= len(self.route)-1: return None
        ind:int|None = self.colind(header)
        if ind is None: return None
        return self.route[self.offset+1][ind]


    def sum_value(self, header:str) -> float:
        """ Sum a numeric column across all waypoints through the next stop """
        ind:int|None = self.colind(header)
        if ind is None or self.route == []: return 0
        return sum(r[ind] for r in self.route[:self.offset+2] if isinstance(r[ind], (int, float)))


    def next_stop_detail(self) -> str:
        """ Return a short secondary detail for the next waypoint(station, genus, etc.) """
        station = self.next_stop_value('Station Name')
        if station: return str(station)

        return ''


    def next_stop_detail_lines(self) -> list[str]:
        """ Extra per-route-type detail for the next waypoint, one entry per line """
        lines:list = []

        commodity = self.next_stop_value('Commodity')
        amount:str = hfplus(tuple([self.next_stop_value('Amount'), 'int', '', 't']))
        if commodity:
            profit:str = hfplus(tuple([self.next_stop_value('Profit'), 'int', '', ' Cr/t']))
            lines.append(f"{amount + ' ' if amount else ''}{commodity} · {profit}")

            cum_profit:str = hfplus(tuple([self.sum_value('Profit'), 'float', '', ' Cr']))
            perhour:str = hfplus(tuple([self.credits_per_hour('Profit'), 'float', 'N/A', ' Cr/hr']))
            lines.append(f"{cum_profit} · ({perhour})")


        subtype = self.next_stop_value('Body Subtype')
        if subtype:
            dist:str = hfplus(tuple([self.next_stop_value('Distance To Arrival'), 'float', '', ' ls']))
            lines.append(" · ".join(p for p in [subtype, dist] if p))

        species = self.next_stop_value('Species')
        if species:
            landmark:str = hfplus(tuple([self.next_stop_value('Landmark Value'), 'float', '', ' Cr']))
            lines.append(f"{species}{f' · {landmark}' if landmark else ''}")

            cum_landmark:str = hfplus(tuple([self.sum_value('Landmark Value'), 'float', '', ' Cr']))
            perhour:str = hfplus(tuple([self.credits_per_hour('Landmark Value'), 'float', 'N/A', ' Cr/hr']))
            lines.append(f"{cum_landmark} · ({perhour})")

        scanval = self.next_stop_value('Estimated Scan Value')
        mapval = self.next_stop_value('Estimated Mapping Value')
        if not species and (scanval or mapval):
            scan:str = hfplus(tuple([scanval, 'float', '', ' Cr']))
            mapping:str = hfplus(tuple([mapval, 'float', '', ' Cr']))
            lines.append(" · ".join(f"{n}: {v}" for n, v in [('Scan', scan), ('Mapping', mapping)] if v))

            cum_scan:str = hfplus(tuple([self.sum_value('Estimated Scan Value'), 'float', '', ' Cr']))
            if cum_scan:
                perhour:str = hfplus(tuple([self.credits_per_hour('Estimated Scan Value'), 'float', 'N/A', ' Cr/hr']))
                lines.append(f"{cum_scan} · ({perhour})")

        return lines


    def tracks_refuel_or_neutron(self) -> bool:
        """ Whether this route has Refuel/Restock/Neutron columns -- column presence,
        not route-type name, so CSV imports are handled correctly too. """
        return (self.colind('Refuel') is not None or self.colind('Restock') is not None
                or self.colind('Neutron') is not None or self.colind('Neutron Star') is not None)


    def jumps_to_refuel(self) -> int|None:
        """ Returns how many jumps until the next fuel stop. Returns None if no fuel stops. """
        if self.route == [] or self.offset >= len(self.route): return None

        ind:int|None = self.colind("Refuel") or self.colind("Restock")
        if ind == None: return None
        if self.route[self.offset][ind] in TRUE: return 0

        waypoint_range:list = self.route[self.offset:len(self.route)]
        return next((i for i, wp in enumerate(waypoint_range) if wp[ind] in TRUE), None)


    def dist_to_refuel(self) -> int|None:
        """ Returns distance to the next fuel stop. Returns None if no fuel stops. """
        if self.route == [] or self.offset >= len(self.route) or self.dc == None: return None

        ind:int|None = self.colind("Refuel") or self.colind("Restock")
        if ind == None: return None
        if self.route[self.offset][ind] in TRUE: return 0
        refind:int|None = next((i for i, wp in enumerate(self.route[self.offset:len(self.route)]) if wp[ind] in TRUE), None)
        return self.route[self.offset][self.dc] - self.route[self.offset+refind][self.dc] if refind is not None else None


    def refuel(self) -> bool:
        """ Return whether we need to refuel at this waypoint """
        if self.fuel_full == True: return False
        ind:int|None = self.colind('Refuel') or self.colind('Restock')
        if ind == None: return False
        return self.route[self.offset][ind] in TRUE


    def is_neutron(self) -> bool:
        """ Return whether we need to neutron boost at this waypoint """
        ind:int|None = self.colind('Neutron') or self.colind('Neutron Star')

        if ind == None or self.offset+1 >= len(self.route): return False
        return self.route[self.offset+1][ind] in TRUE


    def jumps_to_wp(self) -> int:
        """ Return the number of jumps to the next waypoint """
        if self.route == [] or self.jc == None: return 0
        if self.offset+1 >= len(self.route): return 0
        return self.route[self.offset+1][self.jc]


    def total_jumps(self) -> int:
        """ Jumps remaining from start of route """
        return self.jumps_remaining(0)


    def jumps_remaining(self, offset:int|None = None) -> int:
        """ Jumps remaining from this point. Either just rows left or sum of jumps column """
        if self.route == []: return 0
        if offset == None: offset = max(0, self.offset)
        if offset+1 >= len(self.route): return 0

        # No jump count column
        j = len(self.route[offset:])-1
        if self.jc == None: return len(self.route[offset:])-1
        return sum([j[self.jc] for j in self.route[offset+1:]])


    def perc_jumps_rem(self, offset:int|None = None) -> float:
        """ Percentage of jumps remaining """
        if self.route == []: return 0
        return (self.total_jumps() - self.jumps_remaining(offset)) * 100 / self.total_jumps()


    def dist_to_next(self) -> int:
        """ Return the distance to the next waypoint """
        if self.route == []: return 0
        if self.offset+1 >= len(self.route): return 0
        if self.dn:
            return self.route[self.offset+1][self.dn]
        if self.offset >= 0 and self.dc:
            return self.route[self.offset][self.dc]- self.route[self.offset+1][self.dc]
        return 0


    def dist_to_prev(self) -> int:
        """ Return the distance to the previous waypoint """
        if self.route == [] or self.dn == None: return 0
        if self.offset+1 >= len(self.route): return 0
        return self.route[self.offset][self.dn]


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

    def credits_per_hour(self, header:str) -> float:
        """ Credits per hour on this route """
        if self.jumps == []: return 0
        i:int|None = self.colind(header)
        if i is None or self.route == []: return 0

        td:float = (int(self.jumps[-1][0]) - int(self.jumps[0][0])) / 3600
        return self.sum_value(header) / td if td > 0 else 0

    def dist_remaining(self, offset:int|None = None) -> int:
        """ Distance remaining if we know it """
        if self.route == [] or self.dc == None: return 0
        if offset == None: offset = max(0, self.offset)
        return self.route[offset][self.dc]


    def perc_dist_rem(self, offset:int|None = None) -> float:
        """ Percentage of distance remaining """
        if self.route == [] or self.total_dist() == 0: return 0
        return (self.total_dist() - self.dist_remaining(offset)) * 100 / self.total_dist()


    def colind(self, which:str|list = '') -> int|None:
        """ Return the index of a given column, by default the system name column """
        if self.hdrs == []: return None

        if which == '':
            for h in ['Body Name', 'body', 'System Name', 'system', 'name']:
                if h in self.hdrs:
                    Debug.logger.debug(f"{h} {self.hdrs.index(h)}")
                    return self.hdrs.index(h)
            return 0
        if isinstance(which, str): which = [which]
        for w in which:
            if w in self.hdrs or w.lower() in self.hdrs:
                return self.hdrs.index(w)

            if w in HEADER_MAP.keys() and HEADER_MAP[w] in self.hdrs:
                return self.hdrs.index(HEADER_MAP[w])
        return None


    def get_waypoint(self, inc:int = 0) -> str:
        """ Return the system of a waypoint relative to our current offset, used to get the next waypoint or the previous waypoint."""
        inc += 1 # Offset is our current location, but waypoint needs to show the next not the current
        if self.route == [] or self.offset + inc >= len(self.route) or self.offset+inc < 0: return tts["none"]

        return self.route[self.offset+inc][self.nc]


    def update_route(self, direction:int = 0, system:str = '') -> int:
        """
        Step forwards or backwards through the route.
        If no direction is given pickup from wherever we are on the route
        """
        if self.route == []: return -1

        if direction == 0: # Figure out if we're on the route
            self.offset = -1
            for i, r in enumerate(self.route):
                if r[self.nc] == system:
                    self.offset = i
                    break

            # We aren't on the route so just return
            if self.offset == -1:
                Debug.logger.debug(f"We aren't on the route")
                return -1
            Debug.logger.debug(f"New offset {self.offset} {direction} {self.route[self.offset][self.nc]}")

        # Are we at one end or the other?
        if self.offset + direction < 0:
            self.offset = -1
            return self.offset

        if self.offset + direction >= len(self.route):
            self.offset = len(self.route)-1
            return self.offset

        self.offset += direction
        return self.offset


    def record_jump(self, dest:str, dist:float) -> None:
        """ Add details of an FSD jump """
        self.jumps.append([time(), dest, dist])


    def __repr__(self) -> str:
        if self.route == []: return "No route"
        return f"{self.route[0][self.nc]} to {self.route[-1][self.nc]}"


    def __str__(self) -> str:
        return self.__repr__()


    def to_dict(self) -> list:
        return [self.hdrs, self.route, self.offset]
