"""
EDSM system-data enrichment for the currently plotted route: batch-queries EDSM for
StarSystem/SystemAddress/StarPos/StarClass, with an in-memory (session-lifetime) cache backed
by an on-disk (route-lifetime) one. See Router.api.get_navroute(), which serves the result.
"""
import concurrent.futures
import json
import re
from pathlib import Path
from typing import Any

from .utils.debug import Debug
from .utils.misc import singleton
from .constants import DATA_DIR, EDSM_SYSTEMS, EDSM_BATCH_SIZE, EDSM_TIMEOUT
from .context import Context
from .route_manager import SESSION

# EDSM's primaryStar.type is free text
_STAR_CLASS_RE:re.Pattern = re.compile(r"^([A-Za-z]+) \(")
_WHITE_DWARF_RE:re.Pattern = re.compile(r"^White Dwarf \(([A-Za-z0-9]+)\)")
_EXOTIC_STAR_CLASSES:dict[str, str] = {
    "Neutron Star": "N",
    "Black Hole": "H",
    "Supermassive Black Hole": "SupermassiveBlackHole",
}

def _star_class(edsm_type:str) -> str:
    """ Best-effort mapping from EDSM's free-text primaryStar.type to EDMC's short StarClass code. """
    if edsm_type in _EXOTIC_STAR_CLASSES:
        return _EXOTIC_STAR_CLASSES[edsm_type]
    m:re.Match|None = _WHITE_DWARF_RE.match(edsm_type)
    if m: return m.group(1)
    m = _STAR_CLASS_RE.match(edsm_type)
    return m.group(1) if m else edsm_type

@singleton
class EDSMData:
    """ Retrieves and caches EDSM system data for whichever systems are in the currently plotted route. """

    def __init__(self) -> None:
        self.cache:dict[str, dict] = {}
        self.executor:concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="NeutronDancerEDSM")

    def _cache_file(self) -> Path:
        return Path(Context.plugin_dir) / DATA_DIR / 'edsm_cache.json'

    def load(self) -> None:
        file:Path = self._cache_file()
        if not file.exists(): return
        try:
            with open(file) as f:
                self.cache.update(json.load(f))
        except Exception as e:
            Debug.logger.error("Failed to load EDSM cache", exc_info=e)

    def save(self) -> None:
        file:Path = self._cache_file()
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            Debug.logger.error("Failed to save EDSM cache", exc_info=e)

    def clear(self) -> None:
        """ Called when the route is cleared """
        self.cache.clear()
        file:Path = self._cache_file()
        if file.exists():
            file.unlink()

    def get(self, name:str) -> dict|None:
        """ A NavRoute-shaped record for `name`, or None if EDSM hasn't been queried for it (yet). """
        return self.cache.get(name)

    def _fetch(self, names:list[str]) -> None:
        """ batch-query EDSM for any of `names` not already cached. """
        missing:list[str] = [n for n in dict.fromkeys(names) if n and n not in self.cache]
        if not missing: return

        for i in range(0, len(missing), EDSM_BATCH_SIZE):
            chunk:list[str] = missing[i:i + EDSM_BATCH_SIZE]
            try:
                params:list[tuple[str, Any]] = [('systemName[]', name) for name in chunk]
                params += [('showId', 1), ('showCoordinates', 1), ('showPrimaryStar', 1)]
                response = SESSION.get(EDSM_SYSTEMS, params=params,
                                        headers={'User-Agent': Context.plugin_useragent}, timeout=EDSM_TIMEOUT)
                response.raise_for_status()
                for system in response.json():
                    star:dict = system.get('primaryStar') or {}
                    coords:dict|None = system.get('coords')
                    self.cache[system['name']] = {
                        "StarSystem": system['name'],
                        "SystemAddress": system.get('id64'),
                        "StarPos": [coords['x'], coords['y'], coords['z']] if coords else None,
                        "StarClass": _star_class(star['type']) if star.get('type') else '',
                    }
            except Exception as e:
                Debug.logger.error(f"Failed to fetch EDSM data for {chunk}", exc_info=e)

        self.save()

    def start_fetch(self, names:list[str]) -> None:
        """ Bounded, not a raw Thread per call """
        self.executor.submit(self._fetch, names)
