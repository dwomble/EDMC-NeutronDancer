import ast
import csv
import json
import os
from os import path
import re
import requests
from requests import Response
import tkinter.filedialog as filedialog
import webbrowser
from pathlib import Path
from semantic_version import Version # type: ignore
from time import sleep
from typing import TYPE_CHECKING

from utils.Debug import Debug, catch_exceptions

from .strings import hdrs, lbls
from .context import Context

DATA_DIR = 'data'
# Map from returned data to our header names
HDRMAP:dict = {"System Name": "system", "Distance Jumped": "distance_jumped", "Distance Remaining": "distance_left",
               "Jumps": "jumps", "Neutron Star": "neutron_star"}
# Headers that we accept
HEADERS:list = ["System Name", "Jumps", "Neutron Star", "Body Name", "Body Subtype",
                "Is Terraformable", "Distance To Arrival", "Estimated Scan Value", "Estimated Mapping Value",
                "Distance", "Distance Jumped", "Distance Remaining", "Fuel Used", "Icy Ring", "Pristine", "Restock Tritium"]
class Router():
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        self.update_available:bool = False
        self.roadtoriches:bool = False
        self.fleetcarrier:bool = False

        self.headers:list = []
        self.route:list = []
        self.ships:dict = {}
        self.history:list = []
        self.bodies:str = ""

        self.system:str = ""
        self.src:str = ""
        self.dest:str = ""
        self.ship_id:str = ""
        self.ship:dict = {
            'name': "",
            'max_range': 0.0,
            'type': ""
        }
        self.range:float = 32.0
        self.supercharge_mult:int = 4
        self.efficiency:int = 60
        self.offset:int = 0
        self.jumps_left:int = 0
        self.next_stop:str = ""

        self._load()
        self._initialized = True


    def set_ship(self, ship_id:str, range:float, name:str, type:str) -> None:
        Debug.logger.debug(f"Setting current ship to {ship_id} {name} {type}")
        self.ship_id = str(ship_id)

        self.range = round(float(range) * 0.95, 2)
        self.supercharge_mult = 6 if type in ('explorer_nx') else 4

        self.ship['name'] = name
        self.ship['max_range'] = float(range)
        self.ship['type'] = type

        Context.ui.set_range(self.range, self.supercharge_mult)
        self.save()


    def goto_next_waypoint(self) -> None:
        if self.offset < len(self.route) - 1:
            self.update_route(1)


    def goto_prev_waypoint(self) -> None:
        if self.offset > 0:
            self.update_route(-1)


    def _syscol(self, which:str = '') -> int:
        """ Figure out which column has a chosen key """
        if which == '':
            for h in ['System Name', 'system']:
                if h in self.headers:
                    which = h
                    break
        if which == '' or which not in self.headers:
            return 0

        return self.headers.index(which)



    def _store_history(self) -> None:
        """ Upon route completion store route and ship data """
        if self.src != '':
            self.history.insert(0, self.src)
        if self.dest != '':
            self.history.insert(0, self.dest)
        self.ships[self.ship_id] = self.ship
        self.save()

    @catch_exceptions
    def update_route(self, direction:int = 0) -> None:
        """ Step forwards or backwards through the route """
        Debug.logger.debug(f"Updating route by {direction} {self.system}")
        c:int = self._syscol()
        if self.route == []: return

        if direction == 0: # Figure out if we're on the route
            for r in self.route[self.offset:]:
                if r[c] == self.system:
                    Debug.logger.debug(f"Found system {self.offset} {direction}")
                    self.offset = direction
                    direction = 1
                    break
                direction += 1

            # We aren't on the route so just return
            if self.route[self.offset][c] != self.system:
                Debug.logger.debug(f"We aren't on the route")
                return
        Debug.logger.debug(f"New offset {self.offset} {direction} {self.route[self.offset][c]}")

        if self.offset + direction < 0 or self.offset + direction >= len(self.route):
            if direction > 0:
                self.next_stop = lbls['route_complete']
                self._store_history()
            Context.ui.update_display(True)
            return

        Debug.logger.debug(f"Stepping to {self.offset + direction} {self.route[self.offset + direction][c]}")
        self.offset += direction
        self.next_stop = self.route[self.offset][c]

        Context.ui.update_display()


    def goto_changelog_page(self) -> None:
        return
        changelog_url = 'https://github.com/rinkulu/EDMC-SpanshRouterRE/blob/master/CHANGELOG.md#'
        changelog_url += self.spansh_updater.version.replace('.', '')
        webbrowser.open(changelog_url)


    @catch_exceptions
    def import_csv(self, filepath:Path|str, clear_previous_route:bool = True):
        """ Import a csv file """
        ftypes = [
            ('All supported files', '*.csv *.txt'),
            ('CSV files', '*.csv'),
            ('Text files', '*.txt'),
        ]
        filename:str = filedialog.askopenfilename(filetypes=ftypes, initialdir=os.path.expanduser('~'))

        if len(filename) == 0:
            Debug.logger.debug(f"No filename selected")
            return

        with open(filepath, 'r', encoding='utf-8-sig', newline='') as csvfile:
            self.roadtoriches = False
            self.fleetcarrier = False

            if clear_previous_route:
                self.clear_route()

            route_reader = csv.DictReader(csvfile)
            # Check it has column headings
            if not route_reader.fieldnames:
                Debug.logger.error(f"File {filepath} is empty or does't have a header row")
                return

            hdrs:list = list(set(HEADERS).intersection(set(route_reader.fieldnames)))
            if hdrs == [] or "System Name" not in hdrs:
                Debug.logger.error(f"File {filepath} is of unsupported format")
                return

            route:list = []
            for row in route_reader:
                r:list = []
                if row not in (None, "", []): continue
                for col in hdrs:
                    if col in row:
                        if col in ["body_name", "body_subtype"]:
                            r.append(ast.literal_eval(row[col]))
                            continue
                        m = re.match(r"^\d+(\.\d+)?$", row[col])
                        Debug.logger.debug(f"Row {row[col]} {m}")
                        r.append(row[col] if not re.match(r"^\d+(\.\d+)?$", row[col]) else round(float(row[col]), 2))
                route.append(r)

            self.fleetcarrier = True if "Fuel Used" in hdrs else False
            self.roadtoriches = True if "Estimated Scan Value" in hdrs else False
            Debug.logger.debug(f"Headers: {hdrs} rows {len(route)}")
            self.headers = hdrs
            self.route = route
            self.save()


    def plot_route(self, source:str, dest:str, efficiency:int, range:float, supercharge_mult:int = 4) -> bool:
        Debug.logger.debug(f"Plotting route")

        try:
            job_url = "https://spansh.co.uk/api/route?"

            results:Response = requests.post(job_url,
                params={"efficiency": efficiency, "range": range, "from": source, "to": dest, 'supercharge_multiplier': supercharge_mult},
                headers={'User-Agent': Context.plugin_useragent})

            if results.status_code != 202:
                self.plot_error(results)
                return False

            tries = 0
            while tries < 20:
                response:dict = json.loads(results.content)
                job:str = response["job"]

                results_url:str = "https://spansh.co.uk/api/results/" + job
                route_response:Response = requests.get(results_url, timeout=5)
                if route_response.status_code != 202:
                    break
                tries += 1
                sleep(1)

            if not route_response:
                Debug.logger.error("Query to Spansh timed out")
                Context.ui.show_error("The query to Spansh was too long and timed out, please try again.")

            if route_response.status_code != 200:
                self.plot_error(route_response)
                return False

            route:dict = json.loads(route_response.content)["result"]["system_jumps"]

            clist:list = list(route[0].keys())
            cols:list = []
            hdrs:list = []
            for h in HEADERS:
                if HDRMAP.get(h, '') in route[0].keys():
                    hdrs.append(h)
                    cols.append(HDRMAP.get(h, ''))

            Debug.logger.debug(f"Cols: {cols} hdrs: {hdrs}")
            rte:list = []
            for waypoint in route:
                r:list = []
                for c in cols:
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
            Context.ui.update_display(True)
            self.save()
            return True

        except Exception as e:
            Debug.logger.error("Failed to plot route, exception info:", exc_info=e)
            Context.ui.enable_plot_gui(True)
            Context.ui.show_error(lbls["plot_error"])
        Debug.logger.debug(f"Done")
        return False


    def plot_error(self, response:Response) -> None:
        Debug.logger.error(f"Failed to query plotted route from Spansh (response code {response.status_code}): {response.text}")
        Context.ui.enable_plot_gui(True)
        failure:dict = json.loads(response.content)

        if response.status_code == 400 and "error" in failure:
            Context.ui.show_error(failure["error"])
            #if "starting system" in failure["error"]:
            #    Context.ui.source_ac["fg"] = "red"
            #if "finishing system" in failure["error"]:
            #    Context.ui.dest_ac["fg"] = "red"
        else:
            Context.ui.show_error(lbls["plot_error"])
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
        self.offset = 0
        self.headers = []
        self.route = []
        self.next_stop:str = ""
        self.jumps_left = 0
        self.roadtoriches = False
        self.fleetcarrier = False
        self.save()


    def export_route(self) -> None:
        """ Export the route as a csv """

        if self.route == [] or self.headers == []:
            Debug.logger.debug(f"No route")
            return

        route_start:str = self.route[0][0]
        route_end:str = self.route[-1][0]
        route_name:str = f"{route_start} to {route_end}"
        ftypes:list = [('CSV files', '*.csv')]
        filename:str = filedialog.asksaveasfilename(filetypes=ftypes, initialdir=os.path.expanduser('~'), initialfile=f"{route_name}.csv")

        if len(filename) == 0:
            Debug.logger.debug(f"No filename selected")
            return

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.headers)
            for row in self.route:
                writer.writerow(row)


    def update_bodies_text(self) -> None:
        if not self.roadtoriches:
            return

        # For the bodies to scan use the current system, which is one before the next stop
        lastsystemoffset:int = self.offset - 1
        if lastsystemoffset < 0:
            lastsystemoffset = 0    # Display bodies of the first system

        lastsystem:str = self.route[lastsystemoffset][0]
        bodynames:str = self.route[lastsystemoffset][2]
        bodysubtypes:str = self.route[lastsystemoffset][3]

        waterbodies:list = []
        rockybodies:list = []
        metalbodies:list = []
        earthlikebodies:list = []
        unknownbodies:list = []

        for num, name in enumerate(bodysubtypes):
            shortbodyname:str = bodynames[num].replace(lastsystem + " ", "")
            if name.lower() == "high metal content world":
                metalbodies.append(shortbodyname)
            elif name.lower() == "rocky body":
                rockybodies.append(shortbodyname)
            elif name.lower() == "earth-like world":
                earthlikebodies.append(shortbodyname)
            elif name.lower() == "water world":
                waterbodies.append(shortbodyname)
            else:
                unknownbodies.append(shortbodyname)

        bodysubtypeandname:str = ""
        if len(metalbodies) > 0:
            bodysubtypeandname += "\n   Metal: " + ', '.join(metalbodies)
        if len(rockybodies) > 0:
            bodysubtypeandname += "\n   Rocky: " + ', '.join(rockybodies)
        if len(earthlikebodies) > 0:
            bodysubtypeandname += "\n   Earth: " + ', '.join(earthlikebodies)
        if len(waterbodies) > 0:
            bodysubtypeandname += "\n   Water: " + ', '.join(waterbodies)
        if len(unknownbodies) > 0:
            bodysubtypeandname += "\n   Unknown: " + ', '.join(unknownbodies)

        self.bodies = f"\n{lastsystem}:{bodysubtypeandname}"


    def check_for_update(self) -> None:
        return
        version_url = "https://raw.githubusercontent.com/rinkulu/EDMC-SpanshRouterRE/master/version"
        try:
            response = requests.get(version_url, timeout=2)
            if response.status_code == 200:
                if Context.plugin_version != Version(response.text):
                    self.update_available = True
                    self.spansh_updater = Updater(response.text, Context.plugin_dir)
            else:
                Debug.logger.error(
                    f"Could not query latest SpanshRouterRE version (status code {response.status_code}): "
                    + response.text
                )
        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)

    def install_update(self) -> None:
        return
        self.spansh_updater.install()


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
