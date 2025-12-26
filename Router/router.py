import json
import re
import requests
from requests import Response
from pathlib import Path
from time import time, sleep
from threading import Thread

from config import config # type: ignore
from utils.Debug import Debug, catch_exceptions

from .constants import lbls, errs, HEADERS, HEADER_MAP, DATA_DIR, SPANSH_ROUTE, SPANSH_GALAXY_ROUTE, SPANSH_RESULTS
from .context import Context
from .ship import Ship

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
        self.used_ships:list = []
        self.ships:dict[str, Ship] = {}
        self.history:list = []

        # Current route data
        self.system:str = ""
        self.src:str = ""
        self.dest:str = ""
        self.ship_id:str = ""
        self.ship:Ship|None = None
        self.range:float = 32.0
        self.supercharge_mult:int = 4
        self.efficiency:int = 60
        self.offset:int = 0
        self.jumps_left:int = 0
        self.dist_remaining:int = 0
        self.next_stop:str = ""
        self.jumps:int = 0

        self._load()
        self._initialized = True


    def swap_ship(self, ship_id:str) -> None:
        """ Called on a ship swap event to update our current ship information """
        if ship_id not in self.ships.keys():
            Debug.logger.debug(f"ShipID {ship_id} not found in shipyard")
            self.ship_id = ""
            self.ship = None
            return

        self.ship_id = str(ship_id)

        self.range = self.ships[ship_id].range
        self.supercharge_mult = self.ships[ship_id].supercharge_mult
        self.ship = self.ships[ship_id]


    def set_ship(self, entry:dict) -> None:
        """ Set the current ship details and update the UI """
        Debug.logger.debug(f"Setting current ship to {entry.get('ShipID', '')} {entry.get('ShipName', '')} {entry.get('Ship', '')}")
        ship:Ship = Ship(entry)
        self.ship = ship
        self.ship_id = str(ship.id)
        self.supercharge_mult = ship.supercharge_mult
        self.range = ship.range
        self.ships[self.ship_id] = ship

        Context.ui.set_range(self.range, self.supercharge_mult)


    def goto_next_waypoint(self) -> None:
        """ Move to the next waypoint """
        if self.offset < len(self.route) - 1: self.update_route(1)


    def goto_prev_waypoint(self) -> None:
        """ Move back to the previous waypoint """
        if self.offset > 0: self.update_route(-1)


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

        if self.ship_id == None or self.ship == None:
            Debug.logger.debug(f"No ship to store")
            return

        self.ship.range = self.range
        self.ship.supercharge_mult = self.supercharge_mult
        if self.ship_id not in self.used_ships:
            self.used_ships.append(self.ship_id)
        Debug.logger.debug(f"Storing ship {str(self.ship)}")


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


#    def _get_sysid(self, sys:str) -> str:
#        url = "https://spansh.co.uk/api/systems/field_values/system_names?"
#        results:requests.Response = requests.get(url, params={'q': sys}, headers={'User-Agent': Context.plugin_useragent}, timeout=3)
#        res:dict = json.loads(results.content)
#        if 'min_max' not in res or len(res['min_max']) < 1:
#            return ""
#        return res['min_max'][0]['id64']


    def plot_route(self, which:str, params:dict) -> bool:
        """ Initiate Spansh route plotting """
        match which:
            case 'neutron':
                url = SPANSH_ROUTE
            case 'galaxy':
                url = SPANSH_GALAXY_ROUTE

        Debug.logger.debug(f"parameters: {params}")
        thread:Thread = Thread(target=self._plotter, args=(url, params), name="Neutron Dancer route plotting worker")
        thread.start()

        return True


    @catch_exceptions
    def _plotter(self, url:str, params:dict) -> None:
        """ Async function to run the Spansh query """
        Debug.logger.debug(f"Plotting route")

        try:
            limit:int = int(params.get('max_time', 20))
            results:Response = requests.post(url, data=params, headers={'User-Agent': Context.plugin_useragent,
                                                                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

            if results.status_code != 202:
                self.plot_error(results)
                return

            tries = 0
            while tries < limit:
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

            #Debug.logger.debug(f"{route_response.json()}")
            res = json.loads(route_response.content)["result"]

            route = res.get('jumps', res.get('system_jumps', []))

            cols:list = []
            hdrs:list = []
            h:str
            for h in HEADERS:
                k:str
                for k in route[0].keys():
                    if HEADER_MAP.get(k, '') == h:
                        hdrs.append(h)
                        cols.append(k)
                    continue
                if h == "Jumps Rem":
                    hdrs.append(h)
                    cols.append('jumps_remaining')

            Debug.logger.debug(f"hdrs: {hdrs} cols: {cols}")
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
            self.offset = 1 if self.route[0][self._syscol()] == self.system else 0
            self.next_stop = self.route[self.offset][self._syscol()]
            (self.jumps, self.jumps_left) = self._calc_jumps(self.headers, self.route[self.offset:])
            self.dist_remaining = self._calc_dist(self.headers, self.route[self.offset:])
            Debug.logger.debug(f"{self.headers} {self.route}")
            self.save()
            self.plot_finished()
            return

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True) # Return to the plot gui
            Context.ui.show_error(lbls["plot_error"])
        return


    @catch_exceptions
    def plot_error(self, response:Response) -> None:
        """ Parse the response from Spansh on a failed route query """

        Debug.logger.debug(f"Result: {response}")
        err:str = errs["no_response"]
        #if response:
        #    Debug.logger.info(f"Server response: {response.json()}")
        #    err = errs["plot_error"]

        if response.status_code == 400 and "error" in json.loads(response.content).keys():
            Debug.logger.info(f"Server response: {response.json()}")
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


    def _get_module_data(self) -> None:
        """ Download module data from Coriolis """
        try:
            Debug.logger.debug(f"Getting module data")
            modules:list = []
            for key, url  in {"fsd": "https://raw.githubusercontent.com/EDCD/coriolis-data/master/modules/standard/frame_shift_drive.json",
                              "gfsb": "https://raw.githubusercontent.com/EDCD/coriolis-data/master/modules/internal/guardian_fsd_booster.json",
                              "ft": "https://raw.githubusercontent.com/EDCD/coriolis-data/master/modules/standard/fuel_tank.json"}.items():
                r:Response = requests.get(url, timeout=10)
                if r.status_code != 200:
                    Debug.logger.info(f"Could not download FSD data (status code {r.status_code}): {r.text}")
                    return

                data:dict = json.loads(r.content)
                if data.get(key, []) == []:
                    Debug.logger.error(f"No {key} found {json.loads(r.content)} {r.content}")
                    return
                modules = modules + data.get(key, [])

            Context.modules = modules

            # Temporary hack since Coriolis doens't yet have the new MkII overcharge boosters
            Context.modules.append({
                "class": 8,
                "cost": 82042060,
                "fuelmul": 0.011,
                "fuelpower": 2.505,
                "mass": 160,
                "maxfuel": 6.8,
                "optmass": 4670,
                "power": 1.15,
                "rating": "A",
                "symbol": "Int_Hyperdrive_Overcharge_Size8_Class5_Overchargebooster_MkII",
            })

            Debug.logger.debug(f"Downloaded {len(Context.modules)} FSD entries from Coriolis")
            file:Path = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'

            with open(file, 'w') as outfile:
                json.dump(Context.modules, outfile)

        except Exception as e:
            Debug.logger.error("Failed to download FSD data, exception info:", exc_info=e)


    @catch_exceptions
    def _load(self) -> None:
        """ Load state from files """
        Debug.logger.debug(f"Loading modules")
        # Get the FSD data from Coriolis' github repo
        file = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'
        if file.exists():
            with open(file) as json_file:
                Context.modules = json.load(json_file)
                Debug.logger.debug(f"Loaded {len(Context.modules)} modules from local file")
        Debug.logger.debug(f"Total modules: {len(Context.modules)}")

        if not file.exists() or file.stat().st_mtime < time() - 86400:
            Debug.logger.debug("Module data is more than a day old, downloading fresh data")
            thread:Thread = Thread(target=self._get_module_data, args=[], name="Neutron Dancer FSD data downloader")
            thread.start()

        file:Path = Path(Context.plugin_dir) / DATA_DIR / 'route.json'
        if file.exists():
            with open(file) as json_file:
                self._from_dict(json.load(json_file))


    @catch_exceptions
    def save(self) -> None:
        """ Save state to file """

        dir:Path = Path(Context.plugin_dir) / DATA_DIR
        dir.mkdir(parents=True, exist_ok=True)
        file:Path = dir / 'route.json'
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
            'ship': self.ship.to_dict() if self.ship else {},
            'route': self.route,
            'used_ships': self.used_ships,
            'ships': {k: ship.to_dict() for k, ship in self.ships.items()},
            'history': self.history
            }


    def _from_dict(self, dict:dict) -> None:
        """ Populate our data from a Dictionary that has been deserialized """

        # Need to migrate from older ships format?

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
        self.ship = Ship(dict.get('ship', {}))
        self.used_ships = dict.get('used_ships', [])
        self.ships = {k: Ship(data) for k, data in dict.get('ships', {}).items()}
        self.history = dict.get('history', [])
