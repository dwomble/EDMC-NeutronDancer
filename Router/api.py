"""
Router API module
This module provides an interface for other plugins to interact with the Router plugin.

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
from .context import Context

def is_available() -> bool:
    """Check if the Router plugin is available."""
    return Context.router is not None

def get_navroute() -> dict:
    """Get the current navigation route, NavRoute.json-shaped. """
    if not is_available():
        raise RuntimeError("Router plugin is not available.")

    if Context.route is None or Context.route.route == [] or Context.route.sc is None:
        return {"event": "NavRouteClear", "Route": []}

    route:dict = {"event": "NavRoute", "Route": []}
    for waypoint in Context.route.route:
        name:str = waypoint[Context.route.sc]
        nav:dict = Context.route.navroute.get(name, {})
        route["Route"].append({
            "StarSystem": name, "SystemAddress": nav.get('SystemAddress'),
            "StarPos": nav.get('StarPos'), "StarClass": nav.get('StarClass') or '',
        })

    return route