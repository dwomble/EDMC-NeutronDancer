import json
import os
import requests
import zipfile
import webbrowser
from semantic_version import Version # type: ignore

from .constants import GIT_PROJECT, GIT_DOWNLOAD, GIT_CHANGELOG_LIST, GIT_CHANGELOG, GIT_VERSION
from utils.Debug import Debug, catch_exceptions
from .context import Context

class Updater():
    """
    Handle checking for and installing updates
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, version:Version|None = None, plugin_dir:str='') -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        if version != None: self.version:Version = version
        if plugin_dir != '': self.plugin_dir:str = plugin_dir

        self.update_available:bool = False
        self.install_update:bool = False
        self.update_version:Version

        self.download_url:str = ""
        self.zip_downloaded:str = ""

        # Make sure we're actually initialized
        if self.version != None and self.plugin_dir != '':
            self._initialized = True

    def download_zip(self) -> bool:
        """ Download the zipfile of the latest version """
        try:
            r:requests.Response = requests.get(self.download_url)
            Debug.logger.debug(f"{r}")
            r.raise_for_status()
        except Exception:
            Debug.logger.error(f"Failed to download {GIT_PROJECT} update (status code {r.status_code}).)")
            return False

        zip_path:str = os.path.join(self.plugin_dir, "updates")
        os.makedirs(zip_path, exist_ok=True)
        zip_file:str = os.path.join(zip_path, f"{GIT_PROJECT}-{self.update_version}.zip")
        with open(zip_file, 'wb') as f:
            Debug.logger.info(f"Downloading {GIT_PROJECT} to " + zip_file)
            #f.write(os.path.join(r.content))
            for chunk in r.iter_content(chunk_size=32768):
                f.write(chunk)
        self.zip_downloaded = zip_file
        return True

    def install(self) -> None:
        if not self.get_changelogs():
            return

        if not self.download_zip():
            return
        try:
            Debug.logger.debug(f"Extracting zipfile to {self.plugin_dir}")
            with zipfile.ZipFile(self.zip_downloaded, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
            #os.remove(self.zip_path)
        except Exception as e:
            Debug.logger.error("Failed to install update, exception info:", exc_info=e)

    def get_changelogs(self) -> bool:
        try:
            Debug.logger.debug(f"Requesting {GIT_CHANGELOG_LIST}")
            r:requests.Response = requests.get(GIT_CHANGELOG_LIST, timeout=2)
            r.raise_for_status()
        except requests.RequestException as e:
            Debug.logger.error("Failed to get changelog, exception info:", exc_info=e)
            self.install_update = False
            return False

        Debug.logger.debug(f"{json.loads(r.content)}")
        # Get the changelog and replace all breaklines with simple ones
        changelogs:str = json.loads(r.content).get('body', '')
        self.changelogs = "\n".join(changelogs.splitlines())
        self.download_url = json.loads(r.content).get('zipball_url', '')
        Debug.logger.debug(f"{changelogs}")

        return True


    @catch_exceptions
    def check_for_update(self) -> None:
        try:
            Debug.logger.debug(f"Checking for update")
            response:requests.Response = requests.get(GIT_VERSION, timeout=2)
            if response.status_code != 200:
                Debug.logger.error(f"Could not query latest {GIT_PROJECT} version (status code {response.status_code}): {response.text}")
                return

            Debug.logger.debug(f"version: {self.version} response {Version.coerce(response.text)}")
            if self.version == Version.coerce(response.text):
                return
            Debug.logger.debug('Update available')
            self.update_available = True
            self.install_update = True
            self.update_version = Version.coerce(response.text)

        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)
