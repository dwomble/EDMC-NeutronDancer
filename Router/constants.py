from enum import Enum, auto
from config import config  # type: ignore

# Project information
TITLE="Navl's Neutron Dancer"
NAME="NeutronDancer"
GH_USER="dwomble"
GH_PROJECT="EDMC-NeutronDancer"

# GIT info and URLs
GH_BASE:str = f"https://github.com/{GH_USER}/{GH_PROJECT}"
GH_RELEASES:str = f"{GH_BASE}/releases"
GH_LATEST:str = f"{GH_RELEASES}/latest"
GH_DOWNLOAD:str = f"{GH_RELEASES}/download"
GH_VERSION:str = f"https://raw.githubusercontent.com/{GH_USER}/{GH_PROJECT}/master/version"
GH_RELEASE_INFO:str = f"https://api.github.com/repos/{GH_USER}/{GH_PROJECT}/releases/latest"
GH_CHANGELOG:str = f"{GH_BASE}/blob/master/CHANGELOG.md#"

# Check for updates at most once per day
UPDATE_CHECK_INTERVAL:int = (3600 * 24)

# Coriolis Modules GH
GH_MODULES:str = "https://raw.githubusercontent.com/Brighter-Applications/coriolis-data/master/modules"

# Spansh URLs
SPANSH_API:str = "https://spansh.co.uk/api"
SPANSH_ROUTE:str = f"{SPANSH_API}/route"
SPANSH_GALAXY_ROUTE:str = f"{SPANSH_API}/generic/route"
SPANSH_RICHES_ROUTE:str = f"{SPANSH_API}/riches/route"
SPANSH_EXOBIOLOGY_ROUTE:str = f"{SPANSH_API}/exobiology/route"
SPANSH_TRADE_ROUTE:str = f"{SPANSH_API}/trade/route"
SPANSH_RESULTS:str = f"{SPANSH_API}/results"
SPANSH_SYSTEMS:str = f"{SPANSH_API}/systems"
SPANSH_STATIONS_NAME:str = f"{SPANSH_API}/stations/field_values/name"  # station name typeahead; results include system_id64
SPANSH_SYSTEM:str = f"{SPANSH_API}/system"  # /{id64} -> full system record, used to resolve a station's system name

# Directory we store our save data in
DATA_DIR = 'data'
SHIP_DIR = 'ships'
ASSET_DIR = 'assets'
ROUTE_DIR = 'routes'

# Font info
FONT:tuple = ("Helvetica", 9, "normal")
BOLD:tuple = ("Helvetica", 9, "bold")

# Map from returned data to our header names
HEADER_MAP:dict = {"system": "System Name", "name": "System Name",
                   "distance_jumped": "Distance Jumped", "distance": "Distance",
                   "distance_left": "Distance Rem", "distance_to_destination": "Distance Rem",
                    "fuel_in_tank": "Fuel Left", "fuel_used": "Fuel Used", "must_refuel": "Refuel",
                    "jumps": "Jumps", "neutron_star": "Neutron", "has_neutron": "Neutron", "is_scoopable": "Scoopable",
                    "body_name": "Body Name", "subtype": "Body Subtype", "is_terraformable": "Is Terraformable",
                    "distance_to_arrival": "Distance To Arrival", "estimated_scan_value": "Estimated Scan Value",
                    "estimated_mapping_value": "Estimated Mapping Value",
                    "species": "Species", "landmark_value": "Landmark Value",
                    "station": "Station Name", "commodity": "Commodity", "amount": "Amount",
                    "profit": "Profit", "total_profit": "Total Profit", "cumulative_profit": "Cumulative Profit",
                    #"x": "", "y": "", "z": "", "id64": ""
                    }

# Headers that we accept
HEADERS:list = ["System Name", "Station Name", "Jumps", "Jumps Rem", "Waypoints", "Waypoints Rem", "Neutron",
                "Body Name", "Body Subtype", "Is Terraformable", "Species", "Landmark Value", "Commodity", "Amount",
                "Profit", "Total Profit", "Cumulative Profit", "Distance To Arrival", "Estimated Scan Value",
                "Estimated Mapping Value", "Distance", "Distance Jumped", "Distance Rem", "Distance Remaining",
                "Fuel Left", "Fuel Used", "Refuel", "Scoopable", "Neutron Star", "Icy Ring", "Pristine", "Restock Tritium"]

# Formatting info for each header
HEADER_TYPES:dict = {"System Name": ["str", ""],
                    "Station Name": ["str", ""],
                    "Commodity": ["str", ""],
                    "Amount": ["int", "", " t"],
                    "Profit": ["float", "", " Cr"],
                    "Total Profit": ["float", "", " Cr"],
                    "Cumulative Profit": ["float", "", " Cr"],
                    "Jumps": ["int", ""],
                    "Jumps Rem": ["int", ""],
                    "Waypoints": ["int", ""],
                    "Waypoints Rem": ["int", ""],
                    "Neutron": ["bool", ""],
                    "Body Name": ["str", ""],
                    "Body Subtype": ["str", ""],
                    "Is Terraformable": ["bool", ""],
                    "Species": ["str", ""],
                    "Landmark Value": ["float", "", " Cr"],
                    "Distance To Arrival": ["float", "", " ls"],
                    "Estimated Scan Value": ["float", "", " Cr"],
                    "Estimated Mapping Value": ["float", "", " Cr"],
                    "Distance": ["float", "", " ly"],
                    "Distance Jumped": ["float", "", " ly"],
                    "Distance Rem": ["float", "", " ly"],
                    "Distance Remaining": ["float", "", " ly"],
                    "Fuel Left": ["float", "", " t"],
                    "Fuel Used": ["float", "", " t"],
                    "Refuel": ["bool", ""],
                    "Scoopable": ["bool", ""],
                    "Neutron Star": ["bool", ""],
                    "Icy Ring": ["bool", ""],
                    "Pristine": ["bool", ""],
                    "Restock Tritium": ["bool", ""]
                }

# Different ways a file might store true/false
TRUE:list = [True, "True", "true", "YES", "Yes", "yes", 1, "1"]
FALSE:list = [False, "False", "false", "NO", "No", "no", 0, "0"]

# Overlay progress display default
OVERLAY_PROGRESS_DEFAULT = "{st} refuel in {rj} jumps\n{jc} / {jt} jumps, {dc} / {dt} ly, {dr} ly remaining\n{jh} jumps/hr, {dh} ly/hr"
class CarrierStates(Enum):
    Idle = auto()
    Jumping = auto()
    Cooldown = auto()

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
    "help": "Help",
    "route": "Route",
    "plot_title": "I'm just burnin'…",
    "plotter": "Neutron Dancer v{version}",
    "no_route": "No route planned",
    "jumps_remaining": "Remaining",
    "body_count": "Bodies to scan at",
    "restock_tritium": "Time to restock Tritium",
    "source_system": "Source System",
    "dest_system": "Destination System",
    "supercharge_label": "Supercharge Multiplier",
    "standard_supercharge": "Standard (x4)",
    "overcharge_supercharge": "Overcharge (x6)",
    "clear_route_yesno": "Are you sure you want to clear the current route?",
    "route_complete": "End of the road!",
    "update_available": "Version {v} will be installed on exit. Click to cancel.",
    "jump": "jump",
    "jumps": "jumps",
    "range": "Ship Range",
    "waypoints": "waypoints",
    "distance": "distance",
    "total_distance": "Total Distance",
    "neutron_router": "Neutron Plotter",
    "galaxy_router": "Galaxy Plotter",
    "cargo": "Cargo",
    "fuel_reserve": "Fuel Reserve",
    "radius": "Search Radius",
    "max_results": "Maximum Systems",
    "min_landmark_value": "Minimum Landmark (Species) Value (M)",
    "station": "Station",
    "starting_capital": "Starting Capital",
    "max_cargo": "Maximum Cargo Capacity",
    "max_hops": "Maximum Hops",
    "max_hop_distance": "Maximum Hop Distance",
    "max_system_distance": "Maximum Distance To Arrival",
    "max_price_age": "Maximum Market Age (days)",
    "requires_large_pad": "Requires Large Pad",
    "allow_prohibited": "Allow Prohibited",
    "allow_planetary": "Allow Planetary",
    "allow_player_owned": "Allow Player Owned",
    "allow_restricted_access": "Allow Restricted Access",
    "unique": "Unique",
    "permit": "Permit",
    "is_supercharged": "Already Supercharged",
    "use_supercharge": "Use Supercharge",
    "use_injections": "Use FSD Injections",
    "exclude_secondary": "Exclude Secondary Stars",
    "refuel_every_scoopable": "Refuel Every scoopable",
    "use_mapping_value": "Use Mapping Value",
    "avoid_thargoids": "Avoid Thargoids",
    "loop": "Loop",
    "cooldown_complete": "Carrier cooldown completed",
    "plotting": "Plotting route from {s} to {d}",
    "progress": "Progress",
    "speed": "Speed",
    "jumps_per_hour": " jumps/hr",
    "dist_per_hour": " ly/hr",
    "refuel": "Refuel",
    "carrier_jumping": "Carrier Jump Scheduled",
    "carrier_cooldown": "Carrier Cooldown",
    "next_refuel": "Refuel in {r}",
    "refuel_now": "Refuel now!",
    "overlays": "Overlays",
    "router": "Router"
}

# Tooltips
tts:dict = {
    'route_type': "The router to plot",
    'neutron_plotter': "Spansh Neutron Plotter",
    'galaxy_plotter': "Spansh Exact/Galaxy Plotter",
    'help': "Help and user guide",
    'source_system': "Source system name, right click for menu",
    'dest_system': "Destination system name, right click for menu",
    "range": "Ship jump range in light years, right click for menu",
    "efficiency": "Routing efficiency (%)",
    "standard_multiplier": "Standard range increase (4x), right click for menu",
    "overcharge_multiplier": "Caspian range increase( 6x), right click for menu",
    "copy_to_clipboard": "Click to copy to clipboard",
    "jump": "{j} jumps {d}remaining.",
    "waypoints": "{j} waypoints {d}remaining.",
    "speed": "{j} jumps per hour, {d} Ly/hour",
    "releasenotes": "Release notes:\n{c}",
    "select_ship": "Select ship for which to plot route",
    "galaxy_options": "Galaxy plotter options (see help page for details)",
    "cargo": "Tonnes of cargo carried",
    "calc_time": "How long to spend calculating route",
    "select_algorithm": "Select routing algorithm, see spansh.co.uk for details",
    "fuel_reserve": "Amount of fuel (in Tonnes) to keep in reserve before refueling",
    "radius": "Search radius in light years, right click for menu",
    "max_results": "Maximum number of systems to include in the route",
    "min_landmark_value": "Minimum landmark (species) value to look for, in millions of credits",
    "station": "Departure station -- start typing to search",
    "starting_capital": "Credits available to spend on cargo",
    "max_cargo": "Maximum cargo capacity in tonnes",
    "max_hops": "Maximum number of trade hops in the route",
    "max_hop_distance": "Maximum jump distance per hop, in light years",
    "max_system_distance": "Maximum distance of a station from its arrival point, in light seconds",
    "max_price_age": "Ignore market prices older than this many days. Leave blank for no limit",
    "requires_large_pad": "Only include stations with a large landing pad",
    "allow_prohibited": "Allow commodities prohibited by the destination's superpower",
    "allow_planetary": "Allow planetary stations",
    "allow_player_owned": "Allow player-owned fleet carriers as stops",
    "allow_restricted_access": "Allow stations with restricted access (e.g. engineer bases)",
    "unique": "Only visit each station once",
    "permit": "Allow systems that require a permit",
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
    "no_route": "No current route",
    "empty_file": "File is empty or doesn't have a header row",
    "invalid_file": "File is corrupt or of unsupported format",
    "no_filename": "No filename given",
    "parse_error": "Error parsing route file",
    "no_ships": "You must have switched ships for the plotter to receive your ship details",
    "no_ship": "No ship selected",
    "no_station": "Station not found -- start typing to search",
    "format_error": "Error formatting progress display"
}

cnf:dict = {
    "version": "Version",
    "overlays": "Overlays",
    "enable": "Enable",
    "foreground": "Foreground",
    "controller": "To change overlay frame positions, set backgrounds etc. use Modern Overlay's controller",
    "default_overlay": "Default Overlay Options",
    "progress_bar": "Progress Bar",
    "progress_display": "Progress Display",
    "options": "Neutron Dancer Options",
    "select": "Select",
    "show_carrier_cooldown": "Show Carrier Cooldown Popup",
    "routes_directory": "Default Route File Directory"
}

ovr:dict = {
    "jump": "Carrier jump to {d} in {t}",
    "cooldown": "Carrier cooldown {t}",
    "neutron": "Neutron Boost Here",
    "refuel": "Refuel Here"
}