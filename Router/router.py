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
from .route import Route

SAVE_VARS:dict = {'system': '', 'src': '', 'dest': '', 'last_plot':
                  'Neutron', 'neutron_params': {}, 'galaxy_params': {},
                  'ship_id': '', 'cargo': 0, 'used_ships': [], 'history': []}
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

        self.src:str = ''
        self.dest:str = ''

        self.used_ships:list = []
        self.ships:dict[str, Ship] = {}
        self.history:list = []

        # Current ship data
        self.system:str = ""
        self.ship_id:str = ""
        self.cargo:int = 0
        self.ship:Ship|None = None

        self.last_plot:str = "Neutron"
        self.galaxy_params:dict = {}
        self.neutron_params:dict = {}

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

        self.neutron_params['range'] = self.ships[ship_id].range
        self.neutron_params['supercharge_mult'] = self.ships[ship_id].supercharge_mult
        self.ship = self.ships[ship_id]


    def set_ship(self, entry:dict) -> None:
        """ Set the current ship details and update the UI """
        Debug.logger.debug(f"Setting current ship to {entry.get('ShipID', '')} {entry.get('ShipName', '')} {entry.get('Ship', '')}")
        ship:Ship = Ship(entry)
        self.ship = ship
        self.ship_id = str(ship.id)
        self.neutron_params['supercharge_mult'] = ship.supercharge_mult
        self.neutron_params['range'] = ship.range
        self.ships[self.ship_id] = ship
        Context.ui.switch_ship(self.ship)


    def _store_history(self) -> None:
        """ Upon route completion store src, dest and ship data """

        if self.src != '' and self.src:
            self.history.insert(0, Context.route.source())
        if self.dest != '' and self.dest not in self.history:
            self.history.insert(0, Context.route.destination())
        self.history = list(dict.fromkeys(self.history))[:10] # Keep only last 10 unique entries

        if self.ship_id == None or self.ship == None:
            Debug.logger.debug(f"No ship to store")
            return

        if self.ship_id not in self.used_ships:
            self.used_ships.append(self.ship_id)
        Debug.logger.debug(f"Storing ship {str(self.ship)}")


    def plot_route(self, which:str, params:dict) -> bool:
        """ Initiate Spansh route plotting """

        match which:
            case 'Galaxy':
                url = SPANSH_GALAXY_ROUTE
                self.src = params['source']
                self.dest = params['destination']
                self.galaxy_params = params
            case _:
                url:str = SPANSH_ROUTE
                self.src = params['from']
                self.dest = params['to']
                self.neutron_params = params
        self.last_plot = which

        thread:Thread = Thread(target=self._plotter, args=(url, params), name="Neutron Dancer route plotting worker")
        thread.start()
        return True


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

            result:dict = json.loads(route_response.content)["result"]
            res:list = result.get('jumps', result.get('system_jumps', []))

            cols:list = []
            hdrs:list = []
            h:str
            for h in HEADERS:
                k:str
                for k in res[0].keys():
                    if HEADER_MAP.get(k, '') == h:
                        hdrs.append(h)
                        cols.append(k)

            rte:list = []
            for i, waypoint in enumerate(res):
                r:list = []
                for c in cols:
                    if re.match(r"^(\d+)?$", str(waypoint[c])):
                        r.append(round(int(waypoint[c]), 2))
                        continue
                    if re.match(r"^\d+\.(\d+)?$", str(waypoint[c])):
                        r.append(round(float(waypoint[c]), 2))
                        continue
                    r.append(waypoint[c])
                rte.append(r)

            Context.route = Route(hdrs, rte)
            Context.route.offset = 1 if Context.route.source() == self.system else 0

            Context.ui.ctc(Context.route.next_stop())
            Context.ui.show_frame('Route')
            self.save()
            Debug.logger.debug(f" Route plotted {Context.route}")

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True) # Return to the plot gui
            Context.ui.show_error(lbls["plot_error"])


    @catch_exceptions
    def plot_error(self, response:Response) -> None:
        """ Parse the response from Spansh on a failed route query """

        Debug.logger.debug(f"Result: {response} {json.loads(response.content)}")
        err:str = errs["no_response"]
        #if response:
        #    Debug.logger.info(f"Server response: {response.json()}")
        #    err = errs["plot_error"]

        if response.status_code in [400, 500] and "error" in json.loads(response.content).keys():
            Debug.logger.info(f"Server response: {response.json()}")
            err = json.loads(response.content)["error"]

        Context.ui.enable_plot_gui(True)
        Context.ui.show_error(err)
        return


    def import_route(self) -> bool:
        """ Load a route from a CSV """
        try:
            if Context.csv == None or Context.csv.read() == False:
                Debug.logger.debug(f"Failed to load route")
                Context.ui.show_error(errs['no_filename'])
                return False

            hdrs:list = Context.csv.headers
            rte:list = Context.csv.route
            route:Route = Route(hdrs, rte)
            self.src = route.source()
            self.dest = route.destination()

            return True

        except Exception as e:
            Debug.logger.error("Failed to load route:", exc_info=e)
            Context.ui.show_error(errs['parse_error'])
            return False


    def export_route(self) -> bool:
        """ Save a route to a CSV file """
        try:
            if Context.csv == None or Context.csv.write(Context.route.hdrs, Context.route.route) == False:
                Debug.logger.debug(f"Failed to save route")
                Context.ui.show_error(errs['no_filename'])
                return False
            return True
        except Exception as e:
            Debug.logger.error("Failed to save route:", exc_info=e)
            Context.ui.show_error(errs['export_error'])
            return False


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
            json.dump(self._as_dict(), outfile, indent=4)


    def _as_dict(self) -> dict:
        """ Return a Dictionary representation of our data, suitable for serializing """

        save:dict = {k: getattr(self, k, v) for k, v in SAVE_VARS.items()}

        save['ship'] = self.ship.to_dict() if self.ship else {}
        save['ships'] = {k: ship.to_dict() for k, ship in self.ships.items()}
        save['route'] = Context.route.to_dict()
        return save

    def _from_dict(self, dict:dict) -> None:
        """ Populate our data from a Dictionary that has been deserialized """

        [setattr(self, k, dict.get(k, v)) for k, v in SAVE_VARS.items()]
        (hdrs, route, offset, jumps) = dict.get('route', [[], [], 0, []])
        Context.route = Route(hdrs, route, offset, jumps)
        self.ship = Ship(dict.get('ship', {}))
        self.ships = {k: Ship(data) for k, data in dict.get('ships', {}).items()}


