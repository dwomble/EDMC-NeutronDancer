# pyright: reportAssignmentType=false
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from semantic_version import Version #type: ignore

# to avoid circular imports, local imports go here
if TYPE_CHECKING:
    from utils.Updater import Updater
    from .router import Router
    from .ui import UI
    from .csv import CSV

@dataclass
class Context:
    # plugin parameters
    plugin_name:str = os.path.basename(os.path.dirname(__file__))
    plugin_dir:Path = None
    plugin_version:Version = None
    plugin_useragent:str = None

    # Global variables
    modules:list = field(default_factory=list)

    # global objects
    router:'Router' = None
    csv:'CSV' = None
    ui:'UI' = None
    updater:'Updater' = None

