import logging
import os
import tkinter as tk
import tkinter.messagebox as confirmDialog
from pathlib import Path
from semantic_version import Version #type: ignore

from config import appname  # type: ignore

from Router.constants import GIT_PROJECT, NAME, errs, lbls
from utils.Debug import Debug, catch_exceptions

from Router.updater import Updater
from Router.context import Context
from Router.router import Router
from Router.ui import UI


@catch_exceptions
def plugin_start3(plugin_dir: str) -> str:
    # Debug Class
    Debug(plugin_dir)
    Debug.logger.info(f"Starting (start3) {NAME} in {appname}")

    Context.plugin_name = NAME
    Context.plugin_dir = Path(plugin_dir).resolve()
    version_file:Path = Context.plugin_dir / "version"
    version:str = "Development"
    if version_file.is_file():
        version = str(Version(version_file.read_text()))

    Context.plugin_useragent = f"{GIT_PROJECT}-{version}"
    Context.updater = Updater(str(Context.plugin_dir))
    if version_file.is_file():
        Context.updater.check_for_update(version)

    return NAME


@catch_exceptions
def plugin_start(plugin_dir: str) -> None:
    """EDMC calls this function when running in Python 2 mode."""
    raise EnvironmentError(errs["required_version"])


@catch_exceptions
def plugin_stop() -> None:
    Context.router.save()
    # Auto updates are currently disabled.
    #if Context.updater.install_update:
    #    Context.updater.install()


@catch_exceptions
def journal_entry(cmdr:str, is_beta:bool, system:str, station:str, entry:dict, state:dict) -> None:
    match entry['event']:
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.system = entry.get('StarSystem', system)
            Context.router.update_route()
        case 'CarrierJump' if entry.get('Docked', True) == True:
            Context.router.system = entry.get('StarSystem', system)
            Context.router.update_route()
        case 'StoredShips':
            Context.router.shipyard = entry.get('ShipsHere', []) + entry.get('ShipsRemote', [])
        case 'Loadout':
            Context.router.set_ship(entry.get('ShipID', ''), entry.get('MaxJumpRange', 0.0), entry.get('ShipName', ''), entry.get('Ship', ''))
        case 'ShipyardSwap':
            Context.router.swap_ship(entry.get('ShipID', ''))


@catch_exceptions
def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.router = Router()
    Context.ui = UI(parent)

    Debug.logger.debug(f"Plugin_app")

    return Context.ui.frame
