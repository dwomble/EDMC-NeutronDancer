import logging
import os
import tkinter as tk
import tkinter.messagebox as confirmDialog
from pathlib import Path
from semantic_version import Version #type: ignore

from config import appname  # type: ignore

from Router.context import Context, Debug
from Router.router import Router
from Router.ui import UI

NAME="SpanshRouterRedux"

def plugin_start3(plugin_dir: str) -> str:
    # Debug Class
    Debug(plugin_dir)
    Context.plugin_dir = Path(plugin_dir).resolve()
    version_file = Context.plugin_dir / "version"
    Context.plugin_version = Version(version_file.read_text())
    Context.plugin_useragent = f"EDMC-{NAME}-{Context.plugin_version}"
    Context.router = Router()
    Context.router.check_for_update()
    return NAME

def plugin_start(plugin_dir: str) -> None:
    """EDMC calls this function when running in Python 2 mode."""
    raise EnvironmentError("This plugin requires EDMC version 4.0 or later.")


def plugin_stop() -> None:
    Context.router.save_route()
    if Context.router.update_available:
        Context.router.install_update()


def journal_entry(cmdr: str, is_beta: bool, system: str, station: str, entry: dict, state: dict) -> None:
    sys:str = entry.get('StarSystem', '')
    if sys != Context.router.next_stop or sys == Context.system:
        return

    match entry['event']:
        case 'FSDJump' | 'Location' | 'SupercruiseEntry' | 'SupercruiseExit':
            Debug.logger.debug(f"Current system changed: {Context.system} -> {sys}")
            Context.system = sys
            Context.router.update_route()
            Context.ui.set_source_ac(sys)

        case 'FSSDiscoveryScan':
            Debug.logger.debug(f"Current system changed: {Context.system} -> {sys}")
            Context.system = sys
            Context.router.update_route()


def ask_for_update() -> None:
    if Context.router.update_available:
        update_txt = "Update available!\n"
        update_txt += "If you choose to install it, you will have to restart EDMC for it to take effect.\n\n"
        #update_txt += Context.router.spansh_updater.changelogs
        update_txt += "\n\nInstall?"
        install_update = confirmDialog.askyesno("SpanshRouterRedux", update_txt)

        if install_update:
            confirmDialog.showinfo("SpanshRouterRedux", "The update will be installed as soon as you quit EDMC.")
        else:
            Context.router.update_available = False


def plugin_app(parent:tk.Widget) -> tk.Frame:
    Context.router = Router()
    Context.ui = UI(parent)
    Context.router.open_last_route()

    Debug.logger.debug(f"Parent: [{parent}] [{Context.ui}] [{Context.ui.parent}]")
    parent.master.after_idle(ask_for_update)
    return Context.ui.frame
