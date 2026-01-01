# Test Harness Quick Start Guide

## What You Got

A complete test harness for the EDMC Neutron Dancer plugin with:
- **test_harness.py** - Core framework for simulating journal events
- **test_plugin.py** - Comprehensive pytest test suite (20+ tests)
- **examples.py** - 7 interactive example scenarios
- **Full documentation** - TEST_HARNESS.md with API reference

## Installation (5 minutes)

```bash
cd /Volumes/EDMarketConnector/plugins/EDMC-NeutronDancer

# Create virtual environment and install dependencies
python3 setup_tests.py

# Activate the environment
source .venv/bin/activate
```

## Run Examples (2 minutes)

```bash
python examples.py
```

See 7 different testing scenarios in action:
1. Basic usage
2. Jump sequences
3. Multiple ships
4. Cargo tracking
5. Route planning
6. Preset scenarios
7. Custom testing

## Run Tests (1 minute)

```bash
pytest test_plugin.py -v
```

Runs 20+ tests covering:
- Startup events
- Ship loadouts
- Jump tracking
- Cargo management
- Multiple ships
- Route state
- Complex scenarios

## Interactive Testing (Anytime)

```python
from test_harness import TestHarness
from load import journal_entry

# Create harness
harness = TestHarness()
harness.register_journal_handler(journal_entry)

# Simulate events
harness.startup("Sol")
harness.loadout(ship_id="1", ship_type="Anaconda")
harness.jump("Sirius", jump_distance=8.6)
harness.jump("Altair", jump_distance=11.2)

# Check state
harness.print_state()

# Get state as dict
state = harness.get_router_state()
print(f"At system: {state['system']}")
print(f"Ship ID: {state['ship_id']}")
```

## Available Events

```python
# Startup
harness.startup("Sol")

# Jump
harness.jump("Sirius", jump_distance=8.6, star_class='A')

# Load ship
harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Explorer")

# Cargo
harness.cargo(100)

# Supercruise exit
harness.supercruise_exit("Sirius", body="A")

# Docking
harness.docking("Habitats", station_type="Starport")

# Location
harness.location("Sirius", station="Habitats")

# Carrier jump
harness.carrier_jump("Sirius", docked=True)

# Ship swap
harness.shipyard_swap("2")
```

## Common Tasks

### Test a single jump
```python
harness = TestHarness()
harness.register_journal_handler(journal_entry)
harness.startup("Sol")
harness.jump("Sirius", jump_distance=8.6)
assert harness.router.system == "Sirius"
```

### Test jump sequence
```python
harness.startup("Sol")
for system, distance in [("Sirius", 8.6), ("Altair", 11.2), ("Vega", 25.3)]:
    harness.jump(system, jump_distance=distance)
assert harness.router.system == "Vega"
```

### Test ship loading
```python
harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Explorer")
assert harness.router.ship is not None
assert harness.router.ship.range > 0
```

### Test multiple ships
```python
harness.loadout(ship_id="1", ship_type="Anaconda")
harness.loadout(ship_id="2", ship_type="AspX")
harness.shipyard_swap("1")
assert harness.router.ship.type == "Anaconda"
```

### Test cargo
```python
harness.cargo(100)
assert harness.router.cargo == 100
```

## Advanced Usage

### Run specific tests
```bash
pytest test_plugin.py::TestJumps::test_jump_sequence -v
```

### Run with coverage
```bash
pytest test_plugin.py --cov=Router --cov-report=html
```

### Show output
```bash
pytest test_plugin.py -v -s
```

### Stop on first failure
```bash
pytest test_plugin.py -x
```

## File Structure

```
EDMC-NeutronDancer/
├── test_harness.py          # Core test framework
├── test_plugin.py           # Pytest test suite
├── examples.py              # Example scenarios
├── setup_tests.py           # Setup script
├── verify_harness.py        # Verification script
├── README_TESTS.md          # This file
├── TEST_HARNESS.md          # Detailed documentation
└── .venv/                   # Virtual environment (created by setup)
```

## Troubleshooting

### ImportError: No module named 'semantic_version'
```bash
# Make sure you activated the virtual environment
source .venv/bin/activate
```

### ModuleNotFoundError: No module named 'pytest'
```bash
pip install pytest pytest-cov
```

### Command not found: pytest
```bash
# Activate the virtual environment first
source .venv/bin/activate
pytest test_plugin.py -v
```

### "externally-managed-environment" error
The setup script handles this automatically. Just run:
```bash
python3 setup_tests.py
```

## Next Steps

1. **Read the docs** - See TEST_HARNESS.md for detailed API
2. **Run examples** - See practical scenarios in examples.py
3. **Write tests** - Use test_plugin.py as a template
4. **Extend harness** - Add custom events as needed

## Tips

- Tests are isolated - each test gets a fresh harness
- No real network calls or disk I/O
- Tests run in milliseconds
- Virtual environment keeps dependencies contained
- All code is type-hinted for IDE support

## Quick Reference

| Action | Command |
|--------|---------|
| Setup | `python3 setup_tests.py` |
| Activate | `source .venv/bin/activate` |
| Run examples | `python examples.py` |
| Run tests | `pytest test_plugin.py -v` |
| Check syntax | `python3 verify_harness.py` |

## Need Help?

- **API details** → See TEST_HARNESS.md
- **Examples** → See examples.py
- **Test patterns** → See test_plugin.py
- **Setup issues** → Run verify_harness.py

## Good to Know

✅ The harness mocks EDMC's config module automatically
✅ Tests don't require EDMC to be installed
✅ Router is a singleton - use fresh harness per test
✅ All events include timestamps automatically
✅ State is easily inspectable for assertions

Happy testing! 🚀
