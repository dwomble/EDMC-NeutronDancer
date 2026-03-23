"""
Test suite for EDMC Neutron Dancer plugin using pytest.

Run with: .venv/bin/python -m pytest tests/test_plugin.py -v --tb=short 2>&1 | tail -30
Run with: .venv_win\\Scripts\\python.exe -m pytest tests\\test_plugin.py -v --tb=short
"""

import pytest # type: ignore
import sys
import os
import shutil
from pathlib import Path
from typing import Generator, Optional
from time import sleep
from unittest.mock import Mock, patch, MagicMock
import json
import time
import logging
import tkinter as tk

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

# Config is already mocked by conftest.py
from harness import TestHarness
from Router.constants import CarrierStates, SPANSH_ROUTE
from Router.route import Route

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@pytest.fixture
def harness() -> Generator:
    """Provide a fresh test harness for each test."""

    # We want a standard route.json for each test
    shutil.copy(Path(__file__).parent / "config" / "route_init.json", 
                Path(__file__).parent / "data" / "route.json")

    test_harness = TestHarness() 
    test_harness.set_edmc_config()

    # This is ND-specific. /assets is where the images are stored
    import Router.constants
    Router.constants.ASSET_DIR = "../assets"

    from load import plugin_start3, plugin_app, journal_entry

    plugin_start3(str(test_harness.plugin_dir))
    plugin_app(test_harness.parent)

    # ND-specific, this is our plugin object
    from Router.context import Context
    test_harness.plugin = Context
    
    # ND-specific, this is the journal handling function and the default journal params
    test_harness.load_events("journal_events.json")
    test_harness.register_journal_handler(journal_entry, 'Testy', 'Sol', True)

    yield test_harness

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
        filename:str = str(Path(__file__).parent / "config" / "riches-apurui-M23.csv")
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

        out:str = str(Path(__file__).parent / "nodir" / "nofile.csv")
        res:bool = harness.plugin.router.export_route(out)
        assert res == False

    def test_export_route(self, harness:TestHarness) -> None:
        out:str = str(Path(__file__).parent / "config" / "tmp.csv")
        if os.path.exists(out):
            os.remove(out)

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        
        res:bool = harness.plugin.csv.write(harness.plugin.route.hdrs, harness.plugin.route.route, out)
        assert res == True
        assert os.path.exists(out)
        os.remove(out)


class TestCargo:
    """Test cargo management."""

    def test_cargo_event(self, harness:TestHarness):
        """Test cargo event updates."""
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
        assert harness.plugin.ui.parent.clipboard_get() == ''

class TestShipyardSwap:
    """Test ship swapping from shipyard."""

    def test_swap_existing_ship(self, harness:TestHarness):
        """Test swapping to a previously loaded ship."""
        # Load multiple ships
        harness.play_sequence('shipyard_swap')
        assert harness.plugin.router.ship_id == '106'

    def test_swap_unknown_ship(self, harness:TestHarness):
        """Test swapping to an unknown ship."""
        harness.play_sequence('shipyard_swap_unknown')

        assert harness.plugin.router.ship_id == '106'


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
        # Mock Spansh response for job submission
        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        # Mock route results response
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

        # Track the thread so we can join it
        plotter_thread = None
        original_thread = __import__('threading').Thread

        def capture_thread(*args, **kwargs):
            nonlocal plotter_thread
            thread = original_thread(*args, **kwargs)
            if "route plotting worker" in thread.name:
                plotter_thread = thread
            return thread

        with patch('threading.Thread', side_effect=capture_thread):
            with patch('requests.post', return_value=job_response):
                with patch('requests.get', return_value=result_response):
                    params = {'from': 'Start', 'to': 'End', 'max_time': 1}
                    harness.plugin.router.plot_route('Neutron', params)

                    # Join the plotter thread if captured
                    if plotter_thread:
                        plotter_thread.join(timeout=120)

                    # Route should be created and have at least 2 waypoints
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
        
        with patch('threading.Thread', side_effect=capture_thread):
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

    def test_plot_neutron_route(self, harness:TestHarness) -> None:
        """ Plot a Neutron test route """

        res:bool = harness.plugin.router.plot_route('Neutron',
                                             {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                              'range': '60.00', 'efficiency': '60',
                                              'supercharge_multiplier': '4'})
        assert res == True
        time.sleep(20)
        assert harness.plugin.route is not None
        assert harness.plugin.route.source() == 'Apurui'
        assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.route.total_jumps() == 31

    def test_plot_neutron_route_caspian(self, harness:TestHarness) -> None:
        """ Plot a Neutron test route """

        res:bool = harness.plugin.router.plot_route('Neutron',
                                             {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                              'range': '60.00', 'efficiency': '60',
                                              'supercharge_multiplier': '6'})        
        assert res == True
        # Wait for the plot to finish
        time.sleep(20)

        assert harness.plugin.route is not None        
        assert harness.plugin.route.source() == 'Apurui'
        assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.route.total_jumps() == 21


    def test_plot_galaxy_route(self, harness:TestHarness) -> None:
        """Ensure galaxy plot_route sets params and starts worker."""

        harness.plugin.router.swap_ship(1)

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
            "fuel_power": harness.plugin.router.ship.fuel_power,
            "fuel_multiplier": harness.plugin.router.ship.fuel_multiplier,
            "optimal_mass": harness.plugin.router.ship.optimal_mass,
            "base_mass": harness.plugin.router.ship.base_mass,
            "tank_size": harness.plugin.router.ship.tank_size,
            "internal_tank_size": harness.plugin.router.ship.internal_tank_size,
            "max_fuel_per_jump": harness.plugin.router.ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": harness.plugin.router.ship.loadout,
            "supercharge_multiplier": harness.plugin.router.ship.supercharge_multiplier,
            "injection_multiplier": harness.plugin.router.ship.injection_multiplier,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        assert harness.plugin.router.ship.fuel_power == 2.45
        assert harness.plugin.router.ship.fuel_multiplier == 0.013
        assert harness.plugin.router.ship.optimal_mass == 1894.1
        assert harness.plugin.router.ship.base_mass == 287.6
        assert harness.plugin.router.ship.tank_size == 32
        assert harness.plugin.router.ship.internal_tank_size == 0.5
        assert harness.plugin.router.ship.max_fuel_per_jump == 5.2

        res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
        assert res == True

        # Wait for the plot to complete
        time.sleep(62)

        assert harness.plugin.route is not None
        assert harness.plugin.router.src == 'Apurui'
        assert harness.plugin.router.dest == 'Bleae Thua NI-B b27-5'

        # Galaxy plotter's results vary based on a number of factors.
        assert harness.plugin.route.total_jumps() <= 28
        assert harness.plugin.route.total_jumps() >= 11


    def test_plot_galaxy_route_caspian(self, harness:TestHarness) -> None:
        """Ensure galaxy plot_route sets params and starts worker."""

        harness.plugin.router.swap_ship(115)        

        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "optimistic",
            "fuel_reserve": 12,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 1,
            "refuel_every_scoopable": 0,
            "fuel_power": harness.plugin.router.ship.fuel_power,
            "fuel_multiplier": harness.plugin.router.ship.fuel_multiplier,
            "optimal_mass": harness.plugin.router.ship.optimal_mass,
            "base_mass": harness.plugin.router.ship.base_mass,
            "tank_size": harness.plugin.router.ship.tank_size,
            "internal_tank_size": harness.plugin.router.ship.internal_tank_size,
            "max_fuel_per_jump": harness.plugin.router.ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": harness.plugin.router.ship.loadout,
            "supercharge_multiplier": harness.plugin.router.ship.supercharge_multiplier,
            "injection_multiplier": harness.plugin.router.ship.injection_multiplier,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
        assert res == True
        time.sleep(62)

        logging.debug(f"Route: {harness.plugin.route}")
        assert harness.plugin.route is not None
        assert harness.plugin.router.src == 'Apurui'
        assert harness.plugin.router.dest == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.route.total_jumps() >= 11
        assert harness.plugin.route.total_jumps() <= 17
        #harness.plugin.route.offset = 6
        #assert harness.plugin.route.next_stop() == 'Col 359 Sector ZZ-P d5-52'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
