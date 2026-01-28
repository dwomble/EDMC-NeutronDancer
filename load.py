import tkinter as tk
from tkinter import ttk
import myNotebook as nb # type: ignore

from pathlib import Path
from semantic_version import Version #type: ignore

from config import appname  # type: ignore

from Router.constants import GH_PROJECT, NAME, errs
from utils.debug import Debug, catch_exceptions
from utils.updater import Updater

from Router.context import Context
from Router.route_manager import Router
from Router.csv import CSV
from Router.ui import UI

def plugin_start3(plugin_dir: str) -> str:
    Debug(plugin_dir)

    Context.plugin_name = NAME
    Context.plugin_dir = Path(plugin_dir).resolve()

    version:Version = Version("0.0.0")
    version_file:Path = Context.plugin_dir / "version"
    if version_file.is_file():
        version = Version(version_file.read_text())
    Context.plugin_version = version
    Context.plugin_useragent = f"{GH_PROJECT}-{version}"
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


def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.csv = CSV()
    Context.router = Router()
    Context.ui = UI(parent)

    return Context.ui.frame


def journal_entry(cmdr:str, is_beta:bool, system:str, station:str, entry:dict, state:dict) -> None:
    match entry['event']:
        case 'Startup':
            Context.router.system = system
        case 'FSDJump' | 'Location' | 'SupercruiseExit' if entry.get('StarSystem', system) != Context.router.system:
            Context.router.system = system
            Context.router.jumped(system, entry)
        case 'CarrierJumpRequest' | 'CarrierLocation' | 'CarrierJumpCancelled':
            Context.router.carrier_event(entry)
        case 'Loadout':
            Context.router.set_ship(entry)
        case 'ShipyardSwap':
            Context.router.swap_ship(entry.get('ShipID', ''))
        case 'Cargo':
            Context.router.cargo = entry.get('Count', 0)


def plugin_prefs(parent:tk.Frame, cmdr: str, is_beta: bool) -> nb.Frame:
    return Context.ui.prefs_frame(parent)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    Context.ui.save_prefs()


def __version__() -> str:
    return str(Context.plugin_version)
