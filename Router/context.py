# pyright: reportAssignmentType=false
import os
from os import path
import logging
import functools
import traceback
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
@dataclass
class Context:
    # plugin parameters
    plugin_name:str = os.path.basename(os.path.dirname(__file__))
    plugin_version:Version = None
    plugin_dir:Path = None
    plugin_useragent:str = None

    # game state
    system:str|None = None

    # global objects
    logger:logging.Logger = logging.getLogger(f'{appname}.{plugin_name}')
    router:'Router' = None
    ui:'UI' = None

class Debug:
    logger: logging.Logger

    def __init__(self, plugin_dir, dev_mode: bool = False) -> None:
        # A Logger is used per 'found' plugin to make it easy to include the plugin's
        # folder name in the logging output format.
        # NB: plugin_name here *must* be the plugin's folder name as per the preceding
        #     code, else the logger won't be properly set up.
        Debug.logger = logging.getLogger(f'{appname}.{path.basename(plugin_dir)}')

        #if dev_mode == False:
        #    Debug.logger.setLevel(logging.INFO)
        #else:
        Debug.logger.setLevel(logging.DEBUG)


def catch_exceptions(func):
    """ Generic exception handler called via decorators """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            Debug.logger.info(f"An error occurred in {func.__name__}: {e}")
            trace:list = traceback.format_exc().splitlines()
            Debug.logger.error(trace[0] + "\n" + "\n".join(trace[4:]))
    return wrapper

