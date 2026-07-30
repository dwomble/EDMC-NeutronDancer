"""
Test suite for EDMC Neutron Dancer plugin using pytest.
"""
#from __future__ import annotations

import pytest # type: ignore
import sys
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Generator
from unittest.mock import Mock, patch
import json
import logging
import tkinter as tk
from tkinter import ttk
import threading

from tests.edmc import edmc_data
from utils.treeviewplus import TreeviewPlus
import utils.th as th

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

from harness import TestHarness, reset_plugin_modules
from Router.route_window import RouteWindow
from Router.constants import SPANSH_ROUTE, NAME, lbls
from Router.route import Route
from Router.ship import Ship

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

plotter_thread = None
def capture_thread(*args, **kwargs):
    global plotter_thread

    thread = threading.Thread(*args, **kwargs)
    if kwargs.get('name', '') == "Neutron Dancer route plotting worker":
        plotter_thread = thread
    return thread


def fake_systems_get(url, *args, **kwargs):
    """ Stand-in for requests.get against the Spansh systems autocomplete endpoint.
    Echoes back whatever was queried so system-name validation always succeeds without a real network call. """
    q = kwargs.get('params', {}).get('q', '')
    resp = Mock()
    resp.status_code = 200
    resp.content = json.dumps([q]).encode()
    return resp

@pytest.fixture
def harness(request) -> Generator:
    """Provide a fresh test harness for each test."""

    # We want a standard route.json for each test
    Path(__file__).parent.joinpath("data").mkdir(exist_ok=True)

    Path(Path(__file__).parent / "data" / "route.json").unlink(missing_ok=True)
    init_file = getattr(request, 'param', 'route_init.json')
    if init_file != 'None':
        shutil.copy(Path(__file__).parent / "config" / init_file,
                    Path(__file__).parent / "data" / "route.json")

    overlay = 'Modern'
    if request.node.get_closest_marker('overlay'):
        overlay = request.node.get_closest_marker('overlay').args[0]

    hotkeys = request.node.get_closest_marker('hotkeys') or True

    TestHarness.reset_instance()
    reset_plugin_modules()

    test_harness = TestHarness(live_requests=True, overlay=overlay, hotkeys=hotkeys)

    # This is ND-specific. /assets is where the images are stored
    import Router.constants
    Router.constants.ASSET_DIR = "../assets"

    from load import plugin_start3, plugin_app, journal_entry, dashboard_entry

    # Prevent network updater thread from making tests hang on teardown.
    with patch('load.Updater.check_for_update', return_value=None):
        plugin_start3(str(test_harness.plugin_dir))
    plugin_app(test_harness.parent)

    # ND-specific, this is our plugin object
    import Router.context
    test_harness.plugin = Router.context.Context

    # ND-specific, this is the journal handling function and the default journal params
    test_harness.load_events("journal_events.json")
    test_harness.register_journal_handler(journal_entry, 'Testy', 'Sol', True)

    # This is the dashboard handlling function
    test_harness.register_dashboard_handler(dashboard_entry, 'Testy', True)

    yield test_harness

    test_harness.assert_no_unhandled_exceptions()
    TestHarness.reset_instance()

class TestStartup:
    """Test plugin startup behavior."""

    @pytest.mark.parametrize('harness', ['None', 'route_init.json'], indirect=True)
    def test_harness_initialization(self, harness:TestHarness) -> None:
        """Test basic harness initialization."""
        assert harness.plugin.router is not None

    def test_harness_no_init(self, harness:TestHarness) -> None:
        """Test basic harness initialization."""

        assert harness.plugin.router is not None

    def test_startup_event(self, harness:TestHarness) -> None:
        """Test that startup event sets system correctly."""

        assert harness.plugin.router is not None
        harness.play_sequence('startup')
        assert harness.plugin.router.system == "Sol"

    def test_module_import(self, harness:TestHarness) -> None:
        """Test retrieving module data from Coriolis """
        harness.plugin.modules = []
        harness.plugin.router._get_module_data()
        assert len(harness.plugin.modules) == 88

    def test_migration(self, harness:TestHarness) -> None:
        """ Test route.json migration """
        shutil.copy(Path(__file__).parent / "config" / "route_1.10.0.json",
                Path(__file__).parent / "data" / "route.json")

        assert not hasattr(harness.plugin.router, "ships")
        assert isinstance(harness.plugin.router.shiplist, dict)
        assert harness.plugin.router.shiplist["1"] == "Shipping Delay"


class TestStateManagement:
    """Test router state management."""

    def test_load(self, harness:TestHarness) -> None:
        """Call plugin load"""
        harness.plugin.router._load()

    def test_save(self, harness:TestHarness) -> None:
        """Call save"""
        harness.plugin.router.save()

class TestRouteNavigation:
    """Test route navigation methods."""

    def test_not_on_route(self, harness:TestHarness) -> None:
        """Test not on route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.system = 'Apurui'

        dest:str = harness.plugin.route.next_stop()
        assert dest == 'Bleae Thua NI-B b27-5'

    def test_on_route(self, harness:TestHarness) -> None:
        """Test on route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0

        dest:str = harness.plugin.route.next_stop()
        assert dest == 'Bleae Thua RX-L d7-28'

    def test_start_of_route(self, harness:TestHarness) -> None:
        """Test start of route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0

        # First stop shouldn't move further back
        offset:int = harness.plugin.route.update_route(-1)
        assert offset == -1
        dest:str = harness.plugin.route.next_stop()
        assert dest == 'Bleae Thua NI-B b27-5'

    def test_end_of_route(self, harness:TestHarness) -> None:
        """Test start of route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Smojue DR-N d6-34')
        assert offset == 9

        # Last stop
        offset:int = harness.plugin.route.update_route(1)
        dest:str = harness.plugin.route.next_stop()
        assert dest == 'End of the road!'

        # Last stop shouldn't move further along
        offset:int = harness.plugin.route.update_route(1)
        dest:str = harness.plugin.route.next_stop()
        assert dest == 'End of the road!'

    def test_route_neutron(self, harness:TestHarness) -> None:
        """Test route with neutron column."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.is_neutron() == False  # Next waypoint is not a neutron

        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert harness.plugin.route.is_neutron() == True  # Next waypoint is a neutron

    def test_jumps_to_wp(self, harness:TestHarness) -> None:
        """Test jumps to next waypoint."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.jumps_to_wp() == 12

        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert harness.plugin.route.jumps_to_wp() == 3

    def test_total_jumps_neutron(self, harness:TestHarness) -> None:
        """Test total jumps for neutron route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.total_jumps() == 66

    def test_total_jumps_galaxy(self, harness:TestHarness) -> None:
        """Test total jumps for galaxy route."""
        filename:str = str(Path(__file__).parent / "config" / "galaxy-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.total_jumps() == 74

    def test_jumps_remaining_neutron(self, harness:TestHarness) -> None:
        """Test jumps remaining for neutron route (one with a jumps column)."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.jumps_remaining() == 66

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.jumps_remaining() == 66

        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert harness.plugin.route.jumps_remaining() == 54

    def test_jumps_remaining_galaxy(self, harness:TestHarness) -> None:
        """Test jumps remaining for galaxy route (one without a jumps column)."""
        filename:str = str(Path(__file__).parent / "config" / "galaxy-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        # Not yet on the route
        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.jumps_remaining() == 74

        # Start of route
        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        assert harness.plugin.route.jumps_remaining() == 74

        # Partway along
        offset:int = harness.plugin.route.update_route(0, 'Gria Drye JT-O d7-172')
        assert offset == 22
        assert harness.plugin.route.jumps_remaining() == 52


    def test_perc_jumps_remaining(self, harness:TestHarness) -> None:
        """Test percentage of jumps remaining for neutron route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert int(harness.plugin.route.perc_jumps_rem()) == 18

    def test_dist_remaining(self, harness:TestHarness) -> None:
        """Test distance remaining for neutron route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert int(harness.plugin.route.dist_remaining()) == 16273

    def test_total_dist(self, harness:TestHarness) -> None:
        """Test total distance for neutron route."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        offset:int = harness.plugin.route.update_route(0, 'Bleae Thua NI-B b27-5')
        assert offset == 0
        offset:int = harness.plugin.route.update_route(1)
        assert offset == 1
        assert int(harness.plugin.route.total_dist()) == 16458


class TestShipLoadout:
    """Test ship loadout and switching."""

    def test_bad_event(self, harness:TestHarness) -> None:
        """Test bad loadout event."""
        harness.fire_event({"event": "bad", "Ship":"naughty", "ShipID":100000, "ShipName":"Dummy", "ShipIdent":"Dumdum"})

        assert not hasattr(harness.plugin.router.ship, "ship_id")

    def test_loadout_event(self, harness:TestHarness) -> None:
        """Test loading a ship."""

        harness.play_sequence('loadout')
        assert harness.plugin.router.ship_id == '87'
        assert harness.plugin.router.ship is not None
        assert harness.plugin.router.ship.type == 'mandalay'
        assert harness.plugin.router.ship.name == 'Long Delay'
        assert harness.plugin.router.route_params['Neutron']['supercharge_multiplier'] == harness.plugin.router.ship.supercharge_multiplier
        assert harness.plugin.router.route_params['Neutron']['range'] == harness.plugin.router.ship.range


    def test_ship_range_calculation(self, harness:TestHarness) -> None:
        """Test that ship range is calculated."""
        assert harness.plugin.router.ship is not None
        assert hasattr(harness.plugin.router.ship, 'range')
        assert harness.plugin.router.ship.range > 0


class TestImporting:
    """Test importing functionality for different route types."""

    def test_import_nofile(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "missing.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_empty(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "empty.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_bad_route(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "bad_import.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_route_neutron(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.router.dest == 'Smojue DR-N d6-34'
        assert harness.plugin.route.total_jumps() == 66

    def test_import_route_galaxy(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "galaxy-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)

        logging.debug(f"Route: {len(harness.plugin.route.route)} {harness.plugin.route}")
        assert res == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.router.dest == 'Voqooe BI-H d11-864'
        assert harness.plugin.route.total_jumps() == 74

    def test_import_route_fc(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "fc-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.route.fleetcarrier == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        harness.plugin.route.offset = 9
        assert harness.plugin.route.next_stop() == 'Nyeajeau IQ-U c4-7'
        assert harness.plugin.router.dest == 'Voqooe BI-H d11-864'

    def test_import_route_riches(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "riches-Apurui-M23.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.router.src == 'HIP 89264 6'
        assert harness.plugin.router.dest == 'Bleae Thua HF-R d4-116 B 7'


class TestExporting:
    """CSV Export"""
    def test_export_noroute(self, harness:TestHarness) -> None:
        """ Trying to export without a route """
        harness.plugin.route = Route()
        res:bool = harness.plugin.router.export_route()
        assert res == False

    def test_export_no_file(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True

        with patch('Router.csv.filedialog.asksaveasfilename', return_value=''):
            res:bool = harness.plugin.router.export_route()

        assert res == False

    def test_export_route(self, harness:TestHarness) -> None:
        out:str = str(Path(__file__).parent / "config" / "tmp.csv")
        if os.path.exists(out):
            os.remove(out)

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        with patch('Router.csv.filedialog.asksaveasfilename', return_value=out):
            res:bool = harness.plugin.csv.write(harness.plugin.route.hdrs, harness.plugin.route.route)
        assert res == True
        assert os.path.exists(out)
        os.remove(out)


class TestCargo:
    """Test cargo management."""

    def test_cargo_event(self, harness:TestHarness):
        """Test cargo event updates."""
        Path(Path(__file__).parent / "journal_folder" / "Cargo.json").unlink(missing_ok=True)
        shutil.copy(Path(__file__).parent / "journal_config" / "Cargo_init.json",
                    Path(__file__).parent / "journal_folder" / "Cargo.json")

        harness.play_sequence('add_cargo')
        assert harness.plugin.router.cargo == 200
        harness.play_sequence('remove_cargo')
        assert harness.plugin.router.cargo == 0


class TestChatCommands:
    """Test !nd chat commands"""
    def test_next(self, harness:TestHarness):
        """Test next command when at the beginning of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[0])
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_no_next(self, harness:TestHarness):
        """Test next command when at the end of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        harness.plugin.route.offset = len(harness.plugin.route.route)-2
        assert harness.plugin.route.next_stop() == 'Voqooe BI-H d11-864'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[0])
        assert harness.plugin.route.next_stop() == 'End of the road!'

    def test_previous(self, harness:TestHarness):
        """Test prev/previous command when at the beginning of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        harness.plugin.router.system = 'Bleae Thua NI-B b27-5'
        harness.plugin.router.update_route(1)
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_no_previous(self, harness:TestHarness):
        """Test prev/previous command when not yet on the route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_copy(self, harness:TestHarness):
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[2])
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == 'Bleae Thua NI-B b27-5'

    def test_other(self, harness:TestHarness):
        """Test some other random string has no impact"""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        from utils.misc import copy_to_clipboard
        copy_to_clipboard(harness.plugin.ui.parent, '')

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[3])
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == ''

class TestShipyardSwap:
    """Test ship swapping from shipyard."""

    def test_ship_bad_init(self, harness:TestHarness):
        """Test bad ship swap event."""
        entry:dict = {"event": "bad"}
        ship:Ship = Ship(entry)

        assert ship.loadout == {}

    @pytest.mark.parametrize('harness', ['None', 'route_init.json'], indirect=True)
    def test_ship_repr(self, harness:TestHarness):
        """Test ship repr."""
        harness.play_sequence('shipyard_swap')
        ship:Ship = harness.plugin.router.ship

        assert repr(ship) == f"ID {ship.id}, name {ship.name}, type {ship.type}, unladen range {ship.range:.2f}ly)"

    def test_swap_existing_ship(self, harness:TestHarness):
        """Test swapping to a previously loaded ship."""
        # Load multiple ships
        harness.play_sequence('shipyard_swap')
        assert harness.plugin.router.ship_id == '106'

    def test_swap_unknown_ship(self, harness:TestHarness):
        """Test swapping to an unknown ship."""
        harness.play_sequence('shipyard_swap_unknown')
        assert harness.plugin.router.ship_id == ''


class TestOverlay:
    """Test overlay functionality."""

    @pytest.mark.overlay('None')
    def test_no_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is None

    @pytest.mark.overlay('Legacy')
    def test_legacy_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is None

    @pytest.mark.overlay('Modern')
    def test_modern_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is not None

    def test_countdown_starts_thread(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure countdown starts the countdown thread."""

        called:dict[str, bool] = {'flag': False}

        def fake_countdown(self, frame, content, end, stop) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.plugin.overlay), '_countdown', fake_countdown, raising=False)
        harness.plugin.overlay.display_countdown('Carrier', 'Countdown', 100)

        # The thread may run quickly; wait briefly for it to start
        import time
        time.sleep(0.05)
        assert called['flag'] is True

    def test_countdown_shows_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure carrier jump completion starts the countdown thread."""

        called:dict[str, bool] = {'flag': False}

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[1])
        assert harness.plugin.overlay.msgs != {}

    def test_clear_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure clearings all frames removes the messages."""

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[2])

        assert harness.plugin.overlay.msgs != {}
        harness.plugin.overlay.clear_frames()

        assert harness.plugin.overlay.msgs == {}

    def test_hide_show_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure hiding all frames set them as hidden."""

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[2])

        assert harness.plugin.overlay.msgs != {}
        harness.plugin.overlay.hide_frames()

        frames = harness.plugin.overlay.ovfrs
        for fr in harness.plugin.overlay.ovfrs:
            assert frames[fr].visible == False or fr not in harness.plugin.overlay.msgs

        harness.plugin.overlay.show_frames()

        frames = harness.plugin.overlay.ovfrs
        for fr in harness.plugin.overlay.ovfrs:
            assert frames[fr].visible == True or fr not in harness.plugin.overlay.msgs

    def test_redraw_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure redraw_frames renders using the configured progress_display template."""

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        overlay.redraw_frames()

        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"] == 'PD jc=- jr=399 jt=399 dc=0 dr=16.5K dt=16.5K dh=- jh=- rj=- rd=- st=✨'

    def test_update_jump_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure update_jump_overlay renders using the configured progress_display template."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        overlay.update_jump_overlay()

        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"] == 'PD jc=15 jr=384 jt=399 dc=286 dr=16.2K dt=16.5K dh=- jh=- rj=- rd=- st=🌀'

    def test_invalid_format(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure update_jump_overlay handles invalid progress_display format."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.progress_display = "invalid={unknown}"

        overlay.update_jump_overlay()

        progress_line:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"]
        assert progress_line == "Error formatting progress display"

    def test_hide_show_default_frame(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure changing the view updates the overlay."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.update_jump_overlay()

        msg:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]
        assert msg == "Next: Bleia Eohn ZL-J d10-47 (1 jump)"

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Default"].visible == True

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusExternalPanel})
        assert harness.plugin.overlay.ovfrs["Default"].visible == False

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Default"].visible == True

    def test_show_hide_galaxy_frame(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure changing the view updates the overlay."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.update_jump_overlay()

        msg:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]
        assert msg == "Next: Bleia Eohn ZL-J d10-47 (1 jump)"

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusGalaxyMap})
        assert harness.plugin.overlay.ovfrs["Galaxy Map"].visible == True

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Galaxy Map"].visible == False

    def test_show_prefs(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure saving preferences works, or at least doesn't crash."""

        res = harness.plugin.overlay.prefs_display(harness.parent)
        # Should return a child frame of the parent window
        assert res in harness.parent.winfo_children()

    def test_save_prefs(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure saving preferences works."""

        overlay = harness.plugin.overlay
        res = overlay.prefs_display(harness.parent)

        # Should return a child frame of the parent window
        assert res in harness.parent.winfo_children()

        # Save preferences
        overlay.pb.set(False)
        overlay.save_prefs()
        assert harness.config.get_bool(f"{harness.plugin.plugin_name}_progress_bar", True) == False

        # Save preferences
        overlay.pb.set(True)
        overlay.save_prefs()
        assert harness.config.get_bool(f"{harness.plugin.plugin_name}_progress_bar", False) == True

class TestHotkeyCommands:
    """Test hotkey commands"""

    def test_next_hotkey(self, harness:TestHarness) -> None:
        """Test next hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

        harness.plugin.hotkeys.next()
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_previous_hotkey(self, harness:TestHarness) -> None:
        """Test previous hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.route.offset = 1
        assert harness.plugin.route.next_stop() == 'Bleae Thua ZJ-I d9-101'

        harness.plugin.hotkeys.previous()
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_copy_hotkey(self, harness:TestHarness) -> None:
        """Test copy hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.hotkeys.copy()
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == 'Bleae Thua NI-B b27-5'

class TestPlotMethods:
    """Test individual plotting functions"""

    def test_plot_route_starts_thread(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure plot_route returns True and starts the plotting worker."""
        called:dict[str, bool] = {'flag': False}

        def fake_plotter(self, which, url, params) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.plugin.router), '_plotter', fake_plotter, raising=False)

        harness.plugin.router.carrier_id = 'TES-TY1'
        params:dict = {'from': 'A', 'to': 'B', 'max_time': 1}
        result:bool = harness.plugin.router.plot_route('Neutron', params)
        assert result is True
        # The thread may run quickly; wait briefly for it to start
        import time
        time.sleep(0.05)
        assert called['flag'] is True

    def test_plotter_success_creates_route(self, harness:TestHarness) -> None:
        """Test that _plotter successfully creates a route from Spansh response."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        }).encode()


        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'from': 'Start', 'to': 'End', 'max_time': 1}
                    harness.plugin.router.plot_route('Neutron', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) >= 2

        # Regression: plot_route() must persist into route_params, not a stray neutron_params attribute
        assert harness.plugin.router.route_params['Neutron'] == params
        assert not hasattr(harness.plugin.router, 'neutron_params')

    def test_plotter_success_creates_route_galaxy(self, harness:TestHarness) -> None:
        """Test that _plotter persists Galaxy params into route_params (not a stray galaxy_params attribute)."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'source': 'Start', 'destination': 'End', 'max_time': 1}
                    harness.plugin.router.plot_route('Galaxy', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert harness.plugin.router.route_params['Galaxy'] == params
        assert not hasattr(harness.plugin.router, 'galaxy_params')

    def test_plotter_success_creates_route_rtor(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Road-to-Riches response (systems with nested bodies) into one row per
        body, dropping bodyless systems (e.g. the starting system) rather than emitting a placeholder row --
        matching how a Spansh-exported riches CSV never includes a bodyless row (see riches-Apurui-M23.csv)."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        # Real shape captured from the live Spansh riches API: a bodyless system (start)
        # followed by a system with two scannable bodies.
        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Colonia", "jumps": 1, "bodies": []},
                {"name": "Eol Prou LW-L c8-62", "jumps": 1, "bodies": [
                    {"name": "Eol Prou LW-L c8-62 7", "subtype": "Water world", "is_terraformable": True,
                     "distance_to_arrival": 173.1, "estimated_scan_value": 301683, "estimated_mapping_value": 1096113},
                    {"name": "Eol Prou LW-L c8-107 2", "subtype": "Earth-like world", "is_terraformable": False,
                     "distance_to_arrival": 436.9, "estimated_scan_value": 301332, "estimated_mapping_value": 1094838},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20', 'max_time': 1}
                    harness.plugin.router.plot_route('RtoR', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 2  # bodyless Colonia dropped; one row per body
        assert "Body Name" in harness.plugin.route.hdrs
        assert "Estimated Scan Value" in harness.plugin.route.hdrs
        assert harness.plugin.route.source() == 'Eol Prou LW-L c8-62 7'
        assert harness.plugin.router.route_params['RtoR'] == params

    def test_plotter_success_creates_route_ammonia(self, harness:TestHarness) -> None:
        """Regression: _plotter's riches-shape branch must trigger for body_types-filtered
        variants too (Ammonia/Earth-like/Rocky-metal), not just literally 'RtoR' -- it used
        to check `which == 'RtoR'`, so any other riches-family type fell into the flat
        jumps/system_jumps branch and crashed calling .get() on a list."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Eol Prou OC-K c9-5", "jumps": 1, "bodies": [
                    {"name": "Eol Prou OC-K c9-5 3", "subtype": "Ammonia world", "is_terraformable": False,
                     "distance_to_arrival": 337.9, "estimated_scan_value": 302571, "estimated_mapping_value": 1099340},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20',
                              'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 1}
                    harness.plugin.router.plot_route('Ammonia', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 1
        assert harness.plugin.route.source() == 'Eol Prou OC-K c9-5 3'
        assert harness.plugin.router.route_params['Ammonia'] == params

    def test_plotter_success_creates_route_exobiology(self, harness:TestHarness) -> None:
        """Test that _plotter flattens an Exobiology response -- same nested systems/bodies
        shape as riches, but each body also carries a `landmarks` list (biological species)
        and `landmark_value`, which should surface as their own Species/Landmark Value
        columns without polluting riches-family rows that never have that key."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Colonia", "jumps": 1, "bodies": []},
                {"name": "Eol Prou PX-T d3-291", "jumps": 1, "bodies": [
                    {"name": "Eol Prou PX-T d3-291 ABC 3 d", "subtype": "Rocky body",
                     "distance_to_arrival": 2684.5, "estimated_scan_value": 500, "estimated_mapping_value": 2221,
                     "landmark_value": 32831400, "landmarks": [
                        {"count": 41, "subtype": "Frutexa Flammasis", "type": "Frutexa", "value": 10326000},
                        {"count": 9, "subtype": "Concha Aureolas", "type": "Concha", "value": 7774700},
                     ]},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '30', 'max_results': '10',
                              'min_value': 100000, 'max_time': 1}
                    harness.plugin.router.plot_route('Exobiology', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 1  # bodyless Colonia dropped
        assert harness.plugin.route.source() == 'Eol Prou PX-T d3-291 ABC 3 d'
        assert "Species" in harness.plugin.route.hdrs
        assert "Landmark Value" in harness.plugin.route.hdrs
        row = harness.plugin.route.route[0]
        assert row[harness.plugin.route.hdrs.index("Species")] == 'Frutexa Flammasis'  # highest-value landmark
        assert row[harness.plugin.route.hdrs.index("Landmark Value")] == 32831400
        assert harness.plugin.router.route_params['Exobiology'] == params

    def test_plotter_success_creates_route_trade(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Trade response -- a FLAT list of hops (unlike the
        riches family's nested systems/bodies shape), each of which may carry more than one
        commodity at once. Each commodity-per-hop becomes its own row, keyed to the hop's
        *destination* (not source), matching every other route type's "row = next place to
        go" convention. Real shape captured from the live Spansh trade API."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {
                    "commodities": [
                        {"amount": 200, "name": "Agronomic Treatment", "profit": 10617, "total_profit": 2123400,
                         "source_commodity": {"buy_price": 2751, "sell_price": 2656, "demand": 1, "supply": 15577},
                         "destination_commodity": {"buy_price": 0, "sell_price": 13368, "demand": 42, "supply": 0}},
                    ],
                    "cumulative_profit": 2123400,
                    "distance": 12.66,
                    "source": {"station": "Jameson Memorial", "system": "Shinrarta Dezhra", "system_id64": 3932277478106,
                               "distance_to_arrival": 346, "market_id": 128666762},
                    "destination": {"station": "Alvarado Beacon", "system": "Puppis Sector TO-R b4-4",
                                     "system_id64": 9467852826033, "distance_to_arrival": 3, "market_id": 4243439363},
                },
                {
                    "commodities": [
                        {"amount": 186, "name": "Military Grade Fabrics", "profit": 12077, "total_profit": 2246322,
                         "source_commodity": {}, "destination_commodity": {}},
                        {"amount": 14, "name": "Tritium", "profit": 2603, "total_profit": 36442,
                         "source_commodity": {}, "destination_commodity": {}},
                    ],
                    "cumulative_profit": 4406164,
                    "distance": 33.13,
                    "source": {"station": "Alvarado Beacon", "system": "Puppis Sector TO-R b4-4"},
                    "destination": {"station": "Gaiman Port", "system": "Kamici"},
                },
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                              'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                              'max_hop_distance': '50', 'max_system_distance': '10000000', 'max_time': 1}
                    harness.plugin.router.plot_route('Trade', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 3  # 1 commodity in hop 1 + 2 commodities in hop 2
        assert "Station Name" in harness.plugin.route.hdrs
        assert "Commodity" in harness.plugin.route.hdrs
        assert "Cumulative Profit" in harness.plugin.route.hdrs

        # Row 0 is keyed to hop 0's DESTINATION, not its source -- the starting station never
        # gets its own row, matching how every other route type's row 0 is the first waypoint
        # *after* the start, not the start itself. route.source() reads the System Name column;
        # the station itself is a separate column.
        assert harness.plugin.route.source() == 'Puppis Sector TO-R b4-4'
        row0 = harness.plugin.route.route[0]
        assert row0[harness.plugin.route.hdrs.index("Station Name")] == 'Alvarado Beacon'
        assert row0[harness.plugin.route.hdrs.index("Commodity")] == 'Agronomic Treatment'
        assert row0[harness.plugin.route.hdrs.index("Cumulative Profit")] == 2123400

        # Hop 1 carried two commodities -> two rows, same destination, different commodity
        row1, row2 = harness.plugin.route.route[1], harness.plugin.route.route[2]
        assert row1[harness.plugin.route.hdrs.index("Commodity")] == 'Military Grade Fabrics'
        assert row2[harness.plugin.route.hdrs.index("Commodity")] == 'Tritium'
        assert row1[harness.plugin.route.hdrs.index("System Name")] == 'Kamici'
        assert row2[harness.plugin.route.hdrs.index("System Name")] == 'Kamici'

        assert harness.plugin.router.route_params['Trade'] == params

    def test_plotter_success_creates_route_fleetcarrier(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Fleet Carrier response -- each requested stop appears
        twice (ending one leg, starting the next), so only distance_to_destination == 0 rows
        should survive. Real shape captured from the live Spansh fleet carrier API."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {"jumps": [
                {"distance": 0, "distance_to_destination": 131.427, "fuel_in_tank": 42, "fuel_used": 0,
                 "has_icy_ring": False, "id64": 10477373803, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 1, "name": "Sol", "restock_amount": 42,
                 "tritium_in_market": 0},
                {"distance": 131.427, "distance_to_destination": 0, "fuel_in_tank": 21, "fuel_used": 21,
                 "has_icy_ring": True, "id64": 6681123623626, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Deciat", "restock_amount": 0,
                 "tritium_in_market": 0},
                {"distance": 0, "distance_to_destination": 129.796, "fuel_in_tank": 21, "fuel_used": 0,
                 "has_icy_ring": False, "id64": 6681123623626, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Deciat", "restock_amount": 0,
                 "tritium_in_market": 0},
                {"distance": 129.796, "distance_to_destination": 0, "fuel_in_tank": 0, "fuel_used": 21,
                 "has_icy_ring": False, "id64": 1178708478315, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Alpha Centauri", "restock_amount": 0,
                 "tritium_in_market": 0},
            ]}
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'source_name': 'Sol', 'source': 10477373803,
                              'destination_names': ['Deciat', 'Alpha Centauri'],
                              'destinations': [6681123623626, 1178708478315],
                              'carrier_type': 'fleet', 'capacity': 25000, 'mass': 25000,
                              'capacity_used': '0', 'calculate_starting_fuel': 1, 'max_time': 1}
                    harness.plugin.router.plot_route('FleetCarrier', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=30)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 2  # one row per stop, not per jump entry
        row0, row1 = harness.plugin.route.route[0], harness.plugin.route.route[1]
        assert row0[harness.plugin.route.hdrs.index("System Name")] == 'Deciat'
        assert row1[harness.plugin.route.hdrs.index("System Name")] == 'Alpha Centauri'
        assert "Icy Ring" in harness.plugin.route.hdrs
        assert "Restock Tritium" in harness.plugin.route.hdrs

    def test_plotter_error_response_shows_error(self, harness:TestHarness):
        """Test that _plotter handles error responses without crashing."""
        # Mock error response
        error_response = Mock()
        error_response.status_code = 500
        error_response.content = json.dumps({"error": "Server error"}).encode()

        # Track the thread so we can join it
        plotter_thread = None
        original_thread = __import__('threading').Thread

        def capture_thread(*args, **kwargs):
            nonlocal plotter_thread
            thread = original_thread(*args, **kwargs)
            if "route plotting worker" in thread.name:
                plotter_thread = thread
            return thread

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=error_response):
                params = {'from': 'Start', 'to': 'End', 'max_time': 1}
                # Should not raise exception, just handle error gracefully
                harness.plugin.router.plot_route('Neutron', params)

                # Join the plotter thread if captured
                if plotter_thread:
                    plotter_thread.join(timeout=120)

    def test_neutron_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: NeutronPlotter.plot() must actually invoke Context.router.plot_route()."""
        ui = harness.plugin.ui
        neutron_fr = ui.plot_frames['Neutron']

        neutron_fr.nametowidget("source_ac").set_text("Sol", False)
        neutron_fr.nametowidget("dest_ac").set_text("Colonia", False)
        neutron_fr.nametowidget("range_entry").set_text("50", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Neutron'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Neutron'
        assert params['from'] == 'Sol'
        assert params['to'] == 'Colonia'
        assert params['range'] == '50'
        assert params['via'] == []

    def test_neutron_plotter_via_hops(self, harness:TestHarness) -> None:
        """Regression: the + beside source must add via-point hops, sent as an ordered list."""
        ui = harness.plugin.ui
        plotter = ui.plotters['Neutron']
        neutron_fr = ui.plot_frames['Neutron']

        neutron_fr.nametowidget("source_ac").set_text("Sol", False)
        neutron_fr.nametowidget("dest_ac").set_text("Colonia", False)
        neutron_fr.nametowidget("range_entry").set_text("50", False)

        assert len(plotter.hop_rows) == 0
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        _, params = mock_plot_route.call_args[0]
        assert params['via'] == ['Deciat']

    def test_galaxy_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: GalaxyPlotter.plot() must actually invoke Context.router.plot_route()."""
        harness.play_sequence('loadout')
        ui = harness.plugin.ui
        galaxy_fr = ui.plot_frames['Galaxy']

        galaxy_fr.nametowidget("source_ac").set_text("Sol", False)
        galaxy_fr.nametowidget("dest_ac").set_text("Colonia", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Galaxy'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Galaxy'
        assert params['source'] == 'Sol'
        assert params['destination'] == 'Colonia'

    def test_rtor_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: RichesPlotter.plot() must actually invoke Context.router.plot_route()."""
        ui = harness.plugin.ui
        rtor_fr = ui.plot_frames['RtoR']

        rtor_fr.nametowidget("source_ac").set_text("Colonia", False)
        rtor_fr.nametowidget("dest_ac").set_text("", False)  # blank destination -> circular tour
        rtor_fr.nametowidget("range_entry").set_text("50", False)
        rtor_fr.nametowidget("radius_entry").set_text("40", False)
        rtor_fr.nametowidget("max_results_entry").set_text("20", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['RtoR'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'RtoR'
        assert params['from'] == 'Colonia'
        assert 'to' not in params  # destination left blank -> circular tour
        assert params['radius'] == '40'
        assert params['max_results'] == '20'
        assert 'body_types' not in params  # plain Road to Riches has no body filter

    @pytest.mark.parametrize('route_type,expected_body_types', [
        ('Ammonia', ['Ammonia world']),
        ('EarthLike', ['Earth-like world']),
        ('RockyMetal', ['Rocky body', 'High metal content world']),
    ])
    def test_riches_body_filter_plotter_plot_calls_plot_route(self, harness:TestHarness, route_type, expected_body_types) -> None:
        """Regression: each body-type-filtered riches plotter (Ammonia/Earth-like/Rocky-metal)
        must invoke plot_route with its own fixed body_types filter and min_value=1."""
        ui = harness.plugin.ui
        fr = ui.plot_frames[route_type]

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("40", False)
        fr.nametowidget("max_results_entry").set_text("20", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters[route_type].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == route_type
        assert params['from'] == 'Colonia'
        assert params['body_types'] == expected_body_types
        assert params['min_value'] == 1
        assert 'use_mapping_value' not in params  # these pages don't expose that option

    def test_exobiology_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: Exobiology has no body_types filter (unlike Ammonia/Earth-like/Rocky-metal)
        -- its filtering criterion is a real "Minimum Landmark Value" slider (0-21, units of
        millions of credits implied), which must be scaled by 1,000,000 before being sent."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Exobiology']

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("30", False)
        fr.nametowidget("max_results_entry").set_text("10", False)
        fr.nametowidget("min_value_entry").set(5)  # 5 million credits

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Exobiology'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Exobiology'
        assert params['from'] == 'Colonia'
        assert params['min_value'] == 5000000
        assert 'body_types' not in params

    def test_exobiology_min_value_slider_bounds(self, harness:TestHarness) -> None:
        """The Minimum Landmark Value slider should be a 0-20 range (millions implied),
        defaulting near 0 since Spansh's own default (100000 credits) rounds down to 0M."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Exobiology']
        slider = fr.nametowidget("min_value_entry")
        assert float(slider.cget('from')) == 0
        assert float(slider.cget('to')) == 20
        assert int(slider.get()) == 0

    def test_trade_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: TradePlotter.plot() must invoke plot_route with system/station (not
        from/to like every other plotter) and the numeric/boolean fields, and must refuse to
        submit when the typed station text doesn't resolve to a real station (single combined
        "System / Station" field, matching Spansh's own UI -- there's no separate system field
        to fall back on, and no separate system-resolving roundtrip either, since a validated
        match already carries both names -- see query_station_names())."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Trade']

        fr.nametowidget("station_ac").set_text("Not A Real Station", False)
        fr.nametowidget("starting_capital_entry").set_text("1000000", False)
        fr.nametowidget("max_cargo_entry").set_text("200", False)
        fr.nametowidget("max_hops_entry").set_text("5", False)
        fr.nametowidget("max_hop_distance_entry").set_text("50", False)
        fr.nametowidget("max_system_distance_entry").set_text("10000000", False)
        fr.nametowidget("station_ac").set_text("Shinrarta Dezhra / Jameson Memorial", False)
        with patch.object(ui, 'query_station_names', return_value=["Shinrarta Dezhra / Jameson Memorial"]):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Trade'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Trade'
        assert params['system'] == 'Shinrarta Dezhra'
        assert params['station'] == 'Jameson Memorial'
        assert params['starting_capital'] == '1000000'
        assert params['max_cargo'] == '200'
        assert 'max_price_age' not in params  # left blank -> no limit sent
        for flag in ['requires_large_pad', 'allow_prohibited', 'allow_planetary',
                     'allow_player_owned', 'allow_restricted_access', 'unique', 'permit']:
            assert params[flag] == 0  # none selected

    def test_tourist_add_remove_hop_rows(self, harness:TestHarness) -> None:
        """Adding/removing stop rows should track the right systems. Unlike the old
        destination-list design, an empty hop list is valid -- no forced minimum row."""
        ui = harness.plugin.ui
        plotter = ui.plotters['Tourist']

        assert len(plotter.hop_rows) == 0

        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        assert len(plotter.hop_rows) == 1

        plotter._add_hop_row(0)
        plotter.hop_rows[1]['ac'].set_text("Colonia", False)
        assert len(plotter.hop_rows) == 2
        assert plotter.hop_rows[0]['ac'].get() == "Deciat"

        plotter._remove_hop_row(0)
        assert len(plotter.hop_rows) == 1
        assert plotter.hop_rows[0]['ac'].get() == "Colonia"

        plotter._remove_hop_row(0)
        assert len(plotter.hop_rows) == 0

    def test_tourist_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """TouristPlotter.plot() must send source/destination(list)/range/loop, and must omit
        final_destination entirely (rather than sending literal "None") when left blank."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)

        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        plotter._add_hop_row(0)
        plotter.hop_rows[1]['ac'].set_text("Colonia", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Tourist'
        assert params['source'] == 'Sol'
        assert 'final_destination' not in params
        assert params['destination'] == ['Deciat', 'Colonia']
        assert params['range'] == '50'
        assert params['loop'] == 0

    def test_tourist_plotter_loop_checkbox(self, harness:TestHarness) -> None:
        """Tourist only ever has the one "loop" option, so it's a plain checkbox rather than
        the multi-select options listbox every other plotter uses."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        plotter.loop_var.set(1)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        _, params = mock_plot_route.call_args[0]
        assert params['loop'] == 1

    def test_tourist_plotter_final_destination_set(self, harness:TestHarness) -> None:
        """A non-blank final destination should be validated and included."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Colonia", False)
        fr.nametowidget("range_entry").set_text("50", False)
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        mock_plot_route.assert_called_once()
        _, params = mock_plot_route.call_args[0]
        assert params['final_destination'] == 'Colonia'

    def test_fleetcarrier_plotter_plot_calls_plot_route(self, harness:TestHarness) -> None:
        """FleetCarrierPlotter.plot() must resolve each system to an id64 (Spansh's API needs
        ids here, unlike every other route type) and send capacity/mass by carrier type."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['FleetCarrier']
        plotter = ui.plotters['FleetCarrier']

        fr.nametowidget("source_ac").set_text("Sol", False)
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        fr.nametowidget("capacity_used_entry").set_text("500", False)
        plotter.carrier_type.set('fleet')

        id_map = {'Sol': 10477373803, 'Deciat': 6681123623626}
        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(ui, 'resolve_system_id64', side_effect=lambda name: id_map[name]):
                with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                    plotter.plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'FleetCarrier'
        assert params['source_name'] == 'Sol'
        assert params['source'] == 10477373803
        assert params['destination_names'] == ['Deciat']
        assert params['destinations'] == [6681123623626]
        assert params['capacity'] == 25000
        assert params['mass'] == 25000
        assert params['capacity_used'] == '500'
        assert params['calculate_starting_fuel'] == 1

    def test_fleetcarrier_plotter_unresolved_system_shows_error(self, harness:TestHarness) -> None:
        """If a validated system name can't be resolved to an id64, plot() must bail with an
        error rather than sending a broken request."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['FleetCarrier']
        plotter = ui.plotters['FleetCarrier']

        fr.nametowidget("source_ac").set_text("Sol", False)

        with patch('requests.get', side_effect=fake_systems_get):
            with patch.object(ui, 'resolve_system_id64', return_value=None):
                with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                    plotter.plot()

        mock_plot_route.assert_not_called()


class TestUIFunctions:
    """ Test UI functions """

    def test_set_entry_none_does_nothing(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui
        # Should not raise or change state
        ui.set_entry(None, "ignored")

    def test_query_station_names(self, harness:TestHarness) -> None:
        """query_station_names() hits Spansh's station name typeahead directly -- a single
        field, matching Spansh's own "Source Station" combobox -- and formats each result as
        "System / Station" so the Trade Planner's single combined input field can validate a
        typed/selected value and split it back into system+station locally, with no separate
        system-resolving roundtrip (Spansh's own /api/trade/route call errors out on a bad
        system/station combo anyway, so there's nothing worth pre-verifying here)."""
        ui = harness.plugin.ui

        def fake_get(url, *args, **kwargs):
            resp = Mock()
            resp.status_code = 200
            resp.content = json.dumps([
                {"system": "Shinrarta Dezhra", "name": "Jameson Memorial"}
            ]).encode()
            return resp

        with patch('requests.get', side_effect=fake_get):
            assert ui.query_station_names('Jameson') == ['Shinrarta Dezhra / Jameson Memorial']

    def test_resolve_system_id64(self, harness:TestHarness) -> None:
        """resolve_system_id64() is needed only by Fleet Carrier -- every other route type
        sends plain system names, but Spansh's fleetcarrier API needs an id64."""
        ui = harness.plugin.ui

        def fake_get(url, *args, **kwargs):
            resp = Mock()
            resp.status_code = 200
            resp.content = json.dumps({"results": [{"id64": 10477373803, "name": "Sol"}]}).encode()
            return resp

        with patch('requests.get', side_effect=fake_get):
            assert ui.resolve_system_id64('Sol') == 10477373803
            assert ui.resolve_system_id64('Not Sol') is None  # no exact match


    # def test_combobox_bind_fires_on_dark_mode_selection(self, harness:TestHarness) -> None:
    #     """Regression: th.ComboBox.bind("<<ComboboxSelected>>", ...) only ever bound the
    #     light-mode ttk.Combobox half. Its dark-mode alt is a tk.OptionMenu, which has no
    #     <<ComboboxSelected>> virtual event -- each menu entry just runs tk._setit() to update
    #     the shared StringVar directly, so the bound callback silently never fired when the
    #     theme was dark. bind() must wire the callback into each menu entry's own command so a
    #     real dark-mode click still triggers it -- but a plain var.set() from elsewhere (e.g.
    #     ui.show_frame() syncing this same combobox after handling the selection) must NOT
    #     retrigger it, or callback <-> show_frame() loops forever and hangs the UI (this was
    #     tried first via a variable write-trace, which doesn't distinguish the two)."""
    #     var = tk.StringVar(harness.root, value="A")
    #     combo = th.ComboBox(harness.root, var, values=["A", "B", "C"])

    #     calls:list = []
    #     combo.bind("<<ComboboxSelected>>", lambda e: calls.append(var.get()))

    #     combo.alt["menu"].invoke(1)  # simulate a real dark-mode click on "B"
    #     assert calls == ["B"]

    #     calls.clear()
    #     var.set("B")  # simulate show_frame() syncing the widget back to the same value
    #     assert calls == []


    def test_switch_ship(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui

        # Ensure a ship loadout is present
        harness.play_sequence('loadout')
        ship = harness.plugin.router.ship
        assert ship is not None

        # Switch UI to this ship and verify fields update
        ui.switch_ship(ship)
        assert ui.plotters['Galaxy'].shipvar.get() == ship.name
        assert ui.plotters['Neutron'].multiplier.get() == ship.supercharge_multiplier
        assert ui.get_item('Neutron', 'range_entry') == str(ship.get_range(harness.plugin.router.cargo))

    def test_progress(self, harness:TestHarness):
        """ Test _progress() method"""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        harness.plugin.router.import_route(filename)
        harness.plugin.route.update_route(0, 'Bleia Eohn ZL-J d10-47')

        assert harness.plugin.ui._progress() == 2

    def test_update_cargo(self, harness:TestHarness):
        """ test update_cargo() method """
        ui = harness.plugin.ui
        ui.update_cargo(12)

        # Update cargo and verify cargo and range entries update
        assert ui.get_item('Galaxy', 'cargo_entry') == '12'
        assert ui.get_item('Neutron', 'range_entry') == str(harness.plugin.router.ship.get_range(12))

class TestRouteWindow:
    """Test RouteWindow lifecycle and display behavior."""

    def _cleanup_window(self, window: RouteWindow) -> None:
        if window.window is not None:
            try:
                if window.window.winfo_exists():
                    window.close()
            except tk.TclError:
                pass
        window.window = None

    def test_window_is_singleton(self, harness: TestHarness) -> None:
        """RouteWindow should reuse the existing singleton instance."""
        from Router.route_window import RouteWindow
        window:RouteWindow = harness.plugin.ui.window_route
        duplicate:RouteWindow = RouteWindow(harness.parent.winfo_toplevel())

        assert duplicate is window
        self._cleanup_window(window)

    def test_show_ignores_empty_route(self, harness: TestHarness) -> None:
        """show() should not create a window for an empty route."""
        window:RouteWindow = harness.plugin.ui.window_route
        route = Route()

        window.show(route)
        assert window.window is None

    def test_show_creates_window_for_populated_route(self, harness: TestHarness) -> None:
        """show() should create a toplevel window for a populated route."""
        window: RouteWindow = harness.plugin.ui.window_route

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None

        window.window.update_idletasks()
        assert window.window.winfo_exists() == 1
        assert window.window.title() == f"{NAME} – {lbls['route']}"

        self._cleanup_window(window)

    def test_close_saves_geometry_and_destroys_window(self, harness: TestHarness) -> None:
        """close() should persist geometry and destroy the current window."""
        window: RouteWindow = harness.plugin.ui.window_route
        window.root.withdraw()  # Hide the main window to prevent test interference
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None

        window.window.update_idletasks()
        window.window.geometry("640x360+10+20")
        window.window.update_idletasks()
        geometry:str = window.window.winfo_geometry()
        window_ref = window.window

        window.close()

        assert harness.plugin.router.window_geometries['route'] == geometry
        assert window_ref.winfo_exists() == 0
        window.window = None

    def test_show_recreates_existing_window(self, harness: TestHarness) -> None:
        """show() should replace an existing RouteWindow instance with a fresh toplevel."""
        window:RouteWindow = harness.plugin.ui.window_route
        window.root.withdraw()  # Hide the main window to prevent test interference
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None
        first_window = window.window

        window.show(harness.plugin.route)
        assert window.window is not None
        assert window.window is not first_window
        assert first_window.winfo_exists() == 0
        assert window.window.winfo_exists() == 1

        self._cleanup_window(window)

    def test_show_renders_summary_section(self, harness: TestHarness) -> None:
        """show() should render summary labels for progress, jumps and distance."""
        window:RouteWindow = harness.plugin.ui.window_route
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference
        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        summary_frame = container.winfo_children()[0]
        label_texts: list[str] = [
            widget.cget("text")
            for widget in summary_frame.winfo_children()
            if isinstance(widget, ttk.Label)
        ]

        assert lbls['progress'].title() in label_texts
        assert lbls['jumps'].title() in label_texts
        assert any(text.endswith('%') for text in label_texts)

        if harness.plugin.route.total_dist() > 0:
            assert lbls['distance'].title() in label_texts
        else:
            assert lbls['distance'].title() not in label_texts

        self._cleanup_window(window)

    def test_show_renders_table_columns_rows_and_selection(self, harness: TestHarness) -> None:
        """show() should render table headings/rows and select the current route offset row."""
        window: RouteWindow = harness.plugin.ui.window_route
        filename: str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True
        harness.plugin.route.offset = 1

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        table_frame = container.winfo_children()[1]
        tree = next(
            widget for widget in table_frame.winfo_children()
            if isinstance(widget, ttk.Treeview)
        )

        assert tuple(tree["columns"]) == tuple(harness.plugin.route.hdrs)
        children = tree.get_children()
        assert len(children) == len(harness.plugin.route.route)

        selected = tree.selection()
        assert len(selected) == 1
        selected_values = tree.item(selected[0], "values")
        assert selected_values[0] == harness.plugin.route.route[harness.plugin.route.offset][0]

        self._cleanup_window(window)

    def test_table_selection_copies_system_name(self, harness: TestHarness) -> None:
        """Selecting a table row should copy the system name to the clipboard."""
        from Router.route_window import RouteWindow
        window: RouteWindow = harness.plugin.ui.window_route
        filename: str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference
        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        table_frame = container.winfo_children()[1]
        tree:TreeviewPlus = next(
            widget for widget in table_frame.winfo_children()
            if isinstance(widget, TreeviewPlus)
        )

        first_item = tree.get_children()[0]
        first_values = list(tree.item(first_item, "values"))

        assert hasattr(tree, "callback")
        if tree and tree.callback:
            tree.callback(first_values, 0, tree, first_item)

        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == first_values[0]

        self._cleanup_window(window)


class TestRouteWindowUI:
    """Test RouteWindow display logic and edge cases."""

    def test_empty_headers_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty headers - should return without error."""
        from Router.route_window import RouteWindow
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = harness.plugin.route
        assert empty_route.hdrs == []
        assert window.window is None or not window.window.winfo_exists()

    def test_empty_cols_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty columns - should return without error."""
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = Route(['System Name', 'Jumps'], [], 0)
        # Empty route should not crash
        assert empty_route.hdrs == ['System Name', 'Jumps']
        assert empty_route.route == []

    def test_route_with_data_empty_window(self, harness:TestHarness) -> None:
        """Test show() with data but window doesn't exist - should create window."""

        # Create a minimal route with system names
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.hdrs == hdrs
        assert len(route.route) == 3
        assert route.source() == 'Sol'
        assert route.destination() == 'Bleae Thua'

    def test_route_with_tritium_column(self, harness:TestHarness) -> None:
        """Test fleet carrier route with tritium column."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['System A', 5, 50, 'True'],  # Tritium at this waypoint
            ['System B', 10, 45, 'True'],
            ['System C', 8, 50, 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Dist Rem', 'Tritium']
        route = Route(hdrs, route_data, 0)

        assert route.fleetcarrier == True
        assert route.refuel() == False  # Depends on refuel column

    def test_next_stop_current_waypoint(self, harness:TestHarness) -> None:
        """Test next_stop() at current waypoint."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.next_stop() == 'Apurui'  # Next after current (Sol)

    def test_next_stop_complete_route(self, harness:TestHarness) -> None:
        """Test next_stop() when route is complete."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 2)  # At last waypoint

        assert route.next_stop() == 'End of the road!'  # lbls['route_complete']

    def test_jumps_remaining_at_start(self, harness:TestHarness) -> None:
        """Test jumps_remaining() at start of route."""
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.jumps_remaining() == 15  # 10 + 5

    def test_jumps_remaining_incomplete(self, harness:TestHarness) -> None:
        """Test jumps_remaining() mid-route."""

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        route.update_route(1)  # Move to Apurui
        assert route.jumps_remaining() == 5  # Only Bleae Thua remains

    def test_perc_jumps_rem_at_start(self, harness:TestHarness) -> None:
        """Test percentage of jumps remaining at start."""

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]

        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        total = route.total_jumps()
        remaining = route.jumps_remaining()
        assert route.perc_jumps_rem() == (total - remaining) * 100 / total

    def test_perc_jumps_rem_complete(self, harness:TestHarness) -> None:
        """Test percentage of jumps remaining at end."""

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]

        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)
        assert route.perc_jumps_rem(2) == 100.0


    def test_dist_remaining_at_start(self, harness:TestHarness) -> None:
        """Test dist_remaining() at start."""

        route_data = [
            ['Sol', 0, 150],
            ['Apurui', 10, 100],
            ['Bleae Thua', 5, 50]
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0)

        assert route.dist_remaining() == 150

    def test_dist_remaining_mid_route(self, harness:TestHarness) -> None:
        """Test dist_remaining() mid-route."""

        route_data = [
            ['Sol', 0, 150],
            ['Apurui', 10, 100],
            ['Bleae Thua', 5, 50]
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0)

        route.update_route(1)  # Move to Apurui
        assert route.dist_remaining() == 100  # Distance to Bleae Thua

    def test_refuel_check(self, harness:TestHarness) -> None:
        """Test refuel() method."""

        route_data = [
            ['Sol', 0, 'Fuel'],
            ['Apurui', 10, 'No'],
            ['Bleae Thua', 5, 'Fuel']
        ]
        hdrs = ['System Name', 'Jumps', 'Refuel']
        route = Route(hdrs, route_data, 0)

        # Check next waypoint for refuel
        route.update_route(1)  # Now at Apurui
        assert route.refuel() == False  # Apurui doesn't refuel

    def test_neutron_check(self, harness:TestHarness) -> None:
        """Test neutron() method."""

        route_data = [
            ['Sol', 0, 'False'],
            ['Apurui', 10, 'True'],
            ['Bleae Thua', 5, 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Neutron']
        route = Route(hdrs, route_data, 0)

        # Check if next waypoint needs neutron
        route.update_route(1)  # Now at Apurui
        assert route.is_neutron() == False  # Bleae Thua doesn't need neutron

    def test_get_waypoint_next(self, harness:TestHarness) -> None:
        """Test get_waypoint() for next waypoint."""

        route_data = [
            ['A', 0],
            ['B', 1],
            ['C', 2]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.get_waypoint(0) == 'B'

    def test_get_waypoint_end(self, harness:TestHarness) -> None:
        """Test get_waypoint() at end of route."""

        route_data = [
            ['A', 0],
            ['B', 1]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 1)

        assert route.get_waypoint(0) == 'None'  # tbls['none']

    def test_record_jump(self, harness:TestHarness) -> None:
        """Test record_jump() method."""

        route_data = [
            ['Sol', 0]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        # Record a jump
        dest = 'Jupiter'
        dist = 2.5
        route.record_jump(dest, dist)

        assert len(route.jumps) == 1
        assert route.jumps[0][1] == dest
        assert abs(route.jumps[0][2] - dist) < 0.01  # Allow for rounding

class TestPlotting:
    """Test end to end plotting functionality (neutron/galaxy routes)."""

    def test_plot_route_unknown_type(self, harness:TestHarness):
        """Unknown plot types should return False and not start plotting."""
        result:bool = harness.plugin.router.plot_route('UnsupportedType', {})
        assert result is False

    @pytest.mark.slow
    def test_plot_neutron_route(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Neutron',
                                                {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                                'range': '60.00', 'efficiency': '60',
                                                'supercharge_multiplier': '4'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=66)

            assert harness.plugin.route is not None
            assert harness.plugin.route.source() == 'Apurui'
            assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
            assert harness.plugin.route.total_jumps() == 31

    @pytest.mark.slow
    def test_plot_neutron_route_caspian(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot for a Caspian explorer """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Neutron',
                                                {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                                'range': '60.00', 'efficiency': '60',
                                                'supercharge_multiplier': '6'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=22)

            assert harness.plugin.route is not None
            assert harness.plugin.route.source() == 'Apurui'
            assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
            assert harness.plugin.route.total_jumps() == 21

    @pytest.mark.slow
    def test_plot_galaxy_route(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot and check results."""
        global plotter_thread
        plotter_thread = None

        harness.plugin.router.swap_ship(1)
        ship = harness.plugin.router.ship
        print(f"{ship}")
        assert ship is not None
        assert ship.name == 'Shipping Delay'
        assert harness.plugin.route.route == []

        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "optimistic",
            "fuel_reserve": 4,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 1,
            "refuel_every_scoopable": 0,
            "fuel_power": ship.fuel_power,
            "fuel_multiplier": ship.fuel_multiplier,
            "optimal_mass": ship.optimal_mass,
            "base_mass": ship.base_mass,
            "tank_size": ship.tank_size,
            "internal_tank_size": ship.internal_tank_size,
            "max_fuel_per_jump": ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": ship.loadout,
            "supercharge_multiplier": ship.supercharge_multiplier,
            "injection_multiplier": ship.injection_multiplier,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        assert ship.fuel_power == 2.45
        assert ship.fuel_multiplier == 0.013
        assert ship.optimal_mass == 1894.1
        assert ship.base_mass == 297.3
        assert ship.tank_size == 32
        assert ship.internal_tank_size == 0.5
        assert ship.max_fuel_per_jump == 5.2

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
            assert res == True

            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=66)

            assert harness.plugin.router.src == 'Apurui'
            assert harness.plugin.router.dest == 'Bleae Thua NI-B b27-5'

            # This route seems to vary based on current conditions
            assert harness.plugin.route.total_jumps() in [18, 21, 28], f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_galaxy_route_caspian(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot with a caspian explorer and check results."""
        global plotter_thread
        plotter_thread = None

        harness.plugin.router.swap_ship(2)
        ship = harness.plugin.router.ship
        assert ship is not None
        assert ship.name == 'Perviy'
        assert harness.plugin.route.route == []

        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "optimistic",
            "fuel_reserve": 12,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 0,
            "refuel_every_scoopable": 0,
            "fuel_power": ship.fuel_power,
            "fuel_multiplier": ship.fuel_multiplier,
            "optimal_mass": ship.optimal_mass,
            "base_mass": ship.base_mass,
            "tank_size": ship.tank_size,
            "internal_tank_size": ship.internal_tank_size,
            "max_fuel_per_jump": ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": ship.loadout,
            "supercharge_multiplier": ship.supercharge_multiplier,
            "injection_multiplier": ship.injection_multiplier,
            "source": "HIP 87621",
            "destination": "Bleae Thua ED-D c12-5"
        }

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
            assert res == True

            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=62)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == galaxy_params['source']
            assert harness.plugin.router.dest == galaxy_params['destination']
            assert harness.plugin.route.total_jumps() == 9, f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_rtor_route(self, harness:TestHarness) -> None:
        """ Perform a live Road-to-Riches plot """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('RtoR',
                                                {'from': 'Colonia', 'range': '50', 'radius': '40',
                                                'max_results': '20', 'avoid_thargoids': '1', 'loop': '1'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=66)

            assert harness.plugin.route is not None
            # router.src reflects the queried source system; the route table itself only lists
            # systems with scannable bodies, so its first row's source() is a body name, not 'Colonia'.
            assert harness.plugin.router.src == 'Colonia'
            assert harness.plugin.route.source() != None
            assert "Body Name" in harness.plugin.route.hdrs
            assert "Estimated Scan Value" in harness.plugin.route.hdrs
            # Don't assert an exact body/jump count: which bodies are still unscanned
            # (and therefore appear in a riches route) changes over time in the live galaxy.
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_ammonia_route(self, harness:TestHarness) -> None:
        """ Perform a live Ammonia World plot -- representative of the body-type-filtered
        riches variants (Ammonia/Earth-like/Rocky-metal), which all share the same
        /api/riches/route pipeline already exercised by test_plot_rtor_route above.
        Ammonia worlds are rare, and completion time depends on Spansh's shared job
        queue as much as search size, so this allows several minutes rather than the
        ~20s default used for plain (unfiltered) riches routes. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Ammonia',
                                                {'from': 'Colonia', 'range': '50', 'radius': '150',
                                                'max_results': '20', 'avoid_thargoids': '1', 'loop': '1',
                                                'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 240})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=250)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Colonia'
            assert "Body Name" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_exobiology_route(self, harness:TestHarness) -> None:
        """ Perform a live Exobiology (Expressway to Exomastery) plot. Unlike the plain
        body-value riches routes, this checks for Species/Landmark Value columns, since
        that's the whole point of this route type. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Exobiology',
                                                {'from': 'Colonia', 'range': '50', 'radius': '30',
                                                'max_results': '10', 'avoid_thargoids': '1', 'loop': '1',
                                                'min_value': 100000, 'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=70)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Colonia'
            assert "Species" in harness.plugin.route.hdrs
            assert "Landmark Value" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_trade_route(self, harness:TestHarness) -> None:
        """ Perform a live Trade Planner plot from a busy hub (Jameson Memorial), which needs
        real time server-side to check commodity prices across many nearby stations. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Trade',
                                                {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                                                'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                                                'max_hop_distance': '50', 'max_system_distance': '10000000',
                                                'requires_large_pad': '0', 'allow_prohibited': '0',
                                                'allow_planetary': '0', 'allow_player_owned': '0',
                                                'allow_restricted_access': '0', 'unique': '0', 'permit': '0',
                                                'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=70)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Shinrarta Dezhra'
            assert "Station Name" in harness.plugin.route.hdrs
            assert "Commodity" in harness.plugin.route.hdrs
            assert "Cumulative Profit" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_tourist_route(self, harness:TestHarness) -> None:
        """ Perform a live Tourist Route plot between a handful of systems close to Sol,
        so the real route computation stays fast. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Tourist',
                                                {'source': 'Sol', 'destination': ['Alpha Centauri', "Barnard's Star"],
                                                'range': '50', 'loop': '0', 'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=70)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Sol'
            assert "System Name" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0


class TestEventSequences:
    """Test complex multi-step event scenarios."""

    @pytest.mark.manual_only
    @pytest.mark.slow
    def test_full_route_scenario(self, harness:TestHarness):
        """Test a complete route scenario with jumps."""
        harness.plugin.router.system = 'Apurui'

        # Import a route
        filename:str = str(Path(__file__).parent / "config" / "full-route-scenario.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        # Follow the route
        for event in harness.events.get('full_route_scenario', []):
            harness.fire_event(event)
            match event.get('event'):
                case 'ShipyardSwap':
                    assert harness.plugin.router.ship_id == str(event.get('ShipID'))
                case 'Location' | 'FSDJump':
                    assert harness.plugin.router.system == event.get('StarSystem', '')
                    assert "Next: " + harness.plugin.route.next_stop() == harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]

        # Final state check
        assert harness.plugin.route.jumps_remaining() == 0
        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"].startswith("PD jc=4 jr=0 jt=4 dc=304 dr=0 dt=304")

    @pytest.mark.overlay('None')
    @pytest.mark.slow
    def test_full_route_scenario_no_overlay(self, harness:TestHarness):
        """Test a complete route scenario with jumps."""
        harness.plugin.router.system = 'Apurui'

        # Import a route
        filename:str = str(Path(__file__).parent / "config" / "full-route-scenario.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        # Follow the route
        for event in harness.events.get('full_route_scenario', []):
            harness.fire_event(event)
            match event.get('event'):
                case 'ShipyardSwap':
                    assert harness.plugin.router.ship_id == str(event.get('ShipID'))
                case 'Location' | 'FSDJump':
                    assert harness.plugin.router.system == event.get('StarSystem', '')

        # Final state check
        assert harness.plugin.route.jumps_remaining() == 0

    @pytest.mark.slow
    def test_carrier_jump_noroute(self, harness:TestHarness) -> None:
        """Test carrier jump with docking."""
        from Router.constants import CarrierStates
        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown

    @pytest.mark.slow
    def test_carrier_jump_route(self, harness:TestHarness):
        """Test carrier jump with docking."""
        from Router.constants import CarrierStates
        filename:str = str(Path(__file__).parent / "config" / "vc-Bleae-Voqooe.csv")
        harness.plugin.router.import_route(filename)

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown
