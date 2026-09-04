"""
Router API module
This module provides an interface for other plugins to interact with the Router plugin.
"""
import json

from .utils.debug import Debug, catch_exceptions
from .context import Context

"""
try:
    import Router.api as router_api
except ImportError:
    router_api = None

# Always check availability before use
if router_api and router_api.is_available():
    navroute = router_api.get_navroute()
else:
    navroute = None
"""

_cached_navroute:dict = {}

def is_available() -> bool:
    """Check if the Router plugin is available."""
    return Context.router is not None

def get_navroute() -> dict:
    """Get the current navigation route."""
    if not is_available():
        raise RuntimeError("Router plugin is not available.")

    if Context.route is None or Context.route.route == []:
        return {
            "event":"NavRouteClear",
            "Route":[ ]
            }

    route:dict = {
        "event":"NavRoute",
        "Route":[]
    }
    for i, waypoint in enumerate(Context.route.route):
        if waypoint[Context.route.sc] not in _cached_navroute:
            star:dict = { "StarSystem":"Blae Hypue CX-F c13-6", "SystemAddress":1734394780786, "StarPos":[755.93750,-332.78125,12307.15625], "StarClass":"K" }
            route["Route"].append(star)
            pass

        route["Route"][i] = _cached_navroute[waypoint[Context.route.sc]]

    return route