"""Download and install the local routing indexes published on the repository's star-data releases."""
import requests
import hashlib, json, shutil, time, zipfile
from pathlib import Path
from threading import Lock, Thread
from typing import Callable

from config import config # type: ignore

from ..constants import GH_USER, GH_PROJECT, LOCAL_TAG, DATA_DIR,lbls
from ..context import Context
from ..utils.debug import Debug, catch_exceptions
from .index import VERSION

# Each index format has its own release, so older plugin versions keep data they can read
URL:str = f"https://github.com/{GH_USER}/{GH_PROJECT}/releases/download/{LOCAL_TAG}-v{VERSION}"

class LocalData:
    """The index folders under the plugin's data folder, kept in step with the release's manifest."""

    def __init__(self, folder:Path, backup:Path) -> None:
        self.folder:Path = folder
        self.backup:Path = backup
        self.lock:Lock = Lock()

    def installed(self) -> dict:
        """Manifest entries for the indexes on disk, as of their download."""
        path:Path = self.folder / 'star-data.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def ready(self) -> bool:
        """ Whether the local router is enabled and both of its indexes are on disk in the format this version reads """
        metas:list = [Path(Context.plugin_dir) / DATA_DIR / k / 'meta.json' for k in ('neutron', 'kgbfoam')]
        return bool(config.get_bool(f"{Context.plugin_name}_local_router")) and \
            all(m.exists() and json.loads(m.read_text()).get('version') == VERSION for m in metas)

    def update(self, status:Callable[[str], None]) -> bool:
        """Bring the indexes in line with the release's manifest; True if anything changed."""
        if self.lock.locked(): return False

        with self.lock:
            Debug.logger.info(f"Checking star data at {URL}")
            resp:requests.Response = Context.session.get(f"{URL}/manifest.json", headers={'User-Agent': Context.plugin_useragent}, timeout=30)
            resp.raise_for_status()
            files:dict = resp.json()['files']
            have:dict = self.installed()
            stale:list = [k for k, e in files.items()
                          if have.get(k, {}).get('sha256') != e['sha256'] or not (self.folder / k / 'meta.json').exists()]
            gone:list = [k for k in have if k not in files]

            # Record each index as it lands so an interrupted run resumes from there
            for kind in stale:
                self._fetch(kind, files[kind], status)
                have[kind] = files[kind]
                (self.folder / 'star-data.json').write_text(json.dumps(have, indent=2))

            # An add-on is dropped from the manifest once a full rebuild absorbs it
            for kind in gone:
                Debug.logger.info(f"Removing retired star data {kind}")
                shutil.rmtree(self.folder / kind, ignore_errors=True)
                del have[kind]
            if gone: (self.folder / 'star-data.json').write_text(json.dumps(have, indent=2))

            if not stale and not gone: Debug.logger.info("Star data is up to date")
            return bool(stale or gone)

    def delete(self) -> None:
        """Remove every downloaded index and its backup."""
        for kind in self.installed(): shutil.rmtree(self.folder / kind, ignore_errors=True)
        (self.folder / 'star-data.json').unlink(missing_ok=True)
        shutil.rmtree(self.backup, ignore_errors=True)

    def size(self) -> int:
        """Bytes the downloaded indexes and their backup take on disk."""
        dirs:list = [self.folder / k for k in self.installed()] + [self.backup]
        return sum(f.stat().st_size for d in dirs for f in d.rglob('*') if f.is_file())

    def _fetch(self, kind:str, entry:dict, status:Callable[[str], None]) -> None:
        """Download one packaged index, check its hash and swap it in, keeping the previous copy as the backup."""
        Debug.logger.info(f"Downloading star data {entry['asset']}, {entry['size'] / 2 ** 20:.0f} MiB")
        start:float = time.monotonic()
        part:Path = self.folder / f"{kind}.zip.part"
        sha = hashlib.sha256()
        got:int = 0
        shown:int = -1
        self.folder.mkdir(parents=True, exist_ok=True)

        with Context.session.get(f"{URL}/{entry['asset']}", headers={'User-Agent': Context.plugin_useragent}, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(part, 'wb') as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    sha.update(chunk)
                    got += len(chunk)
                    if (pct := got * 100 // max(entry['size'], 1)) != shown: status(f"{kind} {pct}%")
                    shown = pct

        if sha.hexdigest() != entry['sha256'] or got != entry['size']:
            part.unlink(missing_ok=True)
            raise ValueError(f"{entry['asset']} failed its checksum")

        # zipfile strips absolute paths and '..' from entry names and never creates links, so nothing lands outside new
        new:Path = self.folder / f"{kind}.new"
        shutil.rmtree(new, ignore_errors=True)
        with zipfile.ZipFile(part) as z: z.extractall(new)
        part.unlink()

        old:Path = self.backup / kind
        shutil.rmtree(old, ignore_errors=True)
        self.backup.mkdir(parents=True, exist_ok=True)
        if (self.folder / kind).exists(): (self.folder / kind).rename(old)
        new.rename(self.folder / kind)
        Debug.logger.info(f"Installed star data {kind} in {time.monotonic() - start:.0f}s")

    @catch_exceptions
    def check_local_data(self) -> None:
        """ Download or update the local router's data if it's enabled """
        if not config.get_bool(f"{Context.plugin_name}_local_router"): return
        Thread(target=self._sync_local, daemon=True, name="Neutron Dancer star data").start()


    def _sync_local(self) -> None:
        """ Sync the star data, then reload the indexes on the next plot and offer the Local route type if it changed """
        try:
            changed:bool = self.update(Context.ui.local_status)
        except Exception as e:
            Debug.logger.error("Star data update failed, exception info:", exc_info=e)
            Context.ui.local_status(None)
            Context.ui.show_error(lbls['local_failed'])
            return

        Context.ui.local_status(None)
        if not changed: return
        Context.router.local = None
        Context.ui.refresh_route_types()
