"""
Pytest configuration for Neutron Dancer test harness.
"""

import sys
from pathlib import Path

# Add plugin directory to path for all tests
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

# Add tests directory to path
tests_dir = Path(__file__).parent
sys.path.insert(0, str(tests_dir))

# Mock EDMC's config module with shutting_down attribute for tests
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

# Minimal EDMC `theme` module emulator so `from theme import theme` works in tests
import types
from types import SimpleNamespace
theme_mod = types.ModuleType("theme")
# Provide a simple `theme` object; plugins expect `from theme import theme`
theme_mod.theme = SimpleNamespace()
# Optional defaults commonly used by plugins (can be extended as needed)
theme_mod.theme.name = "default"
theme_mod.theme.dark = False
sys.modules['theme'] = theme_mod

# Provide a minimal Debug.logger so utils.debug.Debug.logger calls won't fail in tests
import logging
try:
	from utils.debug import Debug

	logger = logging.getLogger('EDMC.TestHarness')
	if not logger.handlers:
		handler = logging.StreamHandler()
		handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
		logger.addHandler(handler)
	logger.setLevel(logging.DEBUG)

	# Assign the logger on the Debug class so modules using Debug.logger work
	Debug.logger = logger
except Exception:
	# Best-effort: if utils.debug isn't importable yet, ignore — tests that need it will set it.
	pass

# Minimal UI stub to satisfy calls from Router during tests
try:
	from Router.context import Context

	class _StubUI:
		def __init__(self):
			self.frame = None

		def switch_ship(self, ship):
			return None

		def update_waypoint(self):
			return None

		def ctc(self, arg=None):
			return None

		def show_frame(self, which=None):
			return None

		def show_error(self, msg=None):
			return None

		def _show_busy_gui(self, busy:bool):
			return None

	Context.ui = _StubUI()
except Exception:
	pass

# Provide minimal module data so Ship range calculations succeed during tests
try:
	from Router.context import Context as _Context
	# Minimal FSD and fuel tank entries matching TestHarness default module symbols
	_Context.modules = [
		{
			'symbol': 'int_hyperdrive_size8_class5',
			'fuelpower': 2.505,
			'fuelmul': 0.011,
			'maxfuel': 6.8,
			'optmass': 4670,
		},
		{
			'symbol': 'int_fueltank_size8_class3',
			'fuel': 32.0,
		}
	]
except Exception:
	pass

# Suppress logging errors from test teardown (closed file handles in threads)
def pytest_configure(config):
	"""Suppress logging errors that occur during pytest cleanup."""
	logging.raiseExceptions = False
