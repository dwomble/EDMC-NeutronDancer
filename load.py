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
    Debug.logger.info(f"Starting (start3) {NAME} version {Context.plugin_version} in {appname}")

    Context.plugin_name = NAME
    Context.plugin_dir = Path(plugin_dir).resolve()
    version_file = Context.plugin_dir / "version"
    Context.plugin_version = Version(version_file.read_text())
    Context.plugin_useragent = f"{GIT_PROJECT}-{Context.plugin_version}"

    Debug.logger.debug(f"Calling check for update")
    Context.updater = Updater(str(Context.plugin_version), str(Context.plugin_dir))
    Context.updater.check_for_update()

    return NAME


@catch_exceptions
def plugin_start(plugin_dir: str) -> None:
    """EDMC calls this function when running in Python 2 mode."""
    raise EnvironmentError(errs["required_version"])



@catch_exceptions
def plugin_stop() -> None:
    Context.router.save()
    #if Context.updater.update_available: Context.updater.install_update()


@catch_exceptions
def journal_entry(cmdr:str, is_beta:bool, system:str, station:str, entry:dict, state:dict) -> None:
    match entry['event']:
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.system = entry.get('StarSystem', system)
            Context.router.update_route()
        case 'StoredShips':
            Context.router.shipyard = entry.get('ShipsHere', []) + entry.get('ShipsRemote', [])
        case 'Loadout':
            Context.router.set_ship(entry.get('ShipID', ''), entry.get('MaxJumpRange', 0.0), entry.get('ShipName', ''), entry.get('Ship', ''))
        case 'ShipyardSwap':
            Context.router.swap_ship(entry.get('ShipID', ''))


@catch_exceptions
def ask_for_update() -> None:
    if Context.updater.update_available:
        update_txt:str = f"{lbls['update_available']}\n{lbls['install_instructions']}\n\n" + \
                    f"{Context.plugin_changelogs}\n\n{lbls['install']}"
        install_update:bool = confirmDialog.askyesno(GIT_PROJECT, update_txt)

        if install_update:
            confirmDialog.showinfo(GIT_PROJECT, lbls['update_confirm'])
            Context.updater.update_available = True
        else:
            Context.updater.update_available = False


@catch_exceptions
def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.router = Router()
    Context.ui = UI(parent)

    Debug.logger.debug(f"Plugin_app")
    #parent.master.after_idle(ask_for_update)
    return Context.ui.frame
