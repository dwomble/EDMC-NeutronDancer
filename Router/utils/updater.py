import json
import os
import requests
import zipfile
import time
from threading import Thread
from semantic_version import Version # type: ignore

from config import config, user_agent # type: ignore
from timeout_session import new_session # type: ignore
from .debug import Debug

TIMEOUT=10

def _headers(gh_project:str) -> dict:
    """ Blends into EDMC's own UA, per PLUGINS.md. """
    return {'User-Agent': f'{user_agent} {gh_project}-Updater'}

def read_version_file(plugin_dir:str, default:str) -> Version:
    """ Reads the "version" file install() writes -- also
    stamped by CI at release, so a fresh install has one. """
    version_file:str = os.path.join(plugin_dir, "version")
    if os.path.isfile(version_file):
        with open(version_file) as f:
            text:str = f.read().strip()
        if text:
            try:
                return Version.coerce(text)
            except ValueError:
                pass
    return Version.coerce(default)

class Updater():
    """
    Handle checking for, and installing, updates

    Call check_for_update() at plugin startup. It's asynchonrous.
    Install the update when you choose (commonly on shutdown).
    """

    def __init__(self, plugin_dir:str, gh_project:str, gh_release_info:str) -> None:
        self.plugin_dir:str = plugin_dir
        self.gh_project:str = gh_project
        self.gh_release_info:str = gh_release_info

        self.update_available:bool = False # Is there an update available?
        self.install_update:bool = False # Should it be installed?
        self.update_version:Version = Version("0.0.0") # The update version number
        self.releasenotes:str = "" # The update release notes

        self.download_url:str = ""
        self.zip_downloaded:str = "" # ZIP file that was downloaded


    def download_zip(self) -> None:
        """ Download the zipfile of the latest version """

        self.zip_path:str = os.path.join(self.plugin_dir, "updates")
        os.makedirs(self.zip_path, exist_ok=True)

        zip_file:str = os.path.join(self.zip_path, f"{self.gh_project}-{str(self.update_version)}.zip")
        # Don't download again if we already have it. (Was os.remove(zip_file))
        if os.path.exists(zip_file):
            self.zip_downloaded = zip_file
            return

        r:requests.Response|None = None
        try:
            session:requests.Session = new_session(timeout=TIMEOUT)
            r = session.get(self.download_url, headers=_headers(self.gh_project), timeout=TIMEOUT)
            Debug.logger.debug(f"{r}")
            r.raise_for_status()
        except Exception:
            Debug.logger.error(f"Failed to download {self.gh_project} update (status code {r.status_code if r else 'no response'}).")
            return

        with open(zip_file, 'wb') as f:
            Debug.logger.info(f"Downloading {self.gh_project} to " + zip_file)
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
            Debug.logger.debug(f"Requesting {self.gh_release_info}")
            session:requests.Session = new_session(timeout=TIMEOUT)
            r:requests.Response = session.get(self.gh_release_info, headers=_headers(self.gh_project), timeout=TIMEOUT)
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


    def check_for_update(self, version:Version, plugin_name: str, interval:int = 3600 * 24) -> None:
        """ Start an update check thread. `interval` (seconds) throttles how often the check
        actually runs -- defaults to once a day. """
        last:int = config.get_int(f"{plugin_name}_last_update_check", 0)
        if last >= int(time.time()) - interval:
            return

        config.set(f"{plugin_name}_last_update_check", int(time.time()))
        thread:Thread = Thread(target=self._check_update, args=[version], name="Neutron Dancer update checker")
        thread.start()
