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

    def __init__(self, version:str='', plugin_dir:str='') -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        if version != '': self.version = version
        if plugin_dir != '': self.plugin_dir = plugin_dir

        self.update_available:bool = False

        self.zip_name = f"{GIT_PROJECT}-{version}.zip"
        self.zip_path = os.path.join(self.plugin_dir, self.zip_name)
        self.zip_downloaded = False
        self.changelogs = self.get_changelogs()

        # Make sure we're actually initialized
        if self.version != '' and self.plugin_dir != '':
            self._initialized = True


    def download_zip(self):
        """ Download the zipfile of the latest version """
        url = f"{GIT_DOWNLOAD}/v{self.version}/{self.zip_name}"
        try:
            r = requests.get(url)
            r.raise_for_status()
        except Exception:
            Debug.logger.error(f"Failed to download {GIT_PROJECT} update (status code {r.status_code}).)")
            self.zip_downloaded = False
        else:
            with open(self.zip_path, 'wb') as f:
                Debug.logger.info(f"Downloading {GIT_PROJECT} to " + self.zip_path)
                f.write(os.path.join(r.content))
            self.zip_downloaded = True

        return self.zip_downloaded

    def install_update(self):
        if not self.download_zip():
            return
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
            os.remove(self.zip_path)
        except Exception as e:
            Debug.logger.error("Failed to install update, exception info:", exc_info=e)


    def get_changelogs(self) -> str:
        try:
            r = requests.get(GIT_CHANGELOG_LIST, timeout=2)
            r.raise_for_status()
        except requests.RequestException as e:
            Debug.logger.error("Failed to get changelog, exception info:", exc_info=e)
            return ""

        # Get the changelog and replace all breaklines with simple ones
        changelogs = json.loads(r.content)["body"]
        changelogs = "\n".join(changelogs.splitlines())
        return changelogs


    @catch_exceptions
    def check_for_update(self) -> None:
        try:
            Debug.logger.debug(f"Checking for update")
            response:requests.Response = requests.get(GIT_VERSION, timeout=2)
            if response.status_code != 200:
                Debug.logger.error(f"Could not query latest {GIT_PROJECT} version (status code {response.status_code}): {response.text}")
                return
            Debug.logger.debug(f"response {response.text}")
            if Context.plugin_version != Version.coerce(response.text):
                Debug.logger.debug('Update available')
                self.update_available = True

        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)


    def goto_changelog_page(self) -> None:
        webbrowser.open(GIT_CHANGELOG + self.version.replace('.', ''))
