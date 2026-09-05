import concurrent.futures
import json
import re
from pathlib import Path

from .utils.debug import Debug
from .utils.misc import singleton
from .constants import DATA_DIR, SPANSH_SYSTEM, SPANSH_TIMEOUT
from .context import Context
from .route_manager import SESSION

# Spansh's body subtype for a main star is EDSM-style free text
_STAR_CLASS_RE:re.Pattern = re.compile(r"^([A-Za-z]+) \(")
_WHITE_DWARF_RE:re.Pattern = re.compile(r"^White Dwarf \(([A-Za-z0-9]+)\)")
_EXOTIC_STAR_CLASSES:dict[str, str] = {
    "Neutron Star": "N",
    "Black Hole": "H",
    "Supermassive Black Hole": "SupermassiveBlackHole",
}

def _star_class(subtype:str) -> str:
    """ Best-effort mapping from Spansh's free-text star subtype to EDMC's short StarClass code. """
    if subtype in _EXOTIC_STAR_CLASSES:
        return _EXOTIC_STAR_CLASSES[subtype]
    m:re.Match|None = _WHITE_DWARF_RE.match(subtype)
    if m: return m.group(1)
    m = _STAR_CLASS_RE.match(subtype)
    return m.group(1) if m else subtype

@singleton
class SpanshData:
    """ Retrieves and caches the primary StarClass for whichever systems are in the currently plotted route. """
    # Not currently wired into route enrichment -- a cheaper route-flag-based guess is used instead.

    def __init__(self) -> None:
        self.cache:dict[str, str] = {}
        self.executor:concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="NeutronDancerSpansh")

    def _cache_file(self) -> Path:
        return Path(Context.plugin_dir) / DATA_DIR / 'spansh_star_cache.json'

    def load(self) -> None:
        file:Path = self._cache_file()
        if not file.exists(): return
        try:
            with open(file) as f:
                self.cache.update(json.load(f))
        except Exception as e:
            Debug.logger.error("Failed to load Spansh star cache", exc_info=e)

    def save(self) -> None:
        file:Path = self._cache_file()
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            Debug.logger.error("Failed to save Spansh star cache", exc_info=e)

    def clear(self) -> None:
        """ Called when the route is cleared """
        self.cache.clear()
        file:Path = self._cache_file()
        if file.exists():
            file.unlink()

    def get(self, name:str) -> str|None:
        """ The cached StarClass for `name`, or None if Spansh hasn't been queried for it (yet). """
        return self.cache.get(name)

    def _fetch(self, ids:dict[str, int]) -> None:
        """ Query Spansh for the primary star of any of `ids` not already cached. """
        missing:dict[str, int] = {n: i for n, i in ids.items() if n and i is not None and n not in self.cache}
        if not missing: return

        for name, id64 in missing.items():
            try:
                response = SESSION.get(f"{SPANSH_SYSTEM}/{id64}",
                                        headers={'User-Agent': Context.plugin_useragent}, timeout=SPANSH_TIMEOUT)
                response.raise_for_status()
                bodies:list = response.json().get('record', {}).get('bodies', [])
                star:dict|None = next((b for b in bodies if b.get('is_main_star')), None)
                self.cache[name] = _star_class(star['subtype']) if star and star.get('subtype') else ''
            except Exception as e:
                Debug.logger.error(f"Failed to fetch Spansh star data for {name}", exc_info=e)

        self.save()

    def start_fetch(self, ids:dict[str, int]) -> None:
        """ Bounded, not a raw Thread per call """
        self.executor.submit(self._fetch, ids)
