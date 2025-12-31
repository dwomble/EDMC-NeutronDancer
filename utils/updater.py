import json
import os
import requests
import zipfile
from threading import Thread
from semantic_version import Version # type: ignore

from Router.constants import GIT_PROJECT, GIT_RELEASE_INFO, GIT_LATEST
from utils.debug import Debug, catch_exceptions

TIMEOUT=10

class Updater():
    """
    Handle checking for, and installing, updates

    Call check_for_update() at plugin startup. It's asynchonrous.
    Install the update when you choose (commonly on shutdown).
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

        self.update_available:bool = False # Is there an update available?
        self.install_update:bool = False # Should it be installed?
        self.update_version:Version = Version("0.0.0") # The update version number
        self.releasenotes:str = "" # The update release notes

        self.download_url:str = ""
        self.zip_downloaded:str = "" # ZIP file that was downloaded

        # Make sure we're actually initialized
        if self.plugin_dir != '':
            self._initialized = True


    def download_zip(self) -> None:
        """ Download the zipfile of the latest version """

        self.zip_path:str = os.path.join(self.plugin_dir, "updates")
        os.makedirs(self.zip_path, exist_ok=True)

        zip_file:str = os.path.join(self.zip_path, f"{GIT_PROJECT}-{str(self.update_version)}.zip")
        # Don't download again if we already have it. (Was os.remove(zip_file))
        if os.path.exists(zip_file):
            self.zip_downloaded = zip_file
            return

        try:
            r:requests.Response = requests.get(self.download_url)
            Debug.logger.debug(f"{r}")
            r.raise_for_status()
        except Exception:
            Debug.logger.error(f"Failed to download {GIT_PROJECT} update (status code {r.status_code}).)")
            return

        with open(zip_file, 'wb') as f:
            Debug.logger.info(f"Downloading {GIT_PROJECT} to " + zip_file)
            for chunk in r.iter_content(chunk_size=32768):
                f.write(chunk)
        self.zip_downloaded = zip_file


    def install(self) -> None:
        """ Download the latest zip file and install it """
        if self.install_update != True or self.zip_downloaded == "":
            return
        try:
            with zipfile.ZipFile(self.zip_downloaded, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
            with open(os.path.join(self.plugin_dir, "version"), 'w') as version_file:
                version_file.write(str(self.update_version))
            Debug.logger.info(f"Version {self.update_version} installed")
        except Exception as e:
            Debug.logger.error("Failed to install update, exception info:", exc_info=e)


    def get_release(self) -> bool:
        """ Get info about the latest release from github, version, changelog, and download url """
        try:
            Debug.logger.debug(f"Requesting {GIT_RELEASE_INFO}")
            r:requests.Response = requests.get(GIT_RELEASE_INFO, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            Debug.logger.error("Failed to get changelog, exception info:", exc_info=e)
            self.install_update = False
            return False

        version_data:dict = json.loads(r.content)
        if version_data['draft'] == True or version_data['prerelease'] == True:
            Debug.logger.info("Latest server version is draft or pre-release, ignoring")
            return False

        assets:list = version_data.get('assets', [])
        if assets == []:
            Debug.logger.info("No assets")
            return False

        try:
            self.update_version = Version.coerce(version_data.get('tag_name', '0.0.0').replace('v', ''))
        except Exception as e:
            Debug.logger.info(f"Bad version data {e}")
            return False

        # Get the changelog and replace all breaklines with simple ones
        releasenotes:str = version_data.get('body', '')
        self.releasenotes = "\n".join(releasenotes.splitlines())

        self.download_url = assets[0].get('browser_download_url', "")
        if self.download_url == "":
            Debug.logger.info("No download URL")
            return False

        return True


    def _check_update(self, version:Version) -> None:
        """ Compare the current version file with github version """
        try:
            Debug.logger.debug(f"Checking for update")
            if not self.get_release(): return
            Debug.logger.debug(f"Version: {version} response {self.update_version} ")
            if version >= self.update_version: return

            Debug.logger.debug('Update available')
            self.update_available = True
            self.install_update = True
            self.download_zip()

        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)


    def check_for_update(self, version:Version) -> None:
        """ Start an update check thread """
        thread:Thread = Thread(target=self._check_update, args=[version], name="Neutron Dancer update checker")
        thread.start()
