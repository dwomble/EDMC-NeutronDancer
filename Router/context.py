# pyright: reportAssignmentType=false
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import Widget as tkWidget
from typing import Optional, TYPE_CHECKING
from semantic_version import Version #type: ignore
import requests

from timeout_session import new_session # type: ignore
from config import appname  #type: ignore

from .constants import SPANSH_TIMEOUT

# to avoid circular imports, local imports go here
if TYPE_CHECKING:
    from .utils.updater import Updater, Notices
    from .route_manager import Router
    from .ui import UI
    from .csv import CSV
    from .overlay import Overlay
    from .hotkeys import Hotkeys
    from .prefs import Prefs
    from .spansh_data import SpanshData
    from .local.data import LocalData

from .route import Route

@dataclass
class Context:
    # Plugin parameters
    plugin_title:str = ''
    plugin_name:str = ''

    plugin_dir:Path = None
    plugin_version:Version = None
    plugin_useragent:str = None

    # Config variables
    parent:tkWidget = None

    # Global variables
    modules:list = field(default_factory=list) # Module details from Coriolis
    session:requests.Session = new_session(SPANSH_TIMEOUT) # shared, per PLUGINS.md

    # Global objects
    prefs:'Prefs' = None
    route:Route = Route([], [], -1)
    router:'Router' = None
    csv:'CSV' = None
    overlay:'Overlay' = None
    hotkeys:'Hotkeys' = None
    ui:'UI' = None
    updater:'Updater' = None
    notices:'Notices' = None
    spansh:'SpanshData' = None
    localdata:'LocalData' = None