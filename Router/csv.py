import ast
import csv
from pathlib import Path
from tkinter import filedialog
import re

from config import config # type: ignore

from .constants import HEADERS, ROUTE_DIR, errs
from .utils.debug import Debug, catch_exceptions
from .utils.misc import singleton
from .context import Context
from .route import Route
@singleton
class CSV:
    """
    Class to import and export routes as CSV files
    """

    def __init__(self) -> None:
        self.roadtoriches:bool
        self.fleetcarrier:bool
        self.headers:list
        self.route:list
        self.error:str = ""
        self.navroute:dict = {}

    def choose_file(self) -> str:
        ftypes:list = [
            ('All supported files', '*.csv *.txt'),
            ('CSV files', '*.csv'),
            ('Text files', '*.txt'),
        ]
        dir:Path = Path(config.get_str(f"{Context.plugin_name}_routes_directory", Path(Context.plugin_dir) / ROUTE_DIR))
        dir.mkdir(parents=True, exist_ok=True)
        filename:str = filedialog.askopenfilename(filetypes=ftypes, initialdir=dir)
        return filename

    @catch_exceptions
    def read(self, filename:str = '') -> bool:
        """ Import a csv file """
        self.error = ""

        if len(filename) == 0:
            filename = self.choose_file()

        Debug.logger.info(f"Importing route from file: {filename}")
        if len(filename) == 0:
            self.error = errs["no_file"]
            return False

        try:
            with open(filename, 'r', encoding='utf-8-sig', newline='') as csvfile:
                self.roadtoriches = False
                self.fleetcarrier = False

                route_reader:csv.DictReader[str] = csv.DictReader(csvfile)
                # Check it has column headings
                if not route_reader.fieldnames:
                    self.error = errs["empty_file"]
                    Debug.logger.error(f"File {filename} is empty or doesn't have a header row")
                    return False

                fields:list = list(route_reader.fieldnames)
                hasnavroute:bool = 'SystemAddress' in fields and 'StarClass' in fields
                hdrs:list = []
                hdrs = [h for h in fields if h in HEADERS]             # Known headers

                # Append any remaining fields
                for f in fields:
                    if f not in ("SystemAddress", "x", "y", "z", "StarClass") and f not in HEADERS:
                        hdrs.append(f)

                # Need at least the "System Name" header
                if hdrs == [] or "System Name" not in hdrs:
                    self.error = errs["invalid_file"]
                    Debug.logger.error(f"File {filename} is of unsupported format")
                    return False

                # Now build the route
                route:list = []
                navroute:dict = {}
                for row in route_reader:
                    r:list = []
                    if row in (None, "", []): continue
                    for col in hdrs:
                        if col not in row: continue
                        if col in ("body_name", "body_subtype"):
                            r.append(ast.literal_eval(row[col]))
                            continue
                        if re.match(r"^(\d+)$", str(row[col])):
                            r.append(round(int(row[col]), 2))
                            continue
                        if re.match(r"^\d+\.(\d+)?$", str(row[col])):
                            r.append(round(float(row[col]), 2))
                            continue
                        r.append(row[col])
                    route.append(r)

                    if hasnavroute:
                        pos:tuple = (row.get('x'), row.get('y'), row.get('z'))
                        navroute[row["System Name"]] = {
                            'SystemAddress': int(row['SystemAddress']) if row['SystemAddress'] else None,
                            'StarPos': tuple(map(float, pos)) if all(pos) else None,
                            'StarClass': row['StarClass']
                        }

                self.headers = hdrs
                self.route = route
                self.navroute = navroute

                Debug.logger.debug(f"Successfully imported route with {len(route)} rows and headers: {hdrs} {navroute}")
                return True

        except Exception as e:
            self.error = errs["invalid_file"]
            Debug.logger.error(f"Failed to read file {filename}, exception info:", exc_info=e)
            return False


    def write(self, route:Route) -> bool:
        """ Export the route as a csv """

        if not route or route.hdrs == []:
            self.error = errs["no_route"]
            Debug.logger.debug(f"No route")
            return False

        type:str = route.type +" " if hasattr(route, "type") else ""
        ship:str = f" ({route.shipname})" if hasattr(route, "shipname") and route.shipname != "" else ""
        route_name:str = f"{type}{route.source()} to {route.destination()}{ship}"
        ftypes:list = [('CSV files', '*.csv')]
        dir:Path = Path(config.get_str(f"{Context.plugin_name}_routes_directory", Path(Context.plugin_dir) / ROUTE_DIR))
        dir.mkdir(parents=True, exist_ok=True)
        filename:str = filedialog.asksaveasfilename(filetypes=ftypes, initialdir=dir, initialfile=f"{route_name}.csv")

        if len(filename) == 0:
            self.error = errs["no_filename"]
            Debug.logger.debug(f"No filename selected")
            return False

        hdrs:list = route.hdrs.copy()
        rows:list = []

        # Copies, as the route's rows are live; positions only when every stop has one
        if route.navroute:
            nav:list = [route.navroute.get(r[route.sc], {}) for r in route.route]
            sp:bool = all(n.get('StarPos') for n in nav)
            rows = [r + [n.get('SystemAddress', '')] + (list(n['StarPos']) if sp else []) + [n.get('StarClass', '')]
                    for r, n in zip(route.route, nav)]
            hdrs += ['SystemAddress'] + (['x', 'y', 'z'] if sp else []) + ['StarClass']

        if not rows:
            rows = route.route.copy()

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(hdrs)
            for row in rows:
                writer.writerow(row)
        return True


    ### The following is currently unused, but may be useful in the future for displaying bodies to scan in the overlay

    # def update_bodies_text(self) -> None:
    #     if not self.roadtoriches:
    #         return

    #     # For the bodies to scan use the current system, which is one before the next stop
    #     lastsystemoffset:int = Context.route.offset - 1
    #     if lastsystemoffset < 0:
    #         lastsystemoffset = 0    # Display bodies of the first system

    #     lastsystem:str = self.route[lastsystemoffset][0]
    #     bodynames:str = self.route[lastsystemoffset][2]
    #     bodysubtypes:str = self.route[lastsystemoffset][3]

    #     waterbodies:list = []
    #     rockybodies:list = []
    #     metalbodies:list = []
    #     earthlikebodies:list = []
    #     unknownbodies:list = []

    #     for num, name in enumerate(bodysubtypes):
    #         shortbodyname:str = bodynames[num].replace(lastsystem + " ", "")
    #         if name.lower() == "high metal content world":
    #             metalbodies.append(shortbodyname)
    #         elif name.lower() == "rocky body":
    #             rockybodies.append(shortbodyname)
    #         elif name.lower() == "earth-like world":
    #             earthlikebodies.append(shortbodyname)
    #         elif name.lower() == "water world":
    #             waterbodies.append(shortbodyname)
    #         else:
    #             unknownbodies.append(shortbodyname)

    #     bodysubtypeandname:str = ""
    #     if len(metalbodies) > 0:
    #         bodysubtypeandname += "\n   Metal: " + ', '.join(metalbodies)
    #     if len(rockybodies) > 0:
    #         bodysubtypeandname += "\n   Rocky: " + ', '.join(rockybodies)
    #     if len(earthlikebodies) > 0:
    #         bodysubtypeandname += "\n   Earth: " + ', '.join(earthlikebodies)
    #     if len(waterbodies) > 0:
    #         bodysubtypeandname += "\n   Water: " + ', '.join(waterbodies)
    #     if len(unknownbodies) > 0:
    #         bodysubtypeandname += "\n   Unknown: " + ', '.join(unknownbodies)

    #     self.bodies = f"\n{lastsystem}:{bodysubtypeandname}"


    # def plot_edts(self, filename: Path | str) -> None:
    #     """ Currently unused """
    #     try:
    #         with open(filename, 'r') as txtfile:
    #             route_txt:list = txtfile.readlines()
    #             for row in route_txt:
    #                 if row not in (None, "", []):
    #                     if row.lstrip().startswith('==='):
    #                         jumps = int(re.findall(r"\d+ jump", row)[0].rstrip(' jumps'))
    #                         self.jumps_left += jumps

    #                         system:str = row[row.find('>') + 1:]
    #                         if ',' in system:
    #                             systems:list = system.split(',')
    #                             for system in systems:
    #                                 self.route.append([system.strip(), jumps])
    #                                 jumps = 1
    #                                 self.jumps_left += jumps
    #                         else:
    #                             self.route.append([system.strip(), jumps])
    #     except Exception as e:
    #         Debug.logger.error("Failed to parse TXT route file, exception info:", exc_info=e)
    #         Context.ui._show_busy_gui(True)
    #         Context.ui.show_error("An error occured while reading the file.")
