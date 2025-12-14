NAME="Navl's Neutron Dancer"

GIT_USER="dwomble"
GIT_PROJECT="EDMC-NeutronDancer"
GIT_LATEST:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/releases/latest"
GIT_DOWNLOAD:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/releases/download"
GIT_VERSION:str = f"https://raw.githubusercontent.com/{GIT_USER}/{GIT_PROJECT}/master/version"
GIT_CHANGELOG_LIST:str = f"https://api.github.com/repos/{GIT_USER}/{GIT_PROJECT}/releases/latest"
GIT_CHANGELOG:str = f"https://github.com/{GIT_USER}/{GIT_PROJECT}/blob/master/CHANGELOG.md#"

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
                "Distance", "Distance Jumped", "Distance Rem", "Fuel Used", "Icy Ring", "Pristine", "Restock Tritium"]

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
    "plot_title": "I'm just burnin'…",
    "no_route": "No route planned",
    "jumps_remaining": "Remaining",
    "body_count": "Bodies to scan at",
    "restock_tritium": "Time to restock Tritium",
    "plot_error": "Error while trying to plot a route, please try again.",
    "source_system": "Source System",
    "dest_system": "Destination System",
    "range": "Range (LY)",
    "supercharge_label": "Supercharge Multiplier",
    "standard_supercharge": "Standard (x4)",
    "overcharge_supercharge": "Overcharge (x6)",
    "clear_route_yesno": "Are you sure you want to clear the current route?",
    "route_complete": "End of the road!",
    #"update_available": "Version {v} will be installed on exit. Click to cancel.",
    "update_available": "New version available: {v}",
    "jump": "jump",
    "jumps": "jumps"
}

# Tooltips
tts:dict = {
    'source_system': "Source system name, right click for menu",
    'dest_system': "Destination system name, right click for menu",
    "range": "Ship jump range in light years, right click for menu",
    "efficiency": "Routing efficiency (%)",
    "jump": "Click to copy to clipoard.\nJumps remaining in route",
}

# Button names
btns:dict = {
    "prev": "⋖",
    "next": "⋗",
    "next_wp": "Next waypoint ?",
    "plot_route": "do the neutron dance",
    "calculate_route": "Calculate",
    "cancel": "Cancel",
    "import_file": "Import file",
    "export_route": "Export for TCE",
    "clear_route": "Clear route",
    "show_route": "Show route",
}

# Error messages
errs:dict = {
    "required_version": "This plugin requires EDMC version 4.0 or later.",
    "invalid_range": "Invalid range"
}