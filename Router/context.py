# pyright: reportAssignmentType=false
import os
from os import path
import logging
from dataclasses import dataclass
from pathlib import Path
from semantic_version import Version # type: ignore
from typing import TYPE_CHECKING

from config import appname  # type: ignore

# to avoid circular imports, local imports go here
if TYPE_CHECKING:
    from .router import Router
    from .ui import UI
    from .updater import Updater
    from .csv import CSV
@dataclass
class Context:
    # plugin parameters
    plugin_name:str = os.path.basename(os.path.dirname(__file__))
    plugin_dir:Path = None
    plugin_useragent:str = None

    # global objects
    router:'Router' = None
    csv:'CSV' = None
    ui:'UI' = None
    updater:'Updater' = None
