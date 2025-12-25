import tkinter as tk
from pathlib import Path
from semantic_version import Version #type: ignore

from config import appname  # type: ignore

from Router.constants import GIT_PROJECT, NAME, errs, lbls
from utils.Debug import Debug, catch_exceptions
from utils.Updater import Updater
from utils.misc import get_by_path

from Router.context import Context
from Router.router import Router
from Router.csv import CSV
from Router.ui import UI


def plugin_start3(plugin_dir: str) -> str:
    # Debug Class
    Debug(plugin_dir)

    Context.plugin_name = NAME
    Context.plugin_dir = Path(plugin_dir).resolve()

    version:Version = Version("0.0.0")
    version_file:Path = Context.plugin_dir / "version"
    if version_file.is_file():
        version = Version(version_file.read_text())
    Context.plugin_version = version
    Context.plugin_useragent = f"{GIT_PROJECT}-{version}"
    Context.updater = Updater(str(Context.plugin_dir))
    Context.updater.check_for_update(Context.plugin_version)

    return NAME


def plugin_start(plugin_dir: str) -> None:
    """EDMC calls this function when running in Python 2 mode."""
    raise EnvironmentError(errs["required_version"])


def plugin_stop() -> None:
    Context.router.save()
    if Context.updater.install_update:
        Context.updater.install()


def journal_entry(cmdr:str, is_beta:bool, system:str, station:str, entry:dict, state:dict) -> None:
    match entry['event']:
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.system = entry.get('StarSystem', system)
            Context.router.update_route()
        case 'CarrierJump' if entry.get('Docked', True) == True:
            Context.router.system = entry.get('StarSystem', system)
            Context.router.update_route()
        #case 'StoredShips':
        #    Context.router.shipyard = entry.get('ShipsHere', []) + entry.get('ShipsRemote', [])
        case 'Loadout':
            Context.router.set_ship(entry)
        case 'ShipyardSwap':
            Context.router.swap_ship(entry.get('ShipID', ''))


def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.router = Router()
    Context.csv = CSV()
    Context.ui = UI(parent)

    return Context.ui.frame
