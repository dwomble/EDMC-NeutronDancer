import json
import os
import requests
import zipfile
from threading import Thread
from semantic_version import Version # type: ignore

from Router.constants import GIT_PROJECT, GIT_RELEASE_INFO, GIT_VERSION
from utils.Debug import Debug, catch_exceptions

class Updater():
    """
    Handle checking for, and installing, updates
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
        self.update_version:Version = Version("0.0.0")
        self.releasenotes:str = ""

        self.download_url:str = ""
        self.zip_downloaded:str = ""

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
        return


    def install(self) -> None:
        """ Download the latest zip file and install it """
        if self.install_update != True or self.zip_downloaded == "":
            return
        try:
            Debug.logger.debug(f"Extracting zipfile to {self.plugin_dir}")
            Debug.logger.debug(f"Oh no we aren't!")
            return
            with zipfile.ZipFile(self.zip_downloaded, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
        except Exception as e:
            Debug.logger.error("Failed to install update, exception info:", exc_info=e)


    def get_release(self) -> bool:
        """ Mostly only used to get the download_url """
        try:
            Debug.logger.debug(f"Requesting {GIT_RELEASE_INFO}")
            r:requests.Response = requests.get(GIT_RELEASE_INFO, timeout=2)
            r.raise_for_status()
        except requests.RequestException as e:
            Debug.logger.error("Failed to get changelog, exception info:", exc_info=e)
            self.install_update = False
            return False

        version_data:dict = json.loads(r.content)

        # Get the changelog and replace all breaklines with simple ones
        releasenotes:str = version_data.get('body', '')
        self.releasenotes = "\n".join(releasenotes.splitlines())
        Debug.logger.debug(f"Release notes: {releasenotes}")
        if version_data['draft'] == True or version_data['prerelease'] == True:
            Debug.logger.info("Latest server version is draft or pre-release, ignoring")
            return False

        assets:list = version_data.get('assets', [])
        if assets == []:
            Debug.logger.info("No assets")
            return False

        self.download_url = assets[0].get('browser_download_url', "")
        if self.download_url == "":
            Debug.logger.info("No download URL")
            return False

        return True


    @catch_exceptions
    def check_for_update(self, version:Version) -> None:
        """ Compare the current version file with github version """
        try:
            Debug.logger.debug(f"Checking for update")
            latest:Version = Version("0.0.0")
            response:requests.Response = requests.get(GIT_VERSION, timeout=2)
            if response.status_code != 200:
                Debug.logger.error(f"Could not query latest {GIT_PROJECT} version (status code {response.status_code}): {response.text}")
                return
            try:
                latest:Version = Version.coerce(response.text.strip().replace("-", ""))
            except Exception as e:
                Debug.logger.info(f"Bad version file {e}")

            Debug.logger.debug(f"Version: {version} response {latest} ")
            if version >= latest or not self.get_release():
                return

            Debug.logger.debug('Update available')

            self.update_available = True
            self.install_update = True
            self.update_version = latest
            thread:Thread = Thread(target=self.download_zip, name="Neutron Dancer update download worker")
            thread.start()

        except Exception as e:
            Debug.logger.error("Failed to check for updates, exception info:", exc_info=e)
