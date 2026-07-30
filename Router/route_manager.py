import json
import re
import requests
from requests import Response
from pathlib import Path
from time import time, sleep
from datetime import UTC, datetime, timedelta
from threading import Thread

from config import config # type: ignore
import edmc_data # type: ignore
from utils.debug import Debug, catch_exceptions
from utils.misc import singleton, copy_to_clipboard

from .constants import errs, CarrierStates, HEADERS, HEADER_MAP, DATA_DIR, SHIP_DIR, GH_MODULES, SPANSH_RESULTS, SPANSH_RICHES_ROUTE, SPANSH_EXOBIOLOGY_ROUTE, SPANSH_TRADE_ROUTE, SPANSH_FLEETCARRIER_ROUTE
from .context import Context
from .ship import Ship
from .route import Route
from .plotters import PLOTTER_SPECS

SAVE_VARS:dict = {'system': '', 'src': '', 'dest': '', 'last_plot': 'Neutron',
                  'carrier_id': '', 'carrier_location': '', 'route_params': {},
                  'ship_id': '', 'cargo': 0, 'shiplist': [], 'history': [],
                  'window_geometries' : {}}

@singleton
class Router():
    """
    Class to manage routes, all the route data and state information.
    """

    def __init__(self, test:bool = False) -> None:

        # Current location data and settings
        self.system:str = ""
        self.src:str = ''
        self.dest:str = ''

        # Current ship data
        self.ship_id:str = ""
        self.cargo:int = 0
        self.ship:Ship|None = None

        # Record of used ships and shipyard
        self.shiplist:dict = {}
        self.history:list = []

        # Info about the last route plotted
        self.last_plot:str = "Galaxy"
        self.route_types = {name: spec.label for name, spec in PLOTTER_SPECS.items()}
        self.route_params:dict = {}
        for r in self.route_types.keys():
            self.route_params[r] = {}
        self.cancel_plot:bool = False

        # Carrier
        self.carrier_id:str = ''
        self.carrier_state:CarrierStates = CarrierStates.Idle
        self.carrier_location:str = ''
        self.carrier_destination:str = ''

        self.window_geometries:dict = {}

        self._load()

        if Context.route.route != []:
            Context.route.update_route(0, self.system)

    def shipnames(self) -> list:
        """ Return a list of shipnames """
        names:list = list(self.shiplist.values())
        names.reverse()
        return names

    def shipid(self, name:str) -> str:
        """ Get a ship's id from its name """
        for id, ship in self.shiplist.items():
            if name == ship:
                return id
        return ""


    def swap_ship(self, ship_id:str) -> None:
        """
        Called on a ship swap event to update our current ship information
        On a ship swap we don't get the full loadout so we have torely on our shipyard and hope we've seen this ship before
        """
        ship = self.load_ship(ship_id)
        if not ship:
            Debug.logger.info(f"ShipID {ship_id} not found in shipyard")
            self.ship_id = ""
            self.ship = None
            return
        self.set_ship(ship.as_dict())


    def set_ship(self, entry:dict) -> None:
        """ Set the current ship details and update the UI """
        ship:Ship = Ship(entry)
        self.ship = ship
        self.ship_id = str(ship.id)

        self._save_ship(ship)

        # Re-add so keys are in reverse order
        if ship.id in self.shiplist:
            del self.shiplist[ship.id]
        self.shiplist[ship.id] = ship.name

        # Context.ui may be None in headless/test environments; guard the call.
        if getattr(Context, 'ui', None) is not None and hasattr(Context.ui, 'switch_ship'):
            try:
                Context.ui.switch_ship(ship)
            except Exception as e:
                Debug.logger.exception(f"Error switching ship in UI: {e}")
        else:
            Debug.logger.debug("No UI available to switch ship; skipping UI update.")


    def dashboard_entry(self, cmdr, is_beta, entry) -> None:
        """ Copy next waypoint to clipboard on galaxy map entry """
        if not Context.ui.parent or not Context.route.jumps_remaining() or entry.get("GuiFocus") != edmc_data.GuiFocusGalaxyMap:
            return
        copy_to_clipboard(Context.ui.parent, Context.route.next_stop())


    def jumped(self, system:str, entry:dict) -> None:
        """ Called after a jump in order to update the route, the UI etc."""

        Context.route.fuel_full = False # We just jumped so we can't be full anymore
        if Context.route.route == [] or Context.route.fleetcarrier == True: return
        Context.route.record_jump(entry.get('StarSystem', system), entry.get('JumpDist', 0))

        # End of the line?
        if Context.router.system == Context.route.destination():
            self._store_history()

        if Context.route.update_route(0, entry.get('StarSystem', system)) > 0:
            Debug.logger.debug(f"Updating route {system} {Context.route.get_waypoint()}")
            Context.ui.update_progress()
            Context.overlay.update_jump_overlay()


    def update_route(self, i:int) -> None:
        """ Called to move forward or backward along the route 1 == forward, -1 == back """
        Debug.logger.debug(f"Update route {i} {Context.route.get_waypoint()}")
        Context.route.update_route(i)
        Context.ui.update_progress()
        Context.overlay.update_jump_overlay()


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

                Context.overlay.display_carrier(entry.get('CarrierType', ''), end, self.carrier_dest)
                rem:timedelta = end - datetime.now(tz=end.tzinfo)
                Context.ui.frame.after((rem.seconds + 2) * 1000, lambda: self.jump_complete())

            case 'CarrierJumpCancelled' if self.carrier_id == entry.get('CarrierID', ''):
                self.carrier_state = CarrierStates.Cooldown
                Context.overlay.display_carrier('Cooldown', 60)
                Context.ui.frame.after(60000, lambda: self.cooldown_complete())

            case 'CarrierLocation' if self.carrier_state == CarrierStates.Jumping and self.carrier_id == entry.get('CarrierID', ''):
                self.carrier_location = entry.get('StarSystem', '')
                if Context.route.fleetcarrier == True:
                    Context.route.update_route(0, self.carrier_location)
                    Context.ui.update_progress()
                self.carrier_state = CarrierStates.Cooldown
                Context.ui.frame.after(300000, lambda: self.cooldown_complete())
                Context.overlay.display_carrier('Cooldown', 300)


    @catch_exceptions
    def fuel_event(self, state:dict) -> None:
        """ Set fuel_full to true or false """

        fuel:float = -1
        with open(Path(config.get_str("journaldir") / "Status.json"), 'r') as file:
            status:dict = json.load(file)
            fuel = status.get('Fuel', {}).get('FuelMain', 0.0)

        Context.route.fuel_full = (fuel >= float(state.get('FuelCapacity', 0.0)))

        # Update the UI as we may need to hide the refuel notification
        if Context.route.jumps_remaining() > 0:
            Context.ui.update_progress()
            Context.overlay.update_jump_overlay()


    def jump_complete(self) -> None:
        """ If we didn't get a notification of the carrier jump completion complete it """
        if self.carrier_state != CarrierStates.Jumping: return

        self.carrier_location = self.carrier_destination
        if Context.route.fleetcarrier == True:
            Context.route.update_route(0, self.carrier_location)
            Context.ui.update_progress()
        self.carrier_state = CarrierStates.Cooldown
        Context.ui.frame.after(300000, lambda: self.cooldown_complete())
        Context.overlay.display_carrier('Cooldown', 300)


    def cooldown_complete(self) -> None:
        """ Show an informational messagebox indicating a carrier cooldown has completed. """
        self.carrier_state = CarrierStates.Idle
        Context.ui.cooldown_complete()


    def _store_history(self) -> None:
        """ Upon route completion store src, dest and ship data """
        if self.dest != '' and self.dest not in self.history:
            self.history.insert(0, self.dest)
        if self.src != '' and self.src:
            self.history.insert(0, self.src)
        if "" in self.history:
            self.history.remove("")
        self.history = list(dict.fromkeys(self.history))[:10] # Keep only last 10 unique entries


    def plot_route(self, which:str, params:dict) -> bool:
        """ Initiate Spansh route plotting """

        spec = PLOTTER_SPECS.get(which)
        if spec is None:
            Debug.logger.error(f"Unknown route type {which}")
            return False

        self.src = params[spec.src_key]
        self.dest = params.get(spec.dest_key, '')
        self.route_params[which] = params

        self.last_plot = which
        self._store_history()

        Thread(target=self._plotter, args=(which, spec.url, params), daemon=True,
               name="Neutron Dancer route plotting worker").start()
        return True


    def _flatten_nested_bodies_result(self, systems:list) -> list:
        """ Flatten Spansh's nested "systems containing bodies" result (used by the whole riches
        family -- Road to Riches, Ammonia/Earth-like/Rocky-metal, and Exobiology) into one row per
        body. Systems with no scannable bodies (e.g. the starting system) are omitted, matching the
        row shape of a Spansh-exported riches CSV, which never includes a bodyless system.

        Exobiology bodies additionally carry a `landmarks` list (biological species found there) and
        a `landmark_value` -- the figure that actually matters there, unlike `estimated_scan_value`
        which stays near-zero. Those two columns are only added when a body has `landmarks` at all,
        so plain riches-family rows (which never have that key) don't grow empty columns. """
        rows:list = []
        for system in systems:
            bodies:list = system.get('bodies', [])
            for body in bodies:
                row:dict = {
                    'system': system.get('name', ''), 'jumps': system.get('jumps', 0),
                    'body_name': body.get('name', ''), 'subtype': body.get('subtype', ''),
                    'is_terraformable': body.get('is_terraformable', False),
                    'distance_to_arrival': body.get('distance_to_arrival', 0),
                    'estimated_scan_value': body.get('estimated_scan_value', 0),
                    'estimated_mapping_value': body.get('estimated_mapping_value', 0)
                }
                landmarks:list = body.get('landmarks', [])
                if landmarks:
                    top:dict = max(landmarks, key=lambda l: l.get('value', 0))
                    row['species'] = top.get('subtype', '')
                    row['landmark_value'] = body.get('landmark_value', 0)
                rows.append(row)
        return rows


    def _flatten_trade_result(self, hops:list) -> list:
        """ Flatten Spansh's trade route -- a flat list of hops, each carrying one or more
        commodities at once (splitting cargo between them) -- into one row per commodity per
        hop. Each row's system/station is the hop's *destination*, matching every other route
        type's convention that a row represents the next place to travel to, not the
        already-occupied starting position (which is never a row of its own here either). """
        rows:list = []
        for hop in hops:
            dest:dict = hop.get('destination', {})
            for commodity in hop.get('commodities', []):
                rows.append({
                    'system': dest.get('system', ''), 'station': dest.get('station', ''),
                    'distance': hop.get('distance', 0),
                    'commodity': commodity.get('name', ''), 'amount': commodity.get('amount', 0),
                    'profit': commodity.get('profit', 0), 'total_profit': commodity.get('total_profit', 0),
                    'cumulative_profit': hop.get('cumulative_profit', 0)
                })
        return rows


    def _flatten_fleetcarrier_result(self, jumps:list) -> list:
        """ Each requested stop appears twice in Spansh's jumps list -- once ending the leg
        that reached it, once starting the next -- so filter to distance_to_destination == 0
        (arrivals only) for one row per stop, with the starting system never included. """
        return [j for j in jumps if j.get('distance_to_destination') == 0]


    def _plotter(self, which:str, url:str, params:dict) -> None:
        """ Async function to run the Spansh query """

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
            while tries < limit+1:
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

            raw_result = json.loads(route_response.content)["result"]
            if url in (SPANSH_RICHES_ROUTE, SPANSH_EXOBIOLOGY_ROUTE):
                # Every "systems containing bodies" route (Road to Riches and its body_types-filtered
                # variants, plus Exobiology) returns this same nested shape.
                res:list = self._flatten_nested_bodies_result(raw_result)
            elif url == SPANSH_TRADE_ROUTE:
                res:list = self._flatten_trade_result(raw_result)
            elif url == SPANSH_FLEETCARRIER_ROUTE:
                res:list = self._flatten_fleetcarrier_result(raw_result.get('jumps', []))
            else:
                res:list = raw_result.get('jumps', raw_result.get('system_jumps', []))

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

            Context.route = Route(hdrs, rte)
            Context.route.offset = 0
            Context.route.update_route(0, self.system)

            copy_to_clipboard(Context.ui.parent, Context.route.next_stop())
            Context.ui.show_frame('Route')
            Context.overlay.update_jump_overlay()
            self.save()

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.show_frame(Context.router.last_plot) # Return to the plot gui
            Context.ui.show_error(errs["plot_error"])


    @catch_exceptions
    def plot_error(self, response:Response) -> None:
        """ Parse the response from Spansh on a failed route query """

        Debug.logger.info(f"Result: {response} {json.loads(response.content)}")
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

    def clear_route(self) -> None:
        """ Clear the current route """
        Context.route = Route([], [], -1)
        if Context.overlay:
            Context.overlay.update_jump_overlay()
        self.save()

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

            Context.route.update_route(0, self.system)
            copy_to_clipboard(Context.ui.parent, Context.route.next_stop())
            Context.overlay.update_jump_overlay()
            Context.overlay.show_frame('Default')

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
            modules:list = []
            for key, url  in {"fsd": f"{GH_MODULES}/standard/frame_shift_drive.json",
                              "gfsb": f"{GH_MODULES}/internal/guardian_fsd_booster.json",
                              "ft": f"{GH_MODULES}/standard/fuel_tank.json"}.items():
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
            Debug.logger.debug(f"Downloaded {len(Context.modules)} FSD entries from Coriolis")

            dir:Path = Path(Context.plugin_dir) / DATA_DIR
            dir.mkdir(parents=True, exist_ok=True)
            file:Path = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'

            with open(file, 'w') as outfile:
                json.dump(Context.modules, outfile)

        except Exception as e:
            Debug.logger.error("Failed to download FSD data, exception info:", exc_info=e)


    @catch_exceptions
    def load_ship(self, which:str = "") -> Ship|None:
        """ Load a ship """
        if which == self.ship_id: return self.ship
        if which in self.shiplist.values(): which = self.shipid(which)

        dir:Path = Path(Context.plugin_dir) / DATA_DIR / SHIP_DIR
        dir.mkdir(parents=True, exist_ok=True)
        file:Path = dir / f"{which}.json"
        if file.exists():
            with open(file) as json_file:
                return Ship(json.load(json_file))

    @catch_exceptions
    def _save_ship(self, ship:Ship) -> None:
        dir:Path = Path(Context.plugin_dir) / DATA_DIR / SHIP_DIR
        dir.mkdir(parents=True, exist_ok=True)
        file:Path = dir / f"{ship.id}.json"
        with open(file, 'w') as outfile:
            json.dump(ship.as_dict(), outfile, indent=4)


    @catch_exceptions
    def _load(self) -> None:
        """ Load state from files """

        # Get the FSD data from Coriolis' github repo
        Context.modules = []
        file = Path(Context.plugin_dir) / DATA_DIR / 'module_data.json'
        if file.exists():
            with open(file) as json_file:
                Context.modules = json.load(json_file)
                Debug.logger.debug(f"Loaded {len(Context.modules)} modules from local file")

        # We need this so do it synchronously
        if Context.modules == []:
            self._get_module_data()

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
        save['ship'] = self.ship.as_dict() if self.ship else {}
        if Context.route != None:
            save['route'] = Context.route.to_dict()
        return save

    def _from_dict(self, dict:dict) -> None:
        """ Populate our data from a Dictionary that has been deserialized """

        [setattr(self, k, dict.get(k, v)) for k, v in SAVE_VARS.items()]
        r = dict.get('route', ([], [], -1))
        (hdrs, route, offset) = r[0:3]
        Context.route = Route(hdrs, route, offset)
        self.ship = Ship(dict.get('ship', {}))
        ships = {k: Ship(data) for k, data in dict.get('ships', {}).items()}

        # Migrate
        Debug.logger.debug(f"Dict: {dict.keys()}")
        if dict.get('neutron_params'):
            self.route_params['Neutron'] = dict.get('neutron_params', {})
            self.route_params['Galaxy'] = dict.get('galaxy_params', {})
            self.save()

        if isinstance(self.shiplist, list) and ships != {}:
            Debug.logger.info(f"Migrating save data to new structure")
            self.shiplist = {}
            for ship in ships.values(): self.shiplist[ship.id] = ship.name
            [self._save_ship(ship) for ship in ships.values()]
            self.save()
