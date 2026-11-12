"""Download and install the local routing indexes published on the repository's star-data releases."""
import hashlib, json, shutil, zipfile
from pathlib import Path
from threading import Thread
from typing import Callable

import requests

from ..constants import GH_USER, GH_PROJECT, LOCAL_TAG
from ..utils.debug import Debug
from .index import VERSION

# Each index format has its own release, so older plugin versions keep data they can read
URL:str = f"https://github.com/{GH_USER}/{GH_PROJECT}/releases/download/{LOCAL_TAG}-v{VERSION}"

class LocalData:
    """The index folders under the plugin's data folder, kept in step with the release's manifest."""

    def __init__(self, folder:Path, session:requests.Session, agent:str) -> None:
        self.folder:Path = folder
        self.session:requests.Session = session
        self.agent:str = agent
        self.busy:bool = False

    def installed(self) -> dict:
        """Manifest entries for the indexes on disk, as of their download."""
        path:Path = self.folder / 'local.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def update(self, status:Callable[[str|None], None], done:Callable[[bool|None], None]) -> None:
        """Bring the indexes up to date in the background; done gets whether anything changed, or None on failure."""
        if self.busy: return
        self.busy = True
        Thread(target=self._update, args=(status, done), daemon=True, name="Neutron Dancer local data").start()

    def delete(self) -> None:
        """Remove every downloaded index."""
        for kind in self.installed(): shutil.rmtree(self.folder / kind, ignore_errors=True)
        (self.folder / 'local.json').unlink(missing_ok=True)

    def size(self) -> int:
        """Bytes the downloaded indexes take on disk."""
        return sum(f.stat().st_size for k in self.installed() for f in (self.folder / k).glob('*') if f.is_file())

    def _update(self, status:Callable[[str|None], None], done:Callable[[bool|None], None]) -> None:
        changed:bool = False
        try:
            resp:requests.Response = self.session.get(f"{URL}/manifest.json", headers={'User-Agent': self.agent}, timeout=30)
            resp.raise_for_status()
            files:dict = resp.json()['files']
            have:dict = self.installed()

            # Fetch whatever is new or changed, recording each as it lands so an interrupted run resumes from there
            for kind, entry in files.items():
                if have.get(kind, {}).get('sha256') == entry['sha256'] and (self.folder / kind / 'meta.json').exists(): continue
                self._fetch(kind, entry, status)
                have[kind] = entry
                (self.folder / 'local.json').write_text(json.dumps(have, indent=2))
                changed = True

            # An add-on is dropped from the manifest once a full rebuild absorbs it
            for kind in [k for k in have if k not in files]:
                shutil.rmtree(self.folder / kind, ignore_errors=True)
                del have[kind]
                (self.folder / 'local.json').write_text(json.dumps(have, indent=2))
                changed = True

            status(None)
            done(changed)
        except Exception as e:
            Debug.logger.error("Local route data update failed, exception info:", exc_info=e)
            status(None)
            done(None)
        finally:
            self.busy = False

    def _fetch(self, kind:str, entry:dict, status:Callable[[str|None], None]) -> None:
        """Download one packaged index, check its hash, unpack it beside the old one and swap it in."""
        part:Path = self.folder / f"{kind}.zip.part"
        sha = hashlib.sha256()
        got:int = 0
        shown:int = -1
        self.folder.mkdir(parents=True, exist_ok=True)

        with self.session.get(f"{URL}/{entry['asset']}", headers={'User-Agent': self.agent}, stream=True, timeout=60) as r:
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
        old:Path = self.folder / f"{kind}.old"
        shutil.rmtree(new, ignore_errors=True)
        with zipfile.ZipFile(part) as z: z.extractall(new)
        part.unlink()

        shutil.rmtree(old, ignore_errors=True)
        if (self.folder / kind).exists(): (self.folder / kind).rename(old)
        new.rename(self.folder / kind)
        shutil.rmtree(old, ignore_errors=True)
