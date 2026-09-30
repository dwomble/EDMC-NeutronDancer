
from pathlib import Path
from semantic_version import Version
import json
import tkinter as tk

import myNotebook as nb  # type: ignore
from config import user_agent # type: ignore
from monitor import monitor # type: ignore
import edmc_data # type: ignore

from Router.constants import GH_USER, GH_PROJECT, GH_MAIN, NAME, TITLE, errs, CarrierStates
from Router.utils.debug import Debug, catch_exceptions
from Router.utils.updater import Notices, Updater, read_version_file
from Router.utils.misc import copy_to_clipboard

from Router.context import Context
from Router.route_manager import Router
from Router.csv import CSV
from Router.ui import UI
from Router.overlay import Overlay
from Router.hotkeys import Hotkeys
from Router.prefs import Prefs
from Router.spansh_data import SpanshData

def plugin_start3(plugin_dir: str) -> str:
    Debug(plugin_dir, True)

    Context.plugin_name = NAME
    Context.plugin_title = TITLE
    Context.plugin_dir = Path(plugin_dir).resolve()

    version:Version = read_version_file(str(Context.plugin_dir), "0.0.0")
    Context.plugin_version = version
    VERSION:str = version.__str__() # For the plugin browser
    Context.plugin_useragent = f'{user_agent} {NAME}-{VERSION}'
    Context.updater = Updater(str(Context.plugin_dir), GH_USER, GH_PROJECT)
    Context.updater.check_for_update(Context.plugin_version)

    Context.notices = Notices(GH_USER, GH_PROJECT, GH_MAIN)
    Context.notices.check_for_notices()

    return NAME

@catch_exceptions
def plugin_start(plugin_dir: str) -> None:
    """EDMC calls this function when running in Python 2 mode."""
    raise EnvironmentError(errs["required_version"])


@catch_exceptions
def plugin_stop() -> None:
    Context.router.save()
    Context.overlay.stop_countdowns()
    if Context.updater.install_update:
        Context.updater.install(["data"])

def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.prefs = Prefs()
    Context.csv = CSV()
    Context.spansh = SpanshData() # before Router(), which may load a saved route and trigger a fetch
    Context.router = Router()
    Context.ui = UI(parent)
    Context.hotkeys = Hotkeys()
    Context.overlay = Overlay()
    if Context.route.route != []:
        Context.overlay.show_frame('Default')

    parent.after(1000, Context.overlay.update_overlays)
    return Context.ui.frame

@catch_exceptions
def journal_entry(cmdr:str, is_beta:bool, system:str, station:str, entry:dict, state:dict) -> None:
    if Context.router == None: return

    match entry['event']:
        case 'Startup' | 'StartUp':
            Context.router.carrier_state = CarrierStates.Idle
            if Context.route.route != [] and not Context.route.fleetcarrier:
                Context.route.update_route(0, system)
                Context.route.jumps = []
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.jumped(system, entry)
        case 'CarrierJumpRequest' | 'CarrierLocation' | 'CarrierJumpCancelled' | 'CarrierStats':
            Context.router.carrier_event(entry)
        case 'Loadout':
            Context.router.add_loadout(entry)
        case 'ShipyardSwap':
            Context.router.swap_ship(entry.get('ShipID', ''))
        case 'SendText':
            if entry.get('Message', '').startswith("!nd "):
                match entry.get('Message', '')[4:]:
                    case "prev" | "previous":
                        Context.router.update_route(-1)
                    case "next":
                        Context.router.update_route(1)
                    case _:
                        copy_to_clipboard(Context.ui.parent, Context.route.next_system())
        case 'Refueling': # Read fuel from Status.json
            Context.router.fuel_event(state)
        case 'Shutdown':
            if Context.route.route != []: Context.route.jumps = []
            Context.router.save()

    # EDMC is annoying. the ship() object doesn't include all the details of the ship so have to either parse
    # the internal slef string or add elements from state.
    if entry['event'] in ('Commander', 'LoadGame', 'StartUp'):
        loadout:dict = make_loadout(state)
        if loadout:
            Context.router.add_loadout(loadout)

    Context.router.system = system
    cargo:int = sum(state.get('Cargo', {}).values())
    if cargo != Context.router.cargo:
        Context.router.cargo = cargo
        Context.ui.update_cargo(cargo)


def make_loadout(state:dict) -> dict:
    """ Build a loadout event to identify a ship """
    loadout:dict = {}
    if monitor.slef:
        Debug.logger.debug(f"Making loadout from monitor.slef")
        slef:list = json.loads(monitor.slef)
        loadout = slef[0]['data']

    if not loadout and monitor.ship():
        Debug.logger.debug(f"Making loadout from monitor.ship() and state")
        loadout = monitor.ship()

    # Add any missing values that we can
    if loadout:
        for f in ['UnladenMass', 'ShipID', 'ShipType', 'HullValue', 'ModulesValue', 'UnladenMass', 'CargoCapacity', 'MaxJumpRange',   'FuelCapacity', ]:
            if f not in loadout:
                loadout[f] = state.get(f)

    if loadout:
        loadout['event'] = 'Loadout'

    return loadout

@catch_exceptions
def dashboard_entry(cmdr:str, is_beta:bool, entry:dict) -> None:
    if Context.ui.parent and Context.route.jumps_remaining() and entry.get("GuiFocus") == edmc_data.GuiFocusGalaxyMap:
        copy_to_clipboard(Context.ui.parent, Context.route.next_system())

    if Context.overlay:
        Context.overlay.dashboard_entry(cmdr, is_beta, entry)

@catch_exceptions
def plugin_prefs(parent:tk.Frame, cmdr: str, is_beta: bool) -> nb.Frame:
    return Context.prefs.prefs_frame(parent)

@catch_exceptions
def prefs_changed(cmdr: str, is_beta: bool) -> None:
    Context.prefs.save_prefs()
