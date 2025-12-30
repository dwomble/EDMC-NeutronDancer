import ast
import csv
import os
from pathlib import Path
from tkinter import filedialog
import re

from .constants import HEADERS, errs
from utils.debug import Debug, catch_exceptions
from .context import Context

class CSV:
    """
    Class to import and export routes as CSV files
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
        self.roadtoriches:bool
        self.fleetcarrier:bool
        self.headers:list
        self.route:list
        self.error:str = ""

        self._initialized = True


    @catch_exceptions
    def read(self) -> bool:
        """ Import a csv file """
        self.error = ""

        ftypes:list = [
            ('All supported files', '*.csv *.txt'),
            ('CSV files', '*.csv'),
            ('Text files', '*.txt'),
        ]
        filename:str = filedialog.askopenfilename(filetypes=ftypes, initialdir=os.path.expanduser('~'))

        if len(filename) == 0:
            self.error = errs["no_file"]
            Debug.logger.debug(f"No filename selected")
            return False

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
            hdrs:list = []
            hdrs = [h for h in HEADERS if h in fields]

            # Append any remaining fields
            for f in fields:
                if f not in HEADERS:
                    hdrs.append(f)

            Debug.logger.debug(f"Fields: {fields} hdrs: {hdrs}")
            if hdrs == [] or "System Name" not in hdrs:
                self.error = errs["invalid_file"]
                Debug.logger.error(f"File {filename} is of unsupported format")
                return False

            route:list = []
            for row in route_reader:
                r:list = []
                if row in (None, "", []): continue
                for col in hdrs:
                    Debug.logger.debug(f"{col} {row[col]}")
                    if col not in row: continue
                    if col in ["body_name", "body_subtype"]:
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

            self.fleetcarrier = True if "Fuel Used" in hdrs else False
            self.roadtoriches = True if "Estimated Scan Value" in hdrs else False
            Debug.logger.debug(f"Headers: {hdrs} rows {len(route)}")
            self.headers = hdrs
            self.route = route
            return True


    def write(self, headers:list, route:list) -> bool:
        """ Export the route as a csv """

        if route == [] or headers == []:
            Debug.logger.debug(f"No route")
            return False

        route_start:str = route[0][0]
        route_end:str = route[-1][0]
        route_name:str = f"{route_start} to {route_end}"
        ftypes:list = [('CSV files', '*.csv')]
        filename:str = filedialog.asksaveasfilename(filetypes=ftypes, initialdir=os.path.expanduser('~'), initialfile=f"{route_name}.csv")

        if len(filename) == 0:
            self.error = errs["no_filename"]
            Debug.logger.debug(f"No filename selected")
            return False

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for row in route:
                writer.writerow(row)
        return True


    def update_bodies_text(self) -> None:
        if not self.roadtoriches:
            return

        # For the bodies to scan use the current system, which is one before the next stop
        lastsystemoffset:int = Context.route.offset - 1
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


    def plot_edts(self, filename: Path | str) -> None:
        """ Currently unused """
        try:
            with open(filename, 'r') as txtfile:
                route_txt:list = txtfile.readlines()
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
            Context.ui._show_busy_gui(True)
            Context.ui.show_error("An error occured while reading the file.")
