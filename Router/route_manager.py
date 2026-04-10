import json
import re
import requests
from requests import Response
from pathlib import Path
from time import time, sleep
from datetime import UTC, datetime, timedelta
from threading import Thread


from config import config # type: ignore
from utils.debug import Debug, catch_exceptions
from utils.misc import hfplus, copy_to_clipboard

from .constants import ovr, errs, lbls, CarrierStates, HEADERS, HEADER_MAP, DATA_DIR, SPANSH_ROUTE, SPANSH_GALAXY_ROUTE, SPANSH_RESULTS
from .context import Context
from .ship import Ship
from .route import Route

SAVE_VARS:dict = {'system': '', 'src': '', 'dest': '', 'last_plot': 'Neutron',
                  'carrier_id': '', 'carrier_location': '', 'neutron_params': {}, 'galaxy_params': {},
                  'ship_id': '', 'cargo': 0, 'shiplist': [], 'history': [],
                  'window_geometries' : {}}
class Router():
    """
    Class to manage routes, all the route data and state information.
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self, test:bool = False) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        # Current location data and settings
        self.system:str = ""
        self.src:str = ''
        self.dest:str = ''

        # Current ship data
        self.ship_id:str = ""
        self.cargo:int = 0
        self.ship:Ship|None = None

        # Record of used ships and shipyard
        self.shiplist:list = []
        self.ships:dict[str, Ship] = {}
        self.history:list = []

        # Info about the last route plotted
        self.last_plot:str = "Neutron"
        self.galaxy_params:dict = {}
        self.neutron_params:dict = {}
        self.cancel_plot:bool = False

        # Carrier
        self.carrier_id:str = ''
        self.carrier_state:CarrierStates = CarrierStates.Idle
        self.carrier_location:str = ''
        self.carrier_destination:str = ''

        self.window_geometries:dict = {}

        self._load()

        if Context.route.route != []: Context.route.update_route(0, self.system)
        self._initialized = True


    def swap_ship(self, ship_id:str) -> None:
        """
        Called on a ship swap event to update our current ship information
        On a ship swap we don't get the full loadout so we have torely on our shipyard and hope we've seen this ship before
        """
        # Normalize ship_id to string since stored keys are strings
        sid = str(ship_id)
        if sid not in self.ships.keys():
            Debug.logger.info(f"ShipID {sid} not found in shipyard")
            self.ship_id = ""
            self.ship = None
            return

        self.ship_id = sid

        self.neutron_params['range'] = self.ships[sid].range
        self.neutron_params['supercharge_multiplier'] = self.ships[sid].supercharge_multiplier
        self.ship = self.ships[sid]


    def set_ship(self, entry:dict) -> None:
        """ Set the current ship details and update the UI """
        ship:Ship = Ship(entry)
        self.ship = ship
        self.ship_id = str(ship.id)
        self.neutron_params['supercharge_multiplier'] = ship.supercharge_multiplier
        self.neutron_params['range'] = ship.range
        self.ships[self.ship_id] = ship

        if self.ship_id in self.shiplist:
            self.shiplist.remove(self.ship_id)
        self.shiplist.insert(0, self.ship_id)
        # Context.ui may be None in headless/test environments; guard the call.
        if getattr(Context, 'ui', None) is not None and hasattr(Context.ui, 'switch_ship'):
            try:
                Context.ui.switch_ship(self.ship)
            except Exception as e:
                Debug.logger.exception(f"Error switching ship in UI: {e}")
        else:
            Debug.logger.debug("No UI available to switch ship; skipping UI update.")


    def jumped(self, system:str, entry:dict) -> None:
        """ Called after a jump in order to update the route, the UI etc."""

        if Context.route.route == [] or Context.route.fleetcarrier == True: return
        Context.route.record_jump(entry.get('StarSystem', system), entry.get('JumpDist', 0))

        # End of the line?
        if Context.router.system == Context.route.destination():
            self._store_history()

        if Context.route.update_route(0, entry.get('StarSystem', system)) > 0:
            Debug.logger.debug(f"Updating route")
            Context.ui.update_waypoint()
            self.update_jump_overlay()


    def update_jump_overlay(self) -> None:
        """ Update overlay after a waypoint """
        Debug.logger.debug(f"Updating jump overlay")
        wp:str = Context.route.next_stop()
        if Context.route.jumps_to_wp() != 0:
            wp += f" ({Context.route.jumps_to_wp()} {lbls['jumps'] if Context.route.jumps_to_wp() != 1 else lbls['jump']})"

        message:list = [{'size': 'large', 'text' : "Next: " + str(wp)}]
        jumps:tuple = tuple([Context.route.total_jumps() - Context.route.jumps_remaining(), 'int', '0'])
        tjumps:tuple = tuple([Context.route.total_jumps(), 'int'])
        txt:str = lbls['jumps'] if Context.route.jc != None else lbls['waypoints']
        jstr:str = f"{txt} {hfplus(jumps)}/{hfplus(tjumps)}"
        if Context.route.total_dist() > 0:
            jstr += f", {lbls['distance']} "
            dist:tuple = tuple([Context.route.total_dist() - Context.route.dist_remaining(), 'float', '0', ''])
            jstr += f"{hfplus(dist)}/{hfplus(Context.route.total_dist())} ly"

        next_refuel:int|None = Context.route.next_refuel()
        if next_refuel is not None and next_refuel == 0:
            jstr += ", ⛽ " + lbls["refuel_now"]
        if next_refuel is not None and next_refuel > 0:
            jstr += ", " + lbls["next_refuel"].format(r=next_refuel)
            jstr += " " + lbls["jump"] if next_refuel == 1 else " " + lbls["jumps"]

        Debug.logger.debug(f"Next refuel {next_refuel}")
        message.append({'size': "normal", 'text': f"{jstr}"})
        Context.overlay.display_frame('Default', message, ttl=120)
        Context.overlay.display_frame('Galaxy Map', message, ttl=120)


    def update_route(self, i:int) -> None:
        """ Called by the UI when next or prev is clicked """
        Context.route.update_route(i)
        self.update_jump_overlay()


    @catch_exceptions
    def carrier_event(self, entry:dict) -> None:
        """ Note carrier jumps for a cooldown notification """
        #if Context.route.route == [] or Context.route.fleetcarrier == False: return

        match entry.get('event'):
            case 'CarrierJumpRequest': # if entry.get('SystemName', '') == Context.route.next_stop():
                self.carrier_id = entry.get('CarrierID', '')
                self.carrier_state = CarrierStates.Jumping
                self.carrier_dest:str = entry.get('SystemName', '')
                end:datetime = datetime.fromisoformat(entry.get("DepartureTime", ''))

                jstr:str = ovr['jump'].format(d=self.carrier_dest, t='{t}')
                if entry.get('CarrierType', '') == 'SquadronCarrier':
                    jstr = 'Squadron ' + jstr
                Context.overlay.display_countdown('Carrier', jstr, end)
                rem:timedelta = end - datetime.now(tz=end.tzinfo)
                Context.ui.frame.after((rem.seconds + 2) * 1000, lambda: self.jump_complete())
                Debug.logger.debug(f"Carrier {self.carrier_id} jumping to {entry.get('SystemName', '')}")

            case 'CarrierJumpCancelled' if self.carrier_id == entry.get('CarrierID', ''):
                self.carrier_state = CarrierStates.Cooldown
                Context.overlay.stop_countdown('Carrier')
                Context.overlay.display_countdown('Carrier', ovr['cooldown'], 60)
                Context.ui.frame.after(60000, lambda: self.cooldown_complete())

            case 'CarrierLocation' if self.carrier_state == CarrierStates.Jumping and self.carrier_id == entry.get('CarrierID', ''):
                self.carrier_location = entry.get('StarSystem', '')
                Debug.logger.debug(f"Carrier is in {self.carrier_location}")
                if Context.route.fleetcarrier == True:
                    Context.route.update_route(0, self.carrier_location)
                    Context.ui.update_waypoint()
                self.carrier_state = CarrierStates.Cooldown
                Context.ui.frame.after(300000, lambda: self.cooldown_complete())
                Context.overlay.stop_countdown('Carrier')
                Context.overlay.display_countdown('Carrier', ovr['cooldown'], 300)


    def jump_complete(self) -> None:
        """ If we didn't get a notification of the carrier jump completion complete it """
        if self.carrier_state != CarrierStates.Jumping: return

        self.carrier_location = self.carrier_destination
        if Context.route.fleetcarrier == True:
            Context.route.update_route(0, self.carrier_location)
            Context.ui.update_waypoint()
        self.carrier_state = CarrierStates.Cooldown
        Context.ui.frame.after(300000, lambda: self.cooldown_complete())
        Context.overlay.stop_countdown('Carrier')
        Context.overlay.display_countdown('Carrier', ovr['cooldown'], 300)


    def cooldown_complete(self) -> None:
        """ Show an informational messagebox indicating a carrier cooldown has completed. """
        Debug.logger.debug(f"Cooldown complete notification triggered.")
        self.carrier_state = CarrierStates.Idle
        Context.ui.cooldown_complete()


    def _store_history(self) -> None:
        """ Upon route completion store src, dest and ship data """
        Debug.logger.debug(f"Storing route history {self.src}, {self.dest}")
        if self.src != '' and self.src:
            self.history.insert(0, self.src)
        if self.dest != '' and self.dest not in self.history:
            self.history.insert(0, self.dest)
        if "" in self.history:
            self.history.remove("")
        self.history = list(dict.fromkeys(self.history))[:10] # Keep only last 10 unique entries
        Debug.logger.debug(f"Route history updated: {self.history}")


    def plot_route(self, which:str, params:dict) -> bool:
        """ Initiate Spansh route plotting """

        match which:
            case 'Galaxy':
                url = SPANSH_GALAXY_ROUTE
                self.src = params['source']
                self.dest = params['destination']
                self.galaxy_params = params
            case 'Neutron':
                url:str = SPANSH_ROUTE
                self.src = params['from']
                self.dest = params['to']
                self.neutron_params = params
            case _:
                Debug.logger.error(f"Unknown route type {which}")
                return False

        self.last_plot = which

        Thread(target=self._plotter, args=(url, params), daemon=True,
               name="Neutron Dancer route plotting worker").start()
        return True


    def _plotter(self, url:str, params:dict) -> None:
        """ Async function to run the Spansh query """
        Debug.logger.debug(f"Plotting route {params} to {url}")

        self.cancel_plot = False
        try:
            limit:int = int(params.get('max_time', 20))
            results:Response = requests.post(url, data=params,
                                             headers={'User-Agent': Context.plugin_useragent,
                                                      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

            if results.status_code != 202:
                self.plot_error(results)
                return

            tries = 0
            while tries < limit:
                if config.shutting_down or self.cancel_plot: return # Quit
                response:dict = json.loads(results.content)
                job:str = response["job"]

                results_url:str = f"{SPANSH_RESULTS}/{job}"
                route_response:Response = requests.get(results_url, timeout=5)
                if route_response.status_code != 202:
                    break
                tries += 1
                sleep(1)

            if not route_response or route_response.status_code != 200 or self.cancel_plot:
                self.plot_error(route_response)
                return

            result:dict = json.loads(route_response.content)["result"]
            res:list = result.get('jumps', result.get('system_jumps', []))

            cols:list = []; hdrs:list = []; h:str
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

            self._store_history()

            Context.route = Route(hdrs, rte)
            Context.route.offset = 0

            copy_to_clipboard(Context.ui.parent, Context.route.next_stop())
            Context.ui.show_frame('Route')
            self.update_jump_overlay()
            self.save()

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.show_frame(Context.router.last_plot) # Return to the plot gui
            Context.ui.show_error(errs["plot_error"])


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

        Context.ui.show_frame(Context.router.last_plot) # Return to the plot gui
        Context.ui.show_error(err)
        return


    @catch_exceptions
    def import_route(self, filename:str = '') -> bool:
        """ Load a route from a CSV """
        try:
            Debug.logger.info("Importing route")
            if Context.csv == None or Context.csv.read(filename) == False:
                Debug.logger.info(f"Failed to load route")
                Context.ui.show_error(errs['no_filename'] if not Context.csv else Context.csv.error)
                return False

            Context.route = Route(Context.csv.headers, Context.csv.route)
            self.src = Context.route.source()
            self.dest = Context.route.destination()

            Context.route.offset = 0
            copy_to_clipboard(Context.ui.parent, Context.route.next_stop())

            return True

        except Exception as e:
            Debug.logger.error("Failed to load route:", exc_info=e)
            Context.ui.show_error(errs['parse_error'])
            return False


    def export_route(self) -> bool:
        """ Save a route to a CSV file """
        try:
            if Context.csv == None or Context.csv.write(Context.route.hdrs, Context.route.route) == False:
                Debug.logger.error(f"Failed to save route")
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
                "fuelpower": 2.5025,
                "mass": 160,
                "maxfuel": 6.8,
                "optmass": 4670,
                "power": 1.15,
                "rating": "A",
                "symbol": "Int_Hyperdrive_Overcharge_Size8_Class5_Overchargebooster_MkII",
            })

            Debug.logger.debug(f"Downloaded {len(Context.modules)} FSD entries from Coriolis")
            dir:Path = Path(Context.plugin_dir) / DATA_DIR
            dir.mkdir(parents=True, exist_ok=True)
            file:Path = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'

            with open(file, 'w') as outfile:
                json.dump(Context.modules, outfile)

        except Exception as e:
            Debug.logger.error("Failed to download FSD data, exception info:", exc_info=e)


    @catch_exceptions
    def _load(self) -> None:
        """ Load state from files """

        # Get the FSD data from Coriolis' github repo
        file = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'
        if file.exists():
            with open(file) as json_file:
                Context.modules = json.load(json_file)
                Debug.logger.debug(f"Loaded {len(Context.modules)} modules from local file")

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
        if Context.route != None:
            save['route'] = Context.route.to_dict()
        return save

    def _from_dict(self, dict:dict) -> None:
        """ Populate our data from a Dictionary that has been deserialized """

        [setattr(self, k, dict.get(k, v)) for k, v in SAVE_VARS.items()]
        (hdrs, route, offset, jumps) = dict.get('route', ([], [], 0, []))
        Context.route = Route(hdrs, route, offset, jumps)
        self.ship = Ship(dict.get('ship', {}))
        self.ships = {k: Ship(data) for k, data in dict.get('ships', {}).items()}

        # Migrate
        if self.shiplist == [] and self.ships != {}:
            self.shiplist = [id for id in self.ships.keys()]
