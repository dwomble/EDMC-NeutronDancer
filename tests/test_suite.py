"""
Test suite for EDMC Neutron Dancer plugin using pytest.
"""
import pytest # type: ignore
import sys
import os
import shutil
from pathlib import Path
from typing import Generator
from time import sleep
from unittest.mock import Mock, patch
import json
import time
import logging
import tkinter as tk
from tkinter import ttk
import threading

from urllib3 import request

from utils.treeviewplus import TreeviewPlus

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

# Config is already mocked by conftest.py
from harness import TestHarness
from Router.constants import CarrierStates, SPANSH_ROUTE, NAME, lbls
from Router.route import Route
from Router.ship import Ship
from Router.route_window import RouteWindow

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

plotter_thread = None
def capture_thread(*args, **kwargs):
    global plotter_thread

    thread = threading.Thread(*args, **kwargs)
    if kwargs.get('name', '') == "Neutron Dancer route plotting worker":
        plotter_thread = thread
    return thread

@pytest.fixture
def harness() -> Generator:
    """Provide a fresh test harness for each test."""

    # We want a standard route.json for each test
    Path(__file__).parent.joinpath("data").mkdir(exist_ok=True)
    shutil.copy(Path(__file__).parent / "config" / "route_init.json",
                Path(__file__).parent / "data" / "route.json")

    # Almost every test needs to be live.
    test_harness = TestHarness(live_requests=True)
    test_harness.set_edmc_config()

    # This is ND-specific. /assets is where the images are stored
    import Router.constants
    Router.constants.ASSET_DIR = "../assets"

    from load import plugin_start3, plugin_app, journal_entry

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

    yield test_harness

    # Need to clear the singleton.
    delattr(test_harness.plugin.router, "_initialized")


class TestStartup:
    """Test plugin startup behavior."""

    def test_harness_initialization(self, harness:TestHarness) -> None:
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
        assert len(harness.plugin.modules) == 89
class TestStateManagement:
    """Test router state management."""

    def test_load(self, harness:TestHarness) -> None:
        """Call plugin load"""
        harness.plugin.router._load()

    def test_save(self, harness:TestHarness) -> None:
        """Call save"""
        harness.plugin.router.save()

class TestShipLoadout:
    """Test ship loadout and switching."""

    def test_bad_event(self, harness:TestHarness) -> None:
        """Test bad loadout event."""
        harness.fire_event({"event": "bad", "Ship":"naughty", "ShipID":100000, "ShipName":"Dummy", "ShipIdent":"Dumdum"})

        assert hasattr(harness.plugin.router.ship, "ship_id") == False

    def test_loadout_event(self, harness:TestHarness) -> None:
        """Test loading a ship."""

        harness.play_sequence('loadout')
        shipid:str = '87'
        assert harness.plugin.router.ship_id == shipid
        assert harness.plugin.router.ship is not None
        assert harness.plugin.router.ship.type == 'mandalay'
        assert harness.plugin.router.ship.name == 'Long Delay'
        assert harness.plugin.router.neutron_params['supercharge_multiplier'] == harness.plugin.router.ship.supercharge_multiplier
        assert harness.plugin.router.neutron_params['range'] == harness.plugin.router.ship.range
        assert harness.plugin.router.ships[shipid] is harness.plugin.router.ship


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
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[0])
        assert harness.plugin.route.next_stop() == 'Bleae Thua ZJ-I d9-101'

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
        harness.plugin.router.update_route(1)
        assert harness.plugin.route.next_stop() == 'Bleae Thua ZJ-I d9-101'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_no_previous(self, harness:TestHarness):
        """Test prev/previous command when at the beginning of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_copy(self, harness:TestHarness):
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[2])
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == 'Bleae Thua RX-L d7-28'

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
        harness.play_sequence('shipyard_swap')
        assert harness.plugin.router.ship_id == '106'

        harness.play_sequence('shipyard_swap_unknown')
        assert harness.plugin.router.ship_id == ''


class TestOverlay:
    """Test overlay functionality."""

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

        called:dict[str, bool] = {'flag': False}

        def fake_countdown(self, frame, content, end, stop) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.plugin.overlay), '_countdown', fake_countdown, raising=False)
        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[2])
        assert harness.plugin.overlay.msgs != {}
        harness.plugin.overlay.clear_frames()
        assert harness.plugin.overlay.msgs == {}

class TestEventSequences:
    """Test complex multi-step event scenarios."""

    def test_full_route_scenario(self, harness:TestHarness):
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
                    assert harness.plugin.route.next_stop() in json.dumps(harness.plugin.overlay.msgs)

        # Final state check
        assert harness.plugin.route.jumps_remaining() == 0

    def test_carrier_jump_noroute(self, harness:TestHarness) -> None:
        """Test carrier jump with docking."""
        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown

    def test_carrier_jump_route(self, harness:TestHarness):
        """Test carrier jump with docking."""
        filename:str = str(Path(__file__).parent / "config" / "vc-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown

class TestPlotOperations:
    """Test individual plotting functions"""

    def test_plot_route_starts_thread(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure plot_route returns True and starts the plotting worker."""
        called:dict[str, bool] = {'flag': False}

        def fake_plotter(self, url, params) -> None:
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

        # No exception should be raised; Context.ui.show_error would be called
        # Not sure how to capture the error message
        #assert harness.ui.error_lbl['text'] == 'server error'

    def test_plotter(self, harness:TestHarness):
        """Test the _plotter function"""

        harness.plugin.router._plotter(SPANSH_ROUTE,
                                {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                'range': '60.00', 'efficiency': '60',
                                'supercharge_multiplier': '4'})
        assert len(harness.plugin.route.hdrs) == 6
        assert len(harness.plugin.route.route) == 9

class TestPlotting:
    """Test end to end plotting functionality (neutron/galaxy routes)."""

    def test_plot_route_unknown_type(self, harness:TestHarness):
        """Unknown plot types should return False and not start plotting."""
        result:bool = harness.plugin.router.plot_route('UnsupportedType', {})
        assert result is False

    @pytest.mark.manual_only
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

    @pytest.mark.manual_only
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

    @pytest.mark.manual_only
    def test_plot_galaxy_route(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot and check results."""
        global plotter_thread
        plotter_thread = None

        harness.plugin.router.swap_ship(1)
        ship = harness.plugin.router.ship
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

    @pytest.mark.manual_only
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
        assert len(tree.get_children()) == len(harness.plugin.route.route)

        selected = tree.selection()
        assert len(selected) == 1
        selected_values = tree.item(selected[0], "values")
        assert selected_values[0] == harness.plugin.route.route[harness.plugin.route.offset][0]

        self._cleanup_window(window)

    def test_table_selection_copies_system_name(self, harness: TestHarness) -> None:
        """Selecting a table row should copy the system name to the clipboard."""
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


class DisabledRouteWindowDisplay:
    """Test RouteWindow display logic and edge cases."""

    def test_empty_headers_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty headers - should return without error."""
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = harness.plugin.route
        assert empty_route.hdrs == []
        assert window.window is None or not window.window.winfo_exists()

    def test_empty_cols_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty columns - should return without error."""
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = Route(['System Name', 'Jumps'], [], 0, [])
        # Empty route should not crash
        assert empty_route.hdrs == ['System Name', 'Jumps']
        assert empty_route.route == []

    def test_route_with_data_empty_window(self, harness:TestHarness) -> None:
        """Test show() with data but window doesn't exist - should create window."""

        # Create a minimal route with system names
        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        assert route.hdrs == hdrs
        assert len(route.route) == 3
        assert route.source() == 'Sol'
        assert route.destination() == 'Bleae Thua'

    def test_route_with_neutron_column(self, harness:TestHarness) -> None:
        """Test route with neutron column."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', '0', 'False'],
            ['Apurui', '10', 'True'],
            ['Bleae Thua', '5', 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Neutron']
        route = Route(hdrs, route_data, 0, route_data)

        assert route.refuel() == False
        assert route.neutron() == False  # Next waypoint doesn't need neutron

    def test_route_with_tritium_column(self, harness:TestHarness) -> None:
        """Test fleet carrier route with tritium column."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['System A', '5', '50', 'True'],  # Tritium at this waypoint
            ['System B', '10', '45', 'True'],
            ['System C', '8', '50', 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Dist Rem', 'Tritium']
        route = Route(hdrs, route_data, 0, route_data)

        assert route.fleetcarrier == True
        assert route.refuel() == False  # Depends on refuel column

    def test_next_stop_current_waypoint(self, harness:TestHarness) -> None:
        """Test next_stop() at current waypoint."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        assert route.next_stop() == 'Apurui'  # Next after current (Sol)

    def test_next_stop_complete_route(self, harness:TestHarness) -> None:
        """Test next_stop() when route is complete."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 2, [])  # At last waypoint

        assert route.next_stop() == 'End of the road!'  # lbls['route_complete']

    def test_jumps_to_system(self, harness:TestHarness) -> None:
        """Test jumps_to_system() method."""
        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, route_data)

        # First system (offset 0)
        assert route.jumps_to_system() == 0  # Already there
        # After first jump (offset 1)
        route.update_route(1)
        assert route.jumps_to_system() == 5  # Jumps to Bleae Thua

    def test_jumps_remaining_at_start(self, harness:TestHarness) -> None:
        """Test jumps_remaining() at start of route."""
        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, route_data)

        assert route.jumps_remaining() == 15  # 10 + 5

    def test_jumps_remaining_incomplete(self, harness:TestHarness) -> None:
        """Test jumps_remaining() mid-route."""

        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, route_data)

        route.update_route(1)  # Move to Apurui
        assert route.jumps_remaining() == 5  # Only Bleae Thua remains

    def test_perc_jumps_rem_at_start(self, harness:TestHarness) -> None:
        """Test percentage of jumps remaining at start."""

        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, route_data)

        total = route.total_jumps()
        remaining = route.jumps_remaining()
        assert route.perc_jumps_rem() == (total - remaining) * 100 / total

    def test_perc_jumps_rem_complete(self, harness:TestHarness) -> None:
        """Test percentage of jumps remaining at end."""

        route_data = [
            ['Sol', '0'],
            ['Apurui', '10'],
            ['Bleae Thua', '5']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, route_data)

        route.update_route(2)  # Move to last waypoint (Bleae Thua)
        assert route.perc_jumps_rem() == 0

    def test_total_dist(self, harness:TestHarness) -> None:
        """Test total_dist() method."""

        # Use a route with distance column
        route_data = [
            ['Sol', '0', '0'],
            ['Apurui', '10', '100'],
            ['Bleae Thua', '5', '50']
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0, route_data)

        assert route.total_dist() == 100  # At start, total distance

    def test_dist_remaining_at_start(self, harness:TestHarness) -> None:
        """Test dist_remaining() at start."""

        route_data = [
            ['Sol', '0', '0'],
            ['Apurui', '10', '100'],
            ['Bleae Thua', '5', '50']
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0, route_data)

        assert route.dist_remaining() == 0  # Sol has 0 distance remaining

    def test_dist_remaining_mid_route(self, harness:TestHarness) -> None:
        """Test dist_remaining() mid-route."""

        route_data = [
            ['Sol', '0', '0'],
            ['Apurui', '10', '100'],
            ['Bleae Thua', '5', '50']
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0, route_data)

        route.update_route(1)  # Move to Apurui
        assert route.dist_remaining() == 100  # Distance to Bleae Thua

    def test_refuel_check(self, harness:TestHarness) -> None:
        """Test refuel() method."""

        route_data = [
            ['Sol', '0', 'Fuel'],
            ['Apurui', '10', 'No'],
            ['Bleae Thua', '5', 'Fuel']
        ]
        hdrs = ['System Name', 'Jumps', 'Refuel']
        route = Route(hdrs, route_data, 0, route_data)

        # Check next waypoint for refuel
        route.update_route(1)  # Now at Apurui
        assert route.refuel() == False  # Apurui doesn't refuel

    def test_neutron_check(self, harness:TestHarness) -> None:
        """Test neutron() method."""

        route_data = [
            ['Sol', '0', 'False'],
            ['Apurui', '10', 'True'],
            ['Bleae Thua', '5', 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Neutron']
        route = Route(hdrs, route_data, 0, route_data)

        # Check if next waypoint needs neutron
        route.update_route(1)  # Now at Apurui
        assert route.neutron() == False  # Bleae Thua doesn't need neutron

    def test_get_waypoint_next(self, harness:TestHarness) -> None:
        """Test get_waypoint() for next waypoint."""

        route_data = [
            ['A', '0'],
            ['B', '1'],
            ['C', '2']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        assert route.get_waypoint(0) == 'B'

    def test_get_waypoint_end(self, harness:TestHarness) -> None:
        """Test get_waypoint() at end of route."""

        route_data = [
            ['A', '0'],
            ['B', '1']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 1, [])

        assert route.get_waypoint(0) == 'none'  # tbls['none']

    def test_update_route_forward(self, harness:TestHarness) -> None:
        """Test update_route() moves forward."""

        route_data = [
            ['A', '0'],
            ['B', '1'],
            ['C', '2']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        initial_offset = route.offset
        result = route.update_route(1)
        assert result == initial_offset + 1
        assert route.offset == initial_offset + 1

    def test_update_route_backward(self, harness:TestHarness) -> None:
        """Test update_route() moves backward."""

        route_data = [
            ['A', '0'],
            ['B', '1'],
            ['C', '2']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 2, [])

        final_offset = route.offset
        result = route.update_route(-1)
        assert result == final_offset - 1
        assert route.offset == final_offset - 1

    def test_update_route_beyond_end(self, harness:TestHarness) -> None:
        """Test update_route() beyond end of route."""

        route_data = [
            ['A', '0'],
            ['B', '1'],
            ['C', '2']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        result = route.update_route(100)  # Way beyond
        assert route.offset == len(route_data) - 1  # Stay at last valid position

    def test_update_route_before_start(self, harness:TestHarness) -> None:
        """Test update_route() before start of route."""

        route_data = [
            ['A', '0'],
            ['B', '1'],
            ['C', '2']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        result = route.update_route(-100)  # Way before
        assert route.offset == 0  # Stay at first position

    def test_record_jump(self, harness:TestHarness) -> None:
        """Test record_jump() method."""

        route_data = [
            ['Sol', '0']
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0, [])

        # Record a jump
        dest = 'Jupiter'
        dist = 2.5
        route.record_jump(dest, dist)

        assert len(route.jumps) == 1
        assert route.jumps[0][1] == dest
        assert abs(route.jumps[0][2] - dist) < 0.01  # Allow for rounding
