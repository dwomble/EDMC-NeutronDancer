"""
Test suite for EDMC Neutron Dancer plugin using pytest.

Run with: .venv/bin/python -m pytest tests/test_plugin.py -v --tb=short 2>&1 | tail -30
Run with: .venv_win\Scripts\python.exe -m pytest tests\test_plugin.py -v --tb=short
"""

import pytest # type: ignore
import sys
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import Mock, patch, MagicMock
import json
import time

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

# Config is already mocked by conftest.py
from test_harness import TestHarness
from load import journal_entry
from Router.context import Context


@pytest.fixture
def harness() -> Generator:
    """Provide a fresh test harness for each test."""
    test_harness = TestHarness()
    test_harness.register_journal_handler(journal_entry)
    yield test_harness
    # Cleanup if needed
    #Context.router = None


class TestStartup:
    """Test plugin startup behavior."""

    def test_harness_initialization(self) -> None:
        """Test basic harness initialization."""
        harness = TestHarness()
        assert harness.commander == "TestCommander"
        assert harness.system == "Sol"
        assert harness.router is not None

    def test_startup_event(self, harness:TestHarness) -> None:
        """Test that startup event sets system correctly."""

        assert harness.router is not None

        for event in harness.events.get('startup', []):
            harness.fire_event(event)

        assert harness.router.system == "Sol"


class TestShipLoadout:
    """Test ship loadout and switching."""

    def test_loadout_event(self, harness:TestHarness) -> None:
        """Test loading a ship."""

        for event in harness.events.get('loadout', []):
            harness.fire_event(event)

        shipid:str = str(event.get('ShipID', '1'))
        assert harness.router.ship_id == shipid
        assert harness.router.ship is not None
        assert harness.router.ship.type == event.get('Ship', 'Anaconda')
        assert harness.router.ship.name == event.get('ShipName', 'Test Ship')
        assert harness.router.neutron_params['supercharge_multiplier'] == harness.router.ship.supercharge_multiplier
        assert harness.router.neutron_params['range'] == harness.router.ship.range
        assert harness.router.ships[shipid] is harness.router.ship


    def test_ship_range_calculation(self, harness: TestHarness) -> None:
        """Test that ship range is calculated."""
        assert harness.router.ship is not None
        assert hasattr(harness.router.ship, 'range')
        assert harness.router.ship.range > 0


class TestJumps:
    """Test jump tracking and route management."""

    def test_jump_sequence(self, harness:TestHarness):
        """ Test a sequence of FSD jumps. """
        harness.system = 'Kuk'
        for event in harness.events.get('jump_sequence', []):
            harness.fire_event(event)
            assert harness.router.system == event.get("StarSystem", event.get("System", ''))

class TestPlotting:
    """Test plotting functionality (neutron/galaxy routes)."""

    def test_plot_route_starts_thread(self, harness: TestHarness, monkeypatch) -> None:
        """Ensure plot_route returns True and starts the plotting worker."""
        called:dict[str, bool] = {'flag': False}

        def fake_plotter(self, url, params) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.router), '_plotter', fake_plotter, raising=False)

        params:dict = {'from': 'A', 'to': 'B', 'max_time': 1}
        result:bool = harness.router.plot_route('Neutron', params)
        assert result is True
        # The thread may run quickly; wait briefly for it to start
        import time
        time.sleep(0.05)
        assert called['flag'] is True

    def test_plot_route_unknown_type(self, harness: TestHarness):
        """Unknown plot types should return False and not start plotting."""
        result:bool = harness.router.plot_route('UnsupportedType', {})
        assert result is False

    def test_plot_neutron_route(self, harness:TestHarness) -> None:
        """ Plot a Neutron test route """

        res:bool = harness.router.plot_route('Neutron',
                                             {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                              'range': '60.00', 'efficiency': '60', 'supercharge_multiplier': '4'})
        assert res == True
        time.sleep(20)
        assert harness.context.route is not None
        assert harness.context.route.source() == 'Apurui'
        assert harness.context.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.context.route.total_jumps() == 31

    def test_plot_neutron_route_caspian(self, harness:TestHarness) -> None:
        """ Plot a Neutron test route """

        res:bool = harness.router.plot_route('Neutron',
                                             {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                              'range': '60.00', 'efficiency': '60', 'supercharge_multiplier': '6'})
        assert res == True
        time.sleep(20)
        assert harness.context.route is not None
        assert harness.context.route.source() == 'Apurui'
        assert harness.context.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.context.route.total_jumps() == 21


    def test_plot_galaxy_route(self, harness: TestHarness) -> None:
        """Ensure galaxy plot_route sets params and starts worker."""
        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "Optimistic",
            "fuel_reserve": 12,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 1,
            "refuel_every_scoopable": 1,
            "fuel_power": 2.45,
            "fuel_multiplier": 0.013,
            "optimal_mass": 1894.1,
            "base_mass": 286.3,
            "tank_size": 32,
            "internal_tank_size": 0.5,
            "max_fuel_per_jump": 5.2,
            "range_boost": 10.5,
            "ship_build": harness.loadouts.get('Shipping Delay', {}),
            "supercharge_multiplier": 4,
            "injection_multiplier": 2,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        res:bool = harness.router.plot_route('Galaxy', galaxy_params)
        assert res == True
        time.sleep(62)

        assert harness.router.src == 'Apurui'
        assert harness.router.dest == 'Bleae Thua NI-B b27-5'
        assert harness.context.route.total_jumps() == 18


    def test_plot_galaxy_route_caspian(self, harness: TestHarness) -> None:
        """Ensure galaxy plot_route sets params and starts worker."""
        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "Optimistic",
            "fuel_reserve": 12,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 1,
            "refuel_every_scoopable": 1,
            "fuel_power": 2.505,
            "fuel_multiplier": 0.011,
            "optimal_mass": 7528.04,
            "base_mass": 1366.44,
            "tank_size": 128,
            "internal_tank_size": 1.14,
            "max_fuel_per_jump": 6.8,
            "range_boost": 10.5,
            "ship_build": harness.loadouts.get('Perviy', {}),
            "supercharge_multiplier": 6,
            "injection_multiplier": 2,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        res:bool = harness.router.plot_route('Galaxy', galaxy_params)
        assert res == True
        time.sleep(62)

        assert harness.router.src == 'Apurui'
        assert harness.router.dest == 'Bleae Thua NI-B b27-5'
        assert harness.context.route.total_jumps() == 12


    def test_import_route(self, harness: TestHarness) -> None:
        return

    def test_plotter_success_creates_route(self, harness: TestHarness) -> None:
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
                    harness.router.plot_route('Neutron', params)

                    # Join the plotter thread if captured
                    if plotter_thread:
                        plotter_thread.join(timeout=120)

                    # Route should be created and have at least 2 waypoints
                    assert Context.route is not None
                    assert len(Context.route.route) >= 2

    def test_plotter_error_response_shows_error(self, harness: TestHarness):
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
                harness.router.plot_route('Neutron', params)

                # Join the plotter thread if captured
                if plotter_thread:
                    plotter_thread.join(timeout=120)

                # No exception should be raised; Context.ui.show_error would be called


class TestCargo:
    """Test cargo management."""

    def test_cargo_event(self, harness: TestHarness):
        """Test cargo event updates."""
        for event in harness.events.get('add_cargo', []):
            harness.fire_event(event)

        assert harness.router.cargo == 200

        for event in harness.events.get('remove_cargo', []):
            harness.fire_event(event)

        assert harness.router.cargo == 0

class TestComplexScenarios:
    """Test complex multi-step scenarios."""

    def test_full_route_scenario(self, harness: TestHarness):
        """Test a complete route scenario with jumps and cargo."""
        # Setup
        #harness.startup("Sol")
        #harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Route Runner", use_real_loadout=False)
        #harness.cargo(0)

        # Simulate route
        #route_systems = ["Sol", "Sirius", "Procyon", "Altair"]
        #distances = [8.6, 11.4, 10.4]

        #for i, system in enumerate(route_systems[1:], 1):
        #    harness.jump(system, jump_distance=distances[i-1])
        #    assert harness.router.system == system

        # Final state check
        #state = harness.get_router_state()
        #assert state['system'] == "Altair"
        #assert state['cargo'] == 0

        # Simulate route
        #route_systems = ["Sol", "Sirius", "Procyon", "Altair"]
        #distances = [8.6, 11.4, 10.4]

        #for i, system in enumerate(route_systems[1:], 1):
        #    harness.jump(system, jump_distance=distances[i-1])
        #    assert harness.router.system == system

        # Final state check
        #state = harness.get_router_state()
        #assert state['system'] == "Altair"
        #assert state['cargo'] == 0

    def test_carrier_jump_noroute(self, harness: TestHarness) -> None:
        """Test carrier jump with docking."""
        # { "timestamp":"2026-01-24T07:06:27Z", "event":"CarrierLocation", "CarrierType":"FleetCarrier", "CarrierID":3709409280, "StarSystem":"Kuk", "SystemAddress":24859942069665, "BodyID":12 }
        #harness.startup("Sol")
        #harness.carrier_location_event("Sirius", station="My Fleet Carrier", docked=True)

        #assert harness.router.system == "Sol"

    def test_carrier_jump_route(self, harness: TestHarness):
        """Test carrier jump with docking."""
        #harness.startup("Sol")
        #harness.router.carrier_id = "FC-12345"
        #harness.router.carrier_state = "Jumping"
        #harness.carrier_location_event("Sirius", station="My Fleet Carrier", docked=True)

        #assert harness.router.system == "Sol"

    def test_supercruise_exit(self, harness: TestHarness):
        """Test supercruise exit event."""
        #harness.startup("Sol")
        #harness.supercruise_exit("Sirius", body="A", position=[0, 0, 0])

        # System should be updated
        #assert harness.router.system == "Sirius"

    def test_location_event(self, harness: TestHarness):
        """Test location event."""



class TestShipyardSwap:
    """Test ship swapping from shipyard."""

    def test_swap_existing_ship(self, harness: TestHarness):
        """Test swapping to a previously loaded ship."""
        # Load multiple ships
        for event in harness.events.get('shipyard_swap', []):
            harness.fire_event(event)

        assert harness.router.ship_id == str(event.get('ShipID'))

    def test_swap_unknown_ship(self, harness: TestHarness):
        """Test swapping to an unknown ship."""
        for event in harness.events.get('shipyard_swap_unknown', []):
            harness.fire_event(event)

        assert harness.router.ship_id == str(event.get('ShipID'))

class TestStateManagement:
    """Test router state management."""

    def test_router_singleton(self, harness: TestHarness) -> None:
        """Test that Router is a singleton."""

        # Create another harness - should share same router instance
        harness2 = TestHarness()
        assert harness.router is harness2.router

    def test_save_load_parameters(self, harness: TestHarness) -> None:
        """Test that route parameters are saved."""
        for event in harness.events.get('startup', []):
            harness.fire_event(event)

        # Should do a save and verify the json result



if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

