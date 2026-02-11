"""
Test harness for EDMC Neutron Dancer plugin.

This harness simulates EDMC's journal entry events and provides tools to test
the plugin's routing functionality without running the full EDMC application.
"""

import json
import sys
import logging
from pathlib import Path
from typing import Any, Optional, Callable, Dict, List
from dataclasses import dataclass, field
import datetime
import logging

# Configure logging to output INFO level messages and higher to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Add plugin directory to path for imports (go up one level from tests/)
plugin_dir:Path = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

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

    sys.modules['config'] = type('module', (), {
        'appname': 'EDMC',
        'config': MockConfig(),
        'shutting_down': False
    })()

# Minimal EDMC `theme` module emulator for direct runs (examples.py / __main__)
import types
from types import SimpleNamespace
theme_mod = types.ModuleType("theme")
theme_mod.theme = SimpleNamespace() # type:ignore
theme_mod.theme.name = "default"
theme_mod.theme.dark = False
sys.modules['theme'] = theme_mod

# Mock tkinter modules for testing
try:
    import tkinter as tk
    from tkinter import ttk
    import tkinter.messagebox
except ImportError:
    # If tkinter is not available, create mock modules
    class MockTk:
        """Mock tkinter module"""
        class Widget: pass
        class Frame(Widget): pass
        class Toplevel(Widget): pass
        class Label(Widget): pass
        class Button(Widget): pass
        class Radiobutton(Widget): pass
        class Checkbutton(Widget): pass
        class Entry(Widget): pass
        class Text(Widget): pass
        class Canvas(Widget): pass
        class Listbox(Widget): pass
        class Scale(Widget): pass
        class Spinbox(Widget): pass
        class LabelFrame(Widget): pass
        class Message(Widget): pass
        class Scrollbar(Widget): pass
        class OptionMenu(Widget): pass
        class Menubutton(Widget): pass
        class Menu(Widget): pass

        # Constants
        NSEW = "nsew"
        NW = "nw"
        N = "n"
        NE = "ne"
        W = "w"
        CENTER = "center"
        E = "e"
        SW = "sw"
        S = "s"
        SE = "se"
        LEFT = "left"
        RIGHT = "right"
        TOP = "top"
        BOTTOM = "bottom"
        BOTH = "both"
        NONE = "none"
        X = "x"
        Y = "y"
        END = "end"
        DISABLED = "disabled"
        NORMAL = "normal"

        StringVar: Callable[[], None] = lambda: None
        IntVar: Callable[[], None] = lambda: None
        BooleanVar: Callable[[], None] = lambda: None

    class MockTtk:
        """Mock tkinter.ttk module"""
        class Frame(MockTk.Frame): pass
        class Label(MockTk.Label): pass
        class Button(MockTk.Button): pass
        class Entry(MockTk.Entry): pass
        class Combobox(MockTk.Entry): pass
        class Checkbutton(MockTk.Checkbutton): pass
        class Radiobutton(MockTk.Radiobutton): pass
        class Scrollbar(MockTk.Scrollbar): pass
        class LabelFrame(MockTk.LabelFrame): pass
        class Notebook(MockTk.Frame): pass
        class Scale(MockTk.Scale): pass
        class Progressbar(MockTk.Canvas): pass

    class MockMessagebox:
        """Mock tkinter.messagebox module"""
        @staticmethod
        def showinfo(title, message): pass
        @staticmethod
        def showerror(title, message): pass
        @staticmethod
        def showwarning(title, message): pass
        @staticmethod
        def askyesno(title, message): return False
        @staticmethod
        def askokcancel(title, message): return False

    sys.modules['tkinter'] = MockTk()
    sys.modules['tkinter.ttk'] = MockTtk()
    sys.modules['tkinter.messagebox'] = MockMessagebox()

# Mock myNotebook module
class MockNotebook:
    """Mock myNotebook (nb) module"""
    class Frame:
        def __init__(self, parent=None, **kw): pass
    class Label:
        def __init__(self, parent=None, **kw): pass
    class Button:
        def __init__(self, parent=None, **kw): pass
    class Entry:
        def __init__(self, parent=None, **kw): pass
    class Combobox:
        def __init__(self, parent=None, **kw): pass
    class Checkbutton:
        def __init__(self, parent=None, **kw): pass
    class Radiobutton:
        def __init__(self, parent=None, **kw): pass
    class Scrollbar:
        def __init__(self, parent=None, **kw): pass
    class LabelFrame:
        def __init__(self, parent=None, **kw): pass
    class Notebook:
        def __init__(self, parent=None, **kw): pass

sys.modules['myNotebook'] = MockNotebook()

# Now we can import Router modules
from Router.context import Context
from Router.route_manager import Router
from Router.route import Route
from Router.ship import Ship


class TestHarness:
    """Main test harness for the Neutron Dancer plugin."""
    # Prevent pytest from trying to collect this helper class as a test class
    __test__ = False

    def __init__(self, plugin_dir:Optional[str] = None):
        """ Initialize the test harness. """
        if plugin_dir is None:
            plugin_dir = str(Path(__file__).parent)

        self.plugin_dir:Path = Path(plugin_dir).resolve()
        self.commander = "TestCommander"
        self.is_beta = False
        self.system = "Sol"

        # Load our event sequences
        self.events:Dict[str, list] = self._load_events()
        self.loadouts:Dict[str, dict] = self._load_loadouts()

        # Initialize context
        Context.plugin_dir = self.plugin_dir
        Context.plugin_name = "Neutron Dancer"

        # Initialize router (singleton)

        self.router = Router()
        Context.router = self.router

        self.context = Context

        # Ensure minimal module data present for ship calculations during tests
        try:
            # Add FSD entry if missing or missing necessary fields
            fsd_symbol = 'int_hyperdrive_size8_class5'
            # Replace any existing FSD entries with a known-good one so it's chosen first
            fsd_entry = {
                'symbol': 'Int_Hyperdrive_Size8_Class5',
                'fuelpower': 2.505,
                'fuelmul': 0.011,
                'maxfuel': 6.8,
                'optmass': 4670,
            }
            Context.modules = [m for m in Context.modules if m.get('symbol','').lower() != fsd_symbol] if hasattr(Context, 'modules') else []
            Context.modules.insert(0, fsd_entry)

            ft_symbol = 'int_fueltank_size8_class3'
            # Ensure a matching fuel tank entry exists
            ft_entry = {
                'symbol': 'Int_FuelTank_Size8_Class3',
                'fuel': 32.0,
            }
            Context.modules = [m for m in Context.modules if m.get('symbol','').lower() != ft_symbol]
            # Place fuel tank after FSD entries
            Context.modules.insert(1, ft_entry)
        except Exception:
            pass

        # Event handlers registered by plugins
        self.journal_handlers: list[Callable] = []
        self.state_change_handlers: list[Callable] = []

    def setup(self, config_file:str = "test_config.json") -> None:
        """ Setup the harness with a given config file. """

        # Load config
        config_path:Path = self.plugin_dir / config_file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    self.router._from_dict(json.load(f))
            except Exception as e:
                print(f"Warning: Could not load config file {config_path}: {e}")


    def register_journal_handler(self, handler: Callable) -> None:
        """
        Register a journal event handler (simulates journal_entry callback).

        Args:
            handler: Callable that accepts (cmdr, is_beta, system, station, entry, state)
        """
        self.journal_handlers.append(handler)


    def fire_event(self, event:dict, state:Optional[dict] = None) -> None:
        """ Fire a journal event through the harness. """
        if state is None: state = {}
        sys:str = event.get("StarSystem", event.get("System", ""))
        if sys != "": self.system = sys

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

    def _load_events(self) -> Dict[str, list]:
        """Load journal events from events.json file."""
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
        """Load ship loadouts from loadouts.json file."""
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