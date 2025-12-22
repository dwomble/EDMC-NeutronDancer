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
SPANSH_RESULTS:str = f"{SPANSH_API}/results"

# Directory we store our save data in
DATA_DIR = 'data'

# Map from returned data to our header names
HEADER_MAP:dict = {"System Name": "system", "Distance Jumped": "distance_jumped", "Distance Rem": "distance_left",
                "Jumps": "jumps", "Neutron": "neutron_star"}

# Headers that we accept
HEADERS:list = ["System Name", "Jumps", "Jumps Rem", "Neutron", "Body Name", "Body Subtype",
                "Is Terraformable", "Distance To Arrival", "Estimated Scan Value", "Estimated Mapping Value",
                "Distance", "Distance Jumped", "Distance Rem", "Distance Remaining", "Fuel Left", "Fuel Used", "Refuel", "Neutron Star",
                "Icy Ring", "Pristine", "Restock Tritium"]


"""
Output strings
"""

# Headers
hdrs:dict = {
    "restock_tritium": "Restock Tritium",
    "jumps": "Jumps",
    "system_name": "System Name",
    "body_subtype": "Body Subtype",
    "body_name": "Body Name",
}

# Text labels
lbls:dict = {
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
    "jumps": "jumps"
}

# Tooltips
tts:dict = {
    'source_system': "Source system name, right click for menu",
    'dest_system': "Destination system name, right click for menu",
    "range": "Ship jump range in light years, right click for menu",
    "efficiency": "Routing efficiency (%), right click for menu",
    "standard_multiplier": "Standard range increase (4x), right click for menu",
    "overcharge_multiplier": "Caspian range increase( 6x), right click for menu",
    "jump": "Click to copy to clipoard.\n{j} jumps {d}remaining.",
    "releasenotes": "Release notes:\n{c}"
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
    "clear_route": "Clear route",
    "show_route": "Show route",
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
