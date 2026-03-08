"""
Test harness for EDMC Neutron Dancer plugin.

This harness simulates EDMC's journal entry events and provides tools to test
the plugin's routing functionality without running the full EDMC application.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Optional, Callable, Dict
from datetime import datetime, timezone
from time import sleep
import logging
import types as _types
import tkinter as tk

# Configure logging to output INFO level messages and higher to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add plugin directory to path for imports (go up one level from tests/)
plugin_dir:Path = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

# We keep a copy of edmc_data here.
this_dir:Path = Path(__file__).parent
sys.path.insert(0, str(this_dir))


# Mock EDMC's config module (only if not already mocked)
if 'config' not in sys.modules:
    class MockConfig:
        def __init__(self):
            self.data = {}
            self.shutting_down = False

        def __setitem__(self, key, value):
            self.data[key] = value

        def __getitem__(self, key):
            return self.data.get(key)

        def get(self, key, default=None):
            return self.data.get(key, default)

        def set(self, key, value):
            self.data[key] = value

        def get_int(self, key):
            return int(self.data.get(key, 0)) #type: ignore

    _cfg = _types.ModuleType('config')
    _cfg.appname = 'EDMC' # type:ignore
    _cfg.config = MockConfig() # type:ignore
    _cfg.shutting_down = False # type:ignore
    sys.modules['config'] = _cfg

# Minimal EDMC `theme` module emulator for direct runs (examples.py / __main__)
theme_mod = _types.ModuleType("theme")
theme_mod.theme = _types.SimpleNamespace() # type:ignore
theme_mod.theme.name = "default"
theme_mod.theme.dark = False
sys.modules['theme'] = theme_mod


class MockEDMCOverlay:
    def __init__(self): pass

class Mockedmcoverlay:
    def __init__(self): pass

    class Overlay():
        def __init__(self): pass
        @staticmethod
        def send_message(**kw): pass

_edmcoverlay = _types.ModuleType('EDMCOverlay')
for name, val in MockEDMCOverlay.__dict__.items():
    if not name.startswith('__'):
        setattr(_edmcoverlay, name, val)
sys.modules['EDMCOverlay'] = _edmcoverlay

_overlay = _types.ModuleType('edmcoverlay')
for name, val in Mockedmcoverlay.__dict__.items():
    if not name.startswith('__'):
        setattr(_overlay, name, val)
sys.modules['EDMCOverlay.edmcoverlay'] = _overlay

# Mock up the modern overlay and its plugin
class MockOverlay_Plugin:
    def __init__(self, **kw): pass
class Mockoverlay_api:
    def __init__(self, **kw): pass
    @staticmethod
    def define_plugin_group(**kw): pass

_overlay_plugin = _types.ModuleType('overlay_plugin')
for name, val in MockOverlay_Plugin.__dict__.items():
    if not name.startswith('__'):
        setattr(_overlay_plugin, name, val)
sys.modules['overlay_plugin'] = _overlay_plugin

_overlay_api = _types.ModuleType('overlay_api')
for name, val in Mockoverlay_api.__dict__.items():
    if not name.startswith('__'):
        setattr(_overlay_api, name, val)
sys.modules['overlay_plugin.overlay_api'] = _overlay_api

# Now we can import Router modules
from config import config # type: ignore
from Router.context import Context
from Router.route_manager import Router
from Router.route import Route
from Router.ui import UI
from Router.ship import Ship
from Router.csv import CSV
from Router.constants import NAME, TITLE
from Router.overlay import Overlay

class TestHarness:
    """ Main test harness for the Neutron Dancer plugin. """
    # Prevent pytest from trying to collect this helper class as a test class
    __test__ = False

    def __init__(self, plugin_dir:Optional[str] = None):
        """ Initialize the test harness. """
        if plugin_dir is None:
            plugin_dir = str(Path(__file__).parent)

        self.plugin_dir:Path = Path(plugin_dir).resolve()
        self.live_dir:Path = Path(__file__).parent.parent.resolve()
        self.commander = "TestCommander"
        self.is_beta = False
        self.system = "Sol"

        # Load our event sequences
        self.events:Dict[str, list] = self._load_events()
        self.loadouts:Dict[str, dict] = self._load_loadouts()

        # Initialize context
        Context.plugin_dir = self.plugin_dir
        Context.plugin_title = TITLE
        Context.plugin_name = NAME

        # Initialize router (singleton)

        self.router = Router()
        Context.router = self.router

        self.csv = CSV()
        Context.csv = self.csv

        self.overlay = Overlay()
        Context.overlay = self.overlay

        # This got stuck with annoying PhotoImage
        try:
            root:tk.Tk = tk.Tk()
        except:
            pass
        root.withdraw()

        # Have to temporarily switch the plugin dir to live so that it can find the assets folder for images.
        Context.plugin_dir = self.live_dir
        self.ui = UI(tk.Frame(root))
        Context.plugin_dir = self.plugin_dir
        Context.ui = self.ui
        self.context = Context

        # Event handlers registered by plugins
        self.journal_handlers: list[Callable] = []
        self.config = config

    def setup(self, config_file:str = "test_config.json") -> None:
        """ Setup the harness with a specific config file. """

        # Load config
        config_path:Path = self.plugin_dir / "data" / config_file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    self.router._from_dict(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load setup file {config_path}: {e}")


    def set_edmc_config(self, config_file:str = "emdc_config.json") -> None:
        # Load config
        config_path:Path = self.plugin_dir / "data" / config_file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    self.config.set(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load edmc config file {config_path}: {e}")

    def register_journal_handler(self, handler: Callable) -> None:
        """ Register a journal event handler (simulates journal_entry callback). """
        self.journal_handlers.append(handler)


    def fire_event(self, event:dict, state:Optional[dict] = None) -> None:
        """ Fire a journal event through the harness. """
        if state is None: state = {}
        sys:str = event.get("StarSystem", event.get("System", ""))
        if sys != "": self.system = sys
        event['timestamp'] = event.get('timestamp', datetime.now(timezone.utc).isoformat())
        # Call all registered handlers
        for handler in self.journal_handlers:
            try:
                handler(
                    cmdr=self.commander,
                    is_beta=self.is_beta,
                    system=self.system,
                    station="",
                    entry=event,
                    state=state
                )
            except Exception as e:
                print(f"Error in journal handler: {e}")
                raise
            sleep(0.5)  # Allow time for any asynchronous processing (if applicable)

    def play_sequence(self, name:str) -> None:
        """ Fire a sequence of events """
        for event in self.events.get(name, []):
            self.fire_event(event)

    def set_ship(self, ship_name:str) -> None:
        """ Set the current ship in the router context. """
        ship_info:dict = self.loadouts.get(ship_name, {})
        if ship_info == {}:
            print(f"Warning: No loadout info found for ship '{ship_name}' in loadouts.json")
        self.router.ship = Ship(ship_info)
        self.router.ship_id = str(ship_info.get('ShipID', '1'))
        self.router.ships[self.router.ship_id] = self.router.ship

    def _load_events(self) -> Dict[str, list]:
        """ Load journal events from events.json file. """
        events:Dict[str, list] = {}

        EVENTS_FILE = Path(self.plugin_dir, "config", "journal_events.json")
        logging.info(f"Events file: {EVENTS_FILE}")
        if not EVENTS_FILE.exists():
            return events

        try:
            with open(EVENTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load journal_events.json: {e}")

        return events

    def _load_loadouts(self) -> Dict[str, dict]:
        """ Load ship loadouts from loadouts.json file. """
        loadouts:Dict[str, dict] = {}

        LOADOUTS_FILE = Path(self.plugin_dir, "config", "loadouts.json")
        logging.info(f"Loadouts file: {LOADOUTS_FILE}")
        if not LOADOUTS_FILE.exists():
            return loadouts

        try:
            with open(LOADOUTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load loadouts.json: {e}")

        return loadouts