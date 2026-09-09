"""
Router API module
This module provides an interface for other plugins to interact with the Router plugin.

Initial method is a NavRoute compatible list of waypoints.

    try:
        import Router.api as router_api
    except ImportError:
        router_api = None

    # Always check availability before use
    if not router_api or not router_api.is_available():
        return None

    return router_api.get_navroute()
"""
from .context import Context

def is_available() -> bool:
    """ Check if the Router plugin is available. """
    return Context.router is not None

def get_navroute() -> list|None:
    """ Return the current route in a NavRoute style list. """
    if not is_available():
        raise RuntimeError("Router plugin is not available.")

    if Context.route is None or Context.route.route == [] or Context.route.sc is None:
        return None

    route:list = []
    for waypoint in Context.route.route:
        name:str = waypoint[Context.route.sc]

        nav:dict = Context.route.navroute.get(name, {})
        route.append({"StarSystem": name,
                      "SystemAddress": nav.get('SystemAddress'),
                      "StarPos": nav.get('StarPos'),
                      "StarClass": nav.get('StarClass') or '',
        })

    return route