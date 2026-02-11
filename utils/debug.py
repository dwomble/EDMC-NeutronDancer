import logging
import functools
import traceback
from os import path

from config import appname  # type: ignore

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

# Ensure `Debug.logger` exists even if no `Debug` instance was created.
# This prevents attribute errors in tests or modules that reference
# `Debug.logger` before plugin initialization.
Debug.logger = logging.getLogger(appname)
Debug.logger.addHandler(logging.NullHandler())
Debug.logger.setLevel(logging.INFO)

