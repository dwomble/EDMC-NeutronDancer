# pyright: reportAssignmentType=false
import os
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import Widget as tkWidget
from typing import Optional, TYPE_CHECKING
from semantic_version import Version #type: ignore

# to avoid circular imports, local imports go here
if TYPE_CHECKING:
    from utils.updater import Updater
    from utils.overlay import OverlayManager
    from .route_manager import Router
    from .ui import UI
    from .csv import CSV
from .route import Route

@dataclass
class Context:
    # Plugin parameters
    plugin_name:str = os.path.basename(os.path.dirname(__file__))
    plugin_dir:Path = None
    plugin_version:Version = None
    plugin_useragent:str = None

    # Config variables
    parent:tkWidget = None
    #overlay:tk.IntVar = field(default_factory=lambda: tk.IntVar(value=False))
    #overlay_color:tk.StringVar = field(default_factory=lambda: tk.StringVar(value='#000000'))
    #overlay_x:tk.IntVar = field(default_factory=lambda: tk.IntVar(value=300))
    #overlay_y:tk.IntVar = field(default_factory=lambda: tk.IntVar(value=900))

    # Global variables
    modules:list = field(default_factory=list) # Module details from Coriolis

    # Global objects
    route:Route = Route([], [], 0, [])
    router:'Router' = None
    csv:'CSV' = None
    ui:'UI' = None
    updater:'Updater' = None

