import json
from os import path, makedirs
import re
import requests
from requests import Response
from pathlib import Path
from time import sleep
from threading import Thread

from config import config # type: ignore
from utils.Debug import Debug, catch_exceptions

from .constants import lbls, errs, HEADERS, HEADER_MAP, DATA_DIR, SPANSH_ROUTE, SPANSH_RESULTS
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
        self.dist_remaining:int = 0
        self.next_stop:str = ""
        self.jumps:int = 0

        self.shipyard:list = [] # Temporary store of shipyard ships

        self._load()
        self._initialized = True


    def swap_ship(self, ship_id:str) -> None:
        """ Called on a ship swap event to update our current ship information """
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


    def goto_next_waypoint(self) -> None:
        """ Move to the next waypoint """
        if self.offset < len(self.route) - 1:
            self.update_route(1)


    def goto_prev_waypoint(self) -> None:
        """ Move back to the previous waypoint"""
        if self.offset > 0:
            self.update_route(-1)


    def _syscol(self, which:str = '', hdrs:list = []) -> int:
        """ Figure out which column has a chosen key, by default the system name """
        if hdrs == []:
            hdrs = self.headers

        if which == '':
            for h in ['System Name', 'system']:
                if h in hdrs:
                    which = h
                    break
        if which == '' or which not in hdrs:
            return 0

        return hdrs.index(which)


    def _store_history(self) -> None:
        """ Upon route completion store src, dest and ship data """
        if self.src != '' and self.src:
            self.history.insert(0, self.src)
        if self.dest != '' and self.dest not in self.history:
            self.history.insert(0, self.dest)
        self.history = list(dict.fromkeys(self.history))[:10] # Keep only last 10 unique entries

        if self.ship.get('name', '') != '':
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
            Context.ui.show_frame('Route', True)
            return

        Debug.logger.debug(f"Stepping to {self.offset + direction} {self.route[self.offset + direction][c]}")
        self.offset += direction
        self.next_stop = self._calc_next_stop(self.headers, self.route[self.offset])
        (self.jumps, self.jumps_left) = self._calc_jumps(self.headers, self.route[self.offset:])
        self.dist_remaining = self._calc_dist(self.headers, self.route[self.offset:])

        Context.ui.show_frame('Route')


    def plot_route(self, source:str, dest:str, efficiency:int, range:float, supercharge_mult:int = 4) -> bool:
        """ Initiate Spansh route plotting """
        thread:Thread = Thread(target=self._plotter, args=(source, dest, efficiency, range, supercharge_mult), name="Neutron Dancer route plotting worker")
        thread.start()

        return True


    def _plotter(self, source:str, dest:str, efficiency:int, range:float, supercharge_mult:int = 4) -> None:
        """ Async function to run the Spansh query """
        Debug.logger.debug(f"Plotting route")

        try:
            results:Response = requests.post(SPANSH_ROUTE + "?",
                params={"efficiency": efficiency, "range": range, "from": source, "to": dest, 'supercharge_multiplier': supercharge_mult},
                headers={'User-Agent': Context.plugin_useragent})

            if results.status_code != 202:
                self.plot_error(results)
                return

            tries = 0
            while tries < 20:
                if config.shutting_down: return # Quit
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
                return

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

            rte:list = []
            for i, waypoint in enumerate(route):
                r:list = []
                for c in cols:
                    if c == 'jumps_remaining':
                        (j, jr) = self._calc_jumps(hdrs, route[i:])
                        r.append(int(jr))
                        continue
                    if re.match(r"^(\d+)?$", str(waypoint[c])):
                        r.append(round(int(waypoint[c]), 2))
                        continue
                    if re.match(r"^\d+\.(\d+)?$", str(waypoint[c])):
                        r.append(round(float(waypoint[c]), 2))
                        continue
                    r.append(waypoint[c])

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
            self.next_stop = self.route[self.offset][self._syscol()]
            (self.jumps, self.jumps_left) = self._calc_jumps(self.headers, self.route[self.offset:])
            self.dist_remaining = self._calc_dist(self.headers, self.route[self.offset:])
            self.save()
            self.plot_finished()
            return

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True) # Return to the plot gui
            Context.ui.show_error(lbls["plot_error"])
        return


    def plot_error(self, response:Response) -> None:
        """ Parse the response from Spansh on a failed route query """

        err:str = errs["no_response"]
        if response:
            Debug.logger.info(f"Server response: {response} {response.status_code == 400} {'error' in json.loads(response.content).keys()}")
            err = errs["plot_error"]

        if response and response.status_code == 400 and "error" in json.loads(response.content).keys():
            err = json.loads(response.content)["error"]

        Context.ui.enable_plot_gui(True)
        Context.ui.show_error(err)
        return


    def plot_finished(self) -> None:
        """ Called when a plot request completes """
        Debug.logger.debug(f"Route plotted")
        Context.ui.ctc(Context.router.next_stop)
        Context.ui.show_frame('Route')


    def load_route(self) -> bool:
        """ Load a route from a CSV """
        try:
            if Context.csv == None or Context.csv.read() == False:
                Debug.logger.debug(f"Failed to load route")
                Context.ui.show_error(errs['no_filename'])
                return False

            self.clear_route()
            self.headers = Context.csv.headers
            self.route = Context.csv.route

            # Calculate jumps remaining and insert into the headers & the route
            if 'Jumps Rem' not in self.headers:
                jc:int|str = self._syscol('Jumps', self.headers)
                self.headers.insert(jc+1, 'Jumps Rem')
                for i in range(0, len(self.route)):
                    (j, jr) = self._calc_jumps(self.headers, self.route[i:])
                    self.route[i].insert(jc+1, jr)

            self.src = Context.csv.route[0][self._syscol()]
            self.dest = Context.csv.route[-1][self._syscol()]
            self.offset = 1 if self.route[0][self._syscol()] == self.system else 0
            self.next_stop = self._calc_next_stop(self.headers, self.route[self.offset])
            (self.jumps, self.jumps_left) = self._calc_jumps(self.headers, self.route[self.offset:])
            self.dist_remaining = self._calc_dist(self.headers, self.route[self.offset:])
            return True

        except Exception as e:
            Debug.logger.error("Failed to load route:", exc_info=e)
            Context.ui.show_error(errs['parse_error'])
            return False


    def plot_edts(self, filename: Path | str) -> None:
        """ Currently unused """
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
        """ Clear the current route """
        self.offset = 0
        self.headers = []
        self.route = []
        self.next_stop:str = ""
        self.jumps_left = 0


    def _calc_next_stop(self, hdrs:list, stop:list) -> str:
        """ Return the name of the next stop, system or body """
        return stop[self._syscol('Body Name' if 'Body Name' in hdrs else 'System Name', hdrs)]


    def _calc_jumps(self, hdrs:list, route:list) -> tuple:
        """ Calculate how many jumps are left in this route """
        if route == []:
            return (0, 0)

        # Identify system name and jumps columns. It may be a dict or a list so handle both.
        sc:int|str = self._syscol('System Name', hdrs) if isinstance(route[0], list) else HEADER_MAP.get('System Name', 'System Name')
        jc:int|str = self._syscol('Jumps', hdrs) if isinstance(route[0], list) else HEADER_MAP.get('Jumps', 'Jumps')

        # No jump info so treat each row as a single jump
        if 'Jumps' not in hdrs:
            return (0, len(route))

        return (
            route[0][jc], # jumps to this system
            sum([j[jc] for i, j in enumerate(route) if i == 0 or route[i-1][sc] != j[sc]]) # Jumps from this system on
            )


    def _calc_dist(self, headers, route) -> int:
        """ Calculate the distance remaining in this route """
        for val in ['Distance Remaining', 'Distance Rem']:
            if val in headers:
                return int(route[0][self._syscol(val)])
        return 0


    @catch_exceptions
    def _load(self) -> None:
        """ Load state from file """
        file:str = path.join(Context.plugin_dir, DATA_DIR, 'route.json')
        if path.exists(file):
            with open(file) as json_file:
                self._from_dict(json.load(json_file))


    @catch_exceptions
    def save(self) -> None:
        """ Save state to file """

        makedirs(path.join(Context.plugin_dir, DATA_DIR), exist_ok=True)
        file:str = path.join(Context.plugin_dir, DATA_DIR, 'route.json')

        with open(file, 'w') as outfile:
            json.dump(self._as_dict(), outfile)


    def _as_dict(self) -> dict:
        """ Return a Dictionary representation of our data, suitable for serializing """
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
        """ Populate our data from a Dictionary that has been deserialized """
        self.system = dict.get('system', '')
        self.src = dict.get('source', '')
        self.dest = dict.get('destination', '')
        self.range = dict.get('range', 32.0)
        self.efficiency = dict.get('efficiency', 60)
        self.supercharge_mult = dict.get('supercharge_mult', 4)
        self.offset = dict.get('offset', 0)
        self.jumps_left = int(dict.get('jumps_left', 0))
        self.next_stop = dict.get('next_stop', "")
        self.headers = dict.get('headers', [])
        self.route = dict.get('route', [])
        self.ship_id = dict.get('shipid', "")
        self.ship = dict.get('ship', {})
        self.ships = dict.get('ships', {})
        self.history = dict.get('history', [])
