
from pathlib import Path
from semantic_version import Version #type: ignore
import tkinter as tk

import myNotebook as nb  #type: ignore
import edmc_data # type: ignore

from Router.constants import GH_PROJECT, NAME, TITLE, errs, CarrierStates
from utils.debug import Debug, catch_exceptions
from utils.updater import Updater
from utils.misc import copy_to_clipboard

from Router.context import Context
from Router.route_manager import Router
from Router.csv import CSV
from Router.ui import UI
from Router.overlay import Overlay
from Router.hotkeys import Hotkeys
from Router.prefs import Prefs

def plugin_start3(plugin_dir: str) -> str:
    Debug(plugin_dir)

    Context.plugin_name = NAME
    Context.plugin_title = TITLE
    Context.plugin_dir = Path(plugin_dir).resolve()

    version:Version = Version("0.0.0")
    version_file:Path = Context.plugin_dir / "version"
    if version_file.is_file():
        version = Version(version_file.read_text())
    Context.plugin_version = version
    Context.plugin_useragent = f"{GH_PROJECT}-{version}"
    Context.updater = Updater(str(Context.plugin_dir))
    Context.updater.check_for_update(Context.plugin_version, Context.plugin_name)

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
        Context.updater.install()

def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.prefs = Prefs()
    Context.csv = CSV()
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
        case 'Startup':
            Context.router.carrier_state = CarrierStates.Idle
            if Context.route.route != [] and not Context.route.fleetcarrier:
                Context.route.update_route(0, system)
                Context.route.jumps = []
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.jumped(system, entry)
        case 'CarrierJumpRequest' | 'CarrierLocation' | 'CarrierJumpCancelled' | 'CarrierStats':
            Context.router.carrier_event(entry)
        case 'Loadout':
            Context.router.set_ship(entry)
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

    Context.router.system = system
    cargo:int = sum(state.get('Cargo', {}).values())
    if cargo != Context.router.cargo:
        Context.router.cargo = cargo
        Context.ui.update_cargo(cargo)


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
