import json
from os import path, makedirs
import re
import requests
from requests import Response
from pathlib import Path
from time import sleep

from utils.Debug import Debug, catch_exceptions

from .constants import lbls, HEADERS, HEADER_MAP, DATA_DIR, SPANSH_ROUTE, SPANSH_RESULTS
from .context import Context

class Router():
    """
    Class to manage all the route data and state information.
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        self.headers:list = []
        self.route:list = []
        self.ships:dict = {}
        self.history:list = []
        self.bodies:str = ""

        self.system:str = ""
        self.src:str = ""
        self.dest:str = ""
        self.ship_id:str = ""
        self.ship:dict = {'name': "", 'range': 0.0, 'type': "" }
        self.range:float = 32.0
        self.supercharge_mult:int = 4
        self.efficiency:int = 60
        self.offset:int = 0
        self.jumps_left:int = 0
        self.next_stop:str = ""
        self.jumps:int = 0

        self.shipyard:list = [] # Temporary store of shipyard ships

        self._load()
        self._initialized = True


    def swap_ship(self, ship_id:str) -> None:
        self.ship_id = str(ship_id)

        if ship_id in self.ships:
            self.range = self.ships[ship_id].get('range', 32.0)
            self.supercharge_mult = 6 if self.ships[ship_id].get('type', '') in ('explorer_nx') else 4
            self.ship = self.ships[ship_id]
            return

        found_ship:dict = next((item for item in self.shipyard if item.get('ship_id', '') == self.ship_id), {})
        if found_ship != {}:
            self.range = found_ship.get('max_jump_range', 32.0) * 0.95
            self.supercharge_mult = 6 if found_ship.get('type', '') in ('explorer_nx') else 4
            self.ship = {'name': found_ship.get('name', ''), 'range': self.range, 'type': found_ship.get('type', '')}
            return

        self.range = 32.0
        self.supercharge_mult = 4
        self.ship = {'name': '', 'range': 32.0, 'type': ''}
        return

    def set_ship(self, ship_id:str, range:float, name:str, type:str) -> None:
        """ Set the current ship details"""
        Debug.logger.debug(f"Setting current ship to {ship_id} {name} {type}")

        self.range = round(float(range) * 0.95, 2)
        self.supercharge_mult = 6 if type in ('explorer_nx') else 4

        self.ship['name'] = name
        self.ship['range'] = round(float(range) * 0.95, 2)
        self.ship['type'] = type

        Context.ui.set_range(self.range, self.supercharge_mult)
        self.save()


    def goto_next_waypoint(self) -> None:
        """ Move to the next waypoint """
        if self.offset < len(self.route) - 1:
            self.update_route(1)


    def goto_prev_waypoint(self) -> None:
        """ Move back to the previous waypoint"""
        if self.offset > 0:
            self.update_route(-1)


    def _syscol(self, which:str = '') -> int:
        """ Figure out which column has a chosen key, by default the system name """
        if which == '':
            for h in ['System Name', 'system']:
                if h in self.headers:
                    which = h
                    break
        if which == '' or which not in self.headers:
            return 0

        return self.headers.index(which)


    def _store_history(self) -> None:
        """ Upon route completion store src, dest and ship data """
        if self.src != '' and self.src:
            self.history.insert(0, self.src)
        if self.dest != '' and self.dest not in self.history:
            self.history.insert(0, self.dest)
        self.history = list(dict.fromkeys(self.history))[:10] # Keep only last 10 unique entries

        self.ship['range'] = self.range
        self.ship['type'] = self.ship.get('type', '')
        self.ship['name'] = self.ship.get('name', )
        Debug.logger.debug(f"Storing ship {self.ship_id} data {self.ship}")
        self.ships[self.ship_id] = self.ship
        self.save()


    @catch_exceptions
    def update_route(self, direction:int = 0) -> None:
        """
        Step forwards or backwards through the route.
        If no direction is given pickup from wherever we are on the route
        """
        if self.route == []: return
        Debug.logger.debug(f"Updating route by {direction} {self.system}")
        c:int = self._syscol()
        if direction == 0: # Figure out if we're on the route
            for i, r in enumerate(self.route):
                if r[c] == self.system:
                    Debug.logger.debug(f"Found system {self.offset} {direction}")
                    self.offset = i
                    break

            # We aren't on the route so just return
            if self.route[self.offset][c] != self.system:
                Debug.logger.debug(f"We aren't on the route")
                return
            direction = 1  # Default to moving forwards
            Debug.logger.debug(f"New offset {self.offset} {direction} {self.route[self.offset][c]}")

        # Are we at one end or the other?
        if self.offset + direction < 0 or self.offset + direction >= len(self.route):
            if direction >= 0:
                self.next_stop = lbls['route_complete']
                self.jumps_left = 0
                self.jumps = 0
                self._store_history()
            Context.ui.show_frame('Route')
            return

        Debug.logger.debug(f"Stepping to {self.offset + direction} {self.route[self.offset + direction][c]}")
        self.offset += direction
        self.next_stop = self.route[self.offset][c]
        self.jumps = self.route[self.offset][self._syscol('Jumps')] if 'Jumps' in self.headers else 0
        self.jumps_left = sum([j[self._syscol('Jumps')] for j in self.route[self.offset:]]) if 'Jumps' in self.headers else 0

        Context.ui.show_frame('Route')


    def plot_route(self, source:str, dest:str, efficiency:int, range:float, supercharge_mult:int = 4) -> bool:
        """ Plot a route by querying Spansh"""
        Debug.logger.debug(f"Plotting route")

        try:
            results:Response = requests.post(SPANSH_ROUTE + "?",
                params={"efficiency": efficiency, "range": range, "from": source, "to": dest, 'supercharge_multiplier': supercharge_mult},
                headers={'User-Agent': Context.plugin_useragent})

            if results.status_code != 202:
                self.plot_error(results)
                return False

            tries = 0
            while tries < 20:
                Debug.logger.debug(f"Checking for route results, try {tries + 1}")
                response:dict = json.loads(results.content)
                job:str = response["job"]

                results_url:str = f"{SPANSH_RESULTS}/{job}"
                route_response:Response = requests.get(results_url, timeout=5)
                if route_response.status_code != 202:
                    break
                tries += 1
                sleep(1)

            if not route_response or route_response.status_code != 200:
                self.plot_error(route_response)
                return False

            route:dict = json.loads(route_response.content)["result"]["system_jumps"]

            cols:list = []
            hdrs:list = []
            for h in HEADERS:
                if HEADER_MAP.get(h, '') in route[0].keys():
                    hdrs.append(h)
                    cols.append(HEADER_MAP.get(h, ''))
                if h == "Jumps Rem":
                    hdrs.append(h)
                    cols.append('jumps_remaining')

            Debug.logger.debug(f"Cols: {cols} hdrs: {hdrs}")
            rte:list = []
            for i, waypoint in enumerate(route):
                r:list = []
                for c in cols:
                    if c == 'jumps_remaining':
                        r.append(sum([j['jumps'] for j in route[i:]]))
                        continue
                    r.append(waypoint[c] if not re.match(r"^\d+\.(\d+)?$", str(waypoint[c])) else round(float(waypoint[c]), 2))
                rte.append(r)

            self.clear_route()
            self.headers = hdrs
            self.route = rte
            self.src = source
            self.dest = dest
            self.supercharge_mult = supercharge_mult
            self.efficiency = efficiency
            self.range = range
            self.offset = 1 if self.route[0][self._syscol()] == self.system else 0
            self.jumps_left = sum([j[cols.index('jumps')] for j in self.route]) if 'Jumps' in hdrs else 0
            self.next_stop = self.route[self.offset][self._syscol()]
            self.jumps = self.route[self.offset][cols.index('jumps')] if 'Jumps' in hdrs else 0
            self.save()
            return True

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True) # Return to the plot gui
            Context.ui.show_error(lbls["plot_error"])
        Debug.logger.debug(f"Done")
        return False


    def plot_error(self, response:Response) -> None:
        """ Parse the response from Spansh on a failed route query """

        err:str = ""
        if response and response.status_code == 400 and "error" in json.loads(response.content):
            err = json.loads(response.content)["error"]
        elif response:
            err = lbls["plot_error"]
        else:
            err = lbls["no_response"]

        Context.ui.enable_plot_gui(True)
        Context.ui.show_error(err)
        return


    def plot_edts(self, filename: Path | str) -> None:
        try:
            with open(filename, 'r') as txtfile:
                route_txt:list = txtfile.readlines()
                self.clear_route()
                for row in route_txt:
                    if row not in (None, "", []):
                        if row.lstrip().startswith('==='):
                            jumps = int(re.findall(r"\d+ jump", row)[0].rstrip(' jumps'))
                            self.jumps_left += jumps

                            system:str = row[row.find('>') + 1:]
                            if ',' in system:
                                systems:list = system.split(',')
                                for system in systems:
                                    self.route.append([system.strip(), jumps])
                                    jumps = 1
                                    self.jumps_left += jumps
                            else:
                                self.route.append([system.strip(), jumps])
        except Exception as e:
            Debug.logger.error("Failed to parse TXT route file, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True)
            Context.ui.show_error("An error occured while reading the file.")


    def clear_route(self) -> None:
        """ Clear the current route"""
        self.offset = 0
        self.headers = []
        self.route = []
        self.next_stop:str = ""
        self.jumps_left = 0
        self.save()


    @catch_exceptions
    def _load(self) -> None:
        ''' Load state from file '''
        file:str = path.join(Context.plugin_dir, DATA_DIR, 'route.json')
        if path.exists(file):
            with open(file) as json_file:
                self._from_dict(json.load(json_file))


    @catch_exceptions
    def save(self) -> None:
        ''' Save state to file '''

        ind:int = 4
        makedirs(path.join(Context.plugin_dir, DATA_DIR), exist_ok=True)
        file:str = path.join(Context.plugin_dir, DATA_DIR, 'route.json')

        with open(file, 'w') as outfile:
            json.dump(self._as_dict(), outfile, indent=ind)


    def _as_dict(self) -> dict:
        ''' Return a Dictionary representation of our data, suitable for serializing '''
        return {
            'system': self.system,
            'source': self.src,
            'destination': self.dest,
            'range': self.range,
            'efficiency': self.efficiency,
            'supercharge_mult': self.supercharge_mult,
            'offset': self.offset,
            'jumps_left': self.jumps_left,
            'next_stop': self.next_stop,
            'headers': self.headers,
            'shipid': self.ship_id,
            'ship': self.ship,
            'route': self.route,
            'ships': self.ships,
            'history': self.history
            }


    def _from_dict(self, dict:dict) -> None:
        ''' Populate our data from a Dictionary that has been deserialized '''
        self.system = dict.get('system', '')
        self.src = dict.get('source', '')
        self.dest = dict.get('destination', '')
        self.range = dict.get('range', 32.0)
        self.efficiency = dict.get('efficiency', 60)
        self.supercharge_mult = dict.get('supercharge_mult', 4)
        self.offset = dict.get('offset', 0)
        self.jumps_left = dict.get('jumps_left', 0)
        self.next_stop = dict.get('next_stop', "")
        self.headers = dict.get('headers', [])
        self.route = dict.get('route', [])
        self.ship_id = dict.get('shipid', "")
        self.ship = dict.get('ship', {})
        self.ships = dict.get('ships', {})
        self.history = dict.get('history', [])
