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


    def __init__(self, plugin_dir:str='') -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        if plugin_dir != '': self.plugin_dir:str = plugin_dir

        self.update_available:bool = False
        self.install_update:bool = False
        self.update_version:str

        self.download_url:str = ""
        self.zip_downloaded:str = ""

        # Make sure we're actually initialized
        if self.plugin_dir != '':
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

        self.zip_path:str = os.path.join(self.plugin_dir, "updates")
        os.makedirs(self.zip_path, exist_ok=True)
        zip_file:str = os.path.join(self.zip_path, f"{GIT_PROJECT}-{self.update_version}.zip")
        if os.path.exists(zip_file): os.remove(zip_file)
        with open(zip_file, 'wb') as f:
            Debug.logger.info(f"Downloading {GIT_PROJECT} to " + zip_file)
            #f.write(os.path.join(r.content))
            for chunk in r.iter_content(chunk_size=32768):
                f.write(chunk)
        self.zip_downloaded = zip_file
        return True


    def install(self) -> None:
        """ Download the latest zip file and install it """
        if self.install_update != True or not self.get_release() or not self.download_zip():
            return
        try:
            Debug.logger.debug(f"Extracting zipfile to {self.plugin_dir}")
            with zipfile.ZipFile(self.zip_downloaded, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
            #os.remove(self.zip_downloaded)
        except Exception as e:
            Debug.logger.error("Failed to install update, exception info:", exc_info=e)


    def get_release(self) -> bool:
        """ Mostly only used to get the download_url """
        try:
            Debug.logger.debug(f"Requesting {GIT_CHANGELOG_LIST}")
            r:requests.Response = requests.get(GIT_CHANGELOG_LIST, timeout=2)
            r.raise_for_status()
        except requests.RequestException as e:
            Debug.logger.error("Failed to get changelog, exception info:", exc_info=e)
            self.install_update = False
            return False

        version_data:dict = json.loads(r.content)

        # Get the changelog and replace all breaklines with simple ones
        changelogs:str = version_data.get('body', '')
        self.changelogs = "\n".join(changelogs.splitlines())

        if version_data['draft'] == True or version_data['prerelease'] == True:
            Debug.logger.info("Latest server version is draft or pre-release, ignoring")
            return False

        assets:list = version_data.get('assets', [])
        if assets == []: return False

        self.download_url = assets[0].get('browser_download_url', "")
        if self.download_url == "": return False

        return True


    @catch_exceptions
    def check_for_update(self, version:str) -> None:
        """ Compare the current version file with github version """
        try:
            Debug.logger.debug(f"Checking for update")

            response:requests.Response = requests.get(GIT_VERSION, timeout=2)
            if response.status_code != 200:
                Debug.logger.error(f"Could not query latest {GIT_PROJECT} version (status code {response.status_code}): {response.text}")
                return
            latest:str = str(Version.coerce(response.text)).strip().replace("-", "")
            Debug.logger.debug(f"version: {version} response {latest}")
            if version == latest:
                return
            Debug.logger.debug('Update available')
            self.update_available = True
            self.install_update = True
            self.update_version = latest

        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)
