# Neutron Dancer Test Harness

A comprehensive testing framework for the EDMC Neutron Dancer plugin that allows you to simulate journal events and test plugin behavior without running the full EDMC application.

## Quick Start

### 1. Initial Setup

```bash
python3 setup_tests.py
source .venv/bin/activate
```

This creates a virtual environment and installs all dependencies.

### 2. Run the Examples

```bash
python examples.py
```

This runs 7 example scenarios demonstrating the test harness capabilities.

### 3. Run the Test Suite

```bash
pytest test_plugin.py -v
```

This runs the full pytest test suite with 20+ tests covering various plugin functionality.

### 4. Interactive Testing

```python
from test_harness import TestHarness
from load import journal_entry

harness = TestHarness()
harness.register_journal_handler(journal_entry)

# Fire events
harness.startup("Sol")
harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Explorer")
harness.jump("Sirius", jump_distance=8.6)

# Check results
harness.print_state()
```

## Files Included

| File | Purpose |
|------|---------|
| `test_harness.py` | Core testing framework with event simulation |
| `test_plugin.py` | Pytest test suite with comprehensive tests |
| `examples.py` | 7 interactive example scenarios |
| `setup_tests.py` | Setup script to create virtual environment |
| `TEST_HARNESS.md` | Detailed documentation and API reference |
| `README_TESTS.md` | This file |

## Available Events

The harness can simulate these EDMC journal events:

- **Startup** - Plugin initialization with system location
- **FSDJump** - Faster-than-light jump between systems
- **Loadout** - Ship loadout/switching event
- **Cargo** - Cargo inventory change
- **SupercruiseExit** - Exit from supercruise near body
- **Docking** - Dock at station
- **Location** - Transit to new location
- **CarrierJump** - Fleet carrier jump
- **ShipyardSwap** - Switch to different ship in shipyard

## Example Scenarios

### Basic Setup
```python
harness.startup("Sol")
harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Explorer")
```

### Jump Sequence
```python
harness.jump("Sirius", jump_distance=8.6)
harness.jump("Altair", jump_distance=11.2)
harness.jump("Vega", jump_distance=25.3)
```

### Multi-Ship Testing
```python
harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Explorer")
harness.loadout(ship_id="2", ship_type="AspX", ship_name="Trader")
harness.shipyard_swap("1")  # Switch back to Anaconda
```

### Cargo Tracking
```python
harness.jump("Sirius", jump_distance=8.6)
harness.cargo(100)  # Pick up cargo
harness.jump("Altair", jump_distance=11.2)
harness.cargo(75)   # Deliver some
```

## Testing Patterns

### Pattern 1: Single Event Test
```python
def test_jump():
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    harness.jump("Sirius", jump_distance=8.6)
    assert harness.router.system == "Sirius"
```

### Pattern 2: Sequence Test
```python
def test_route_sequence():
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    harness.startup("Sol")
    harness.loadout(ship_id="1", ship_type="Anaconda")
    harness.jump("Sirius", jump_distance=8.6)
    harness.jump("Altair", jump_distance=11.2)
    
    assert harness.router.system == "Altair"
```

### Pattern 3: State Validation
```python
def test_state():
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    harness.startup("Sol")
    harness.loadout(ship_id="1", ship_type="Anaconda")
    
    state = harness.get_router_state()
    assert state['system'] == "Sol"
    assert state['ship_id'] == "1"
```

## Running Tests

```bash
# All tests
pytest test_plugin.py -v

# Specific test class
pytest test_plugin.py::TestJumps -v

# Specific test
pytest test_plugin.py::TestJumps::test_single_jump -v

# With coverage report
pytest test_plugin.py --cov=Router --cov-report=html

# Exit on first failure
pytest test_plugin.py -x

# Show print statements
pytest test_plugin.py -v -s
```

## Test Coverage

The test suite covers:

- ✅ Plugin startup behavior
- ✅ Ship loadout and swapping
- ✅ Jump tracking and sequences
- ✅ Cargo management
- ✅ Multiple ships in shipyard
- ✅ Route state management
- ✅ Supercruise exits
- ✅ Station docking
- ✅ Fleet carrier jumps
- ✅ Complex multi-step scenarios
- ✅ Edge cases and error handling
- ✅ Router singleton pattern

## Accessing Plugin State

```python
# Get state as dict
state = harness.get_router_state()

# Pretty-print state
harness.print_state()

# Access individual properties
system = harness.router.system
ship = harness.router.ship
cargo = harness.router.cargo
ship_range = harness.router.ship.range if harness.router.ship else 0
```

## Extending the Harness

### Add Custom Event
```python
def my_custom_event(self):
    self.fire_event({
        'event': 'MyEvent',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'data': 'value',
    })
```

### Add Validation Helper
```python
def assert_at_system(self, expected: str):
    assert self.router.system == expected, \
        f"Expected {expected}, got {self.router.system}"
```

### Register Multiple Handlers
```python
harness.register_journal_handler(journal_entry)
harness.register_journal_handler(my_custom_handler)
harness.register_journal_handler(another_handler)
```

## Troubleshooting

### Virtual Environment Issues
```bash
# Remove old venv and recreate
rm -rf .venv
python3 setup_tests.py
```

### Import Errors
Ensure you've activated the virtual environment:
```bash
source .venv/bin/activate
```

### Pytest Not Found
Install test dependencies:
```bash
pip install pytest pytest-cov
```

### Config Module Errors
The test harness automatically mocks the EDMC config module. If you get import errors, check that `test_harness.py` is being imported before Router modules.

## Performance Tips

- Tests run fast (~1-2ms each) since they don't require EDMC
- No disk I/O or network calls (unless mocked)
- Tests are isolated and can run in parallel
- Use `pytest -n auto` for parallel execution with pytest-xdist

## Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    python3 setup_tests.py
    source .venv/bin/activate
    pytest test_plugin.py -v --cov=Router
```

## Documentation

For detailed API documentation and advanced usage, see [TEST_HARNESS.md](TEST_HARNESS.md).

## Features

✨ **No EDMC Required** - Test without running the full application
🚀 **Fast Tests** - Tests run in milliseconds  
🎯 **Event Simulation** - Simulate any journal event
📊 **State Inspection** - Easily check plugin state
🔧 **Extensible** - Add custom events and validators
📚 **Well Documented** - Comprehensive docs and examples
🧪 **Pytest Integration** - Full pytest support
🎓 **Learning Tool** - 7 example scenarios included

## Support

For issues or questions:
1. Check [TEST_HARNESS.md](TEST_HARNESS.md) documentation
2. Review example scenarios in [examples.py](examples.py)
3. Check test patterns in [test_plugin.py](test_plugin.py)
4. See plugin repo: https://github.com/dwomble/EDMC-NeutronDancer

## License

This test harness is part of the Neutron Dancer plugin and follows the same license.
