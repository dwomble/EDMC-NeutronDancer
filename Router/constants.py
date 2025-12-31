from config import config  # type: ignore

# Project information
NAME="Navl's Neutron Dancer"
GIT_USER="dwomble"
GIT_PROJECT="EDMC-NeutronDancer"

# GIT info and URLs
GIT_LATEST:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/releases/latest"
GIT_DOWNLOAD:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/releases/download"
GIT_VERSION:str = f"https://raw.githubusercontent.com/{GIT_USER}/{GIT_PROJECT}/master/version"
GIT_RELEASE_INFO:str = f"https://api.github.com/repos/{GIT_USER}/{GIT_PROJECT}/releases/latest"
GIT_CHANGELOG:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/blob/master/CHANGELOG.md#"

# Spansh URLs
SPANSH_API:str = "https://spansh.co.uk/api"
SPANSH_ROUTE:str = f"{SPANSH_API}/route"
SPANSH_GALAXY_ROUTE:str = f"{SPANSH_API}/generic/route"
SPANSH_RESULTS:str = f"{SPANSH_API}/results"
SPANSH_SYSTEMS:str = f"{SPANSH_API}/systems"

# Directory we store our save data in
DATA_DIR = 'data'
ASSET_DIR = 'assets'
ROUTE_DIR = 'routes'

FONT = ("Helvetica", int(9*config.get_int('ui_scale') / 100.00), "normal")
BOLD = ("Helvetica", int(9*config.get_int('ui_scale') / 100.00), "bold")

# Map from returned data to our header names
#HEADER_MAP:dict = {"System Name": "system", "Distance Jumped": "distance_jumped", "Distance Rem": "distance_left",
#                "Jumps": "jumps", "Neutron": "neutron_star", "Refuel": "must_refuel"}

HEADER_MAP:dict = {"system": "System Name", "name": "System Name",
                   "distance_jumped": "Distance Jumped", "distance": "Distance",
                   "distance_left": "Distance Rem", "distance_to_destination": "Distance Rem",
                    "fuel_in_tank": "Fuel Left", "fuel_used": "Fuel Used", "must_refuel": "Refuel",
                    "jumps": "Jumps", "neutron_star": "Neutron", "has_neutron": "Neutron", "is_scoopable": "Scoopable",
                    #"x": "", "y": "", "z": "", "id64": ""
                    }


# Headers that we accept
HEADERS:list = ["System Name", "Jumps", "Jumps Rem", "Waypoints", "Waypoints Rem", "Neutron", "Body Name", "Body Subtype",
                "Is Terraformable", "Distance To Arrival", "Estimated Scan Value", "Estimated Mapping Value",
                "Distance", "Distance Jumped", "Distance Rem", "Distance Remaining", "Fuel Left", "Fuel Used",
                "Refuel", "Scoopable", "Neutron Star", "Icy Ring", "Pristine", "Restock Tritium"]

# Formatting info for each header
HEADER_TYPES:dict = {"System Name": ["str", ""],
                    "Jumps": ["int", ""],
                    "Jumps Rem": ["int", ""],
                    "Waypoints": ["int", ""],
                    "Waypoints Rem": ["int", ""],
                    "Neutron": ["bool", ""],
                    "Body Name": ["str", ""],
                    "Body Subtype": ["str", ""],
                    "Is Terraformable": ["bool", ""],
                    "Distance To Arrival": ["float", "", " Ls"],
                    "Estimated Scan Value": ["float", "", " Cr"],
                    "Estimated Mapping Value": ["float", "", " Cr"],
                    "Distance": ["float", "", " Ly"],
                    "Distance Jumped": ["float", "", " Ly"],
                    "Distance Rem": ["float", "", " Ly"],
                    "Distance Remaining": ["float", "", " Ly"],
                    "Fuel Left": ["float", "", " T"],
                    "Fuel Used": ["float", "", " T"],
                    "Refuel": ["bool", ""],
                    "Scoopable": ["bool", ""],
                    "Neutron Star": ["bool", ""],
                    "Icy Ring": ["bool", ""],
                    "Pristine": ["bool", ""],
                    "Restock Tritium": ["bool", ""]
                }

"""
Output strings
"""

# Headers
hdrs:dict = {
    "restock_tritium": "Restock Tritium",
    "jumps": "Jumps",
    "system_name": "System Name",
    "body_subtype": "Body Subtype",
    "body_name": "Body Name"
}

# Text labels
lbls:dict = {
    "warning": "Warning",
    "route": "Route",
    "plot_title": "I'm just burnin'…",
    "no_route": "No route planned",
    "jumps_remaining": "Remaining",
    "body_count": "Bodies to scan at",
    "restock_tritium": "Time to restock Tritium",
    "source_system": "Source System",
    "dest_system": "Destination System",
    "range": "Range (LY)",
    "supercharge_label": "Supercharge Multiplier",
    "standard_supercharge": "Standard (x4)",
    "overcharge_supercharge": "Overcharge (x6)",
    "plotting_route": "Plotting route...",
    "clear_route_yesno": "Are you sure you want to clear the current route?",
    "route_complete": "End of the road!",
    "update_available": "Version {v} will be installed on exit. Click to cancel.",
    "jump": "jump",
    "jumps": "jumps",
    "distance": "distance",
    "total_distance": "Total Distance",
    "neutron_router": "Neutron Plotter",
    "galaxy_router": "Galaxy Plotter",
    "cargo": "Cargo",
    "fuel_reserve": "Fuel Reserve",
    "is_supercharged": "Already Supercharged?",
    "use_supercharge": "Use Supercharge?",
    "use_injections": "Use FSD Injections?",
    "exclude_secondary": "Exclude Secondary Stars?",
    "refuel_every_scoopable": "Refuel Every scoopable?",
    "plotting": "Plotting route",
    "progress": "Progress",
    "speed": "Speed",
    "jumps_per_hour": "Jumps/hr",
    "dist_per_hour": "Ly/hr"
}

# Tooltips
tts:dict = {
    'source_system': "Source system name, right click for menu",
    'dest_system': "Destination system name, right click for menu",
    "range": "Ship jump range in light years, right click for menu",
    "efficiency": "Routing efficiency (%), right click for menu",
    "standard_multiplier": "Standard range increase (4x), right click for menu",
    "overcharge_multiplier": "Caspian range increase( 6x), right click for menu",
    "copy_to_clipboard": "Click to copy to clipboard",
    "jump": "{j} jumps {d}remaining.",
    "waypoints": "{j} waypoints {d}remaining.",
    "speed": "{j} jumps per hour, {d} Ly/hour",
    "releasenotes": "Release notes:\n{c}",
    "select_ship": "Select ship for which to plot route",
    "galaxy_options": "Galaxy plotter options (see Spansh for details)",
    "cargo": "Tonnes of cargo carried",
    "calc_time": "How long to spend calculating route",
    "select_algorithm": "Select routing algorithm, see spansh.co.uk for details",
    "fuel_reserve": "Amount of fuel (in Tonnes) to keep in reserve before refueling",
    "progress": "Progress",
    "none": "None"
}

# Button names
btns:dict = {
    "prev": "⋖",
    "next": "⋗",
    "next_wp": "Next waypoint ?",
    "plot_route": "do the neutron dance",
    "import_route": "Import",
    "calculate_route": "Calculate",
    "cancel": "Cancel",
    "import_file": "Import file",
    "export_route": "Export for TCE",
    "clear_route": "Clear",
    "show_route": "Show",
    "export_route": "Export"
}

# Error messages
errs:dict = {
    "plot_error": "Error while trying to plot a route, please try again.",
    "required_version": "This plugin requires EDMC version 4.0 or later.",
    "invalid_range": "Invalid range",
    "no_response": "No response from server",
    "no_file": "No file selected",
    "empty_file": "File is empty or doesn't have a header row",
    "invalid_file": "File is corrupt or of unsupported format",
    "no_filename": "No filename given",
    "parse_error": "Error parsing route file",
}
