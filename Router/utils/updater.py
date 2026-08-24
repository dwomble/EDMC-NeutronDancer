import json
import os
import re
import requests
import zipfile
import time
from threading import Thread
from semantic_version import Version # type: ignore

from config import config, user_agent # type: ignore
from timeout_session import new_session # type: ignore
from .debug import Debug

# Check for updates at most once per day
CHECK_INTERVAL:int = (3600 * 24)
_NOTICE_HEADING:re.Pattern = re.compile(r'^##\s+(\d+)\s*$', re.MULTILINE)
TIMEOUT=10

def _headers(gh_project:str) -> dict:
    """ Blends into EDMC's own UA, per PLUGINS.md. """
    return {'User-Agent': f'{user_agent} {gh_project}-Updater'}

def read_version_file(plugin_dir:str, default:str) -> Version:
    """ Reads the "version" file  by CI at release and updated by install(). """
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
    Handle checking for, and installing, plugin updates.

    Create the object with parameters plugin_dir, gh_owner, gh_project, gh_release_info.
      gh_owner is the github owner/org, e.g. "coder"
      gh_project is the github project name, e.g. "my-plugin"
      gh_release_info is the github api url for release info, e.g. "https://api.github.com/repos/coder/my-plugin/releases/latest"
    Call check_for_update(version) at plugin startup. It's asynchronous.
    Call install() to install the update when you choose (commonly on shutdown).
    """

    def __init__(self, plugin_dir:str, gh_owner:str, gh_project:str) -> None:
        self.plugin_dir:str = plugin_dir
        self.gh_owner:str = gh_owner
        self.gh_project:str = gh_project

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
            url:str = f"https://api.github.com/repos/{self.gh_owner}/{self.gh_project}/releases/latest"
            Debug.logger.debug(f"Requesting {url}")
            session:requests.Session = new_session(timeout=TIMEOUT)
            r:requests.Response = session.get(url, headers=_headers(self.gh_project), timeout=TIMEOUT)
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


    def check_for_update(self, version:Version, plugin_name:str, interval:int = CHECK_INTERVAL) -> None:
        """ Start an update check thread. `interval` (seconds) throttles how often the check
        actually runs -- defaults to once a day. """
        last:int = config.get_int(f"{plugin_name}_last_update_check", 0)
        if last >= int(time.time()) - interval:
            return

        config.set(f"{plugin_name}_last_update_check", int(time.time()))
        thread:Thread = Thread(target=self._check_update, args=[version], name="Neutron Dancer update checker")
        thread.start()

class Notices():
    """
    Fetches NOTICES.md from the repo's default branch, tracking
    which "## N" notice heading the user has dismissed.

    Call check_for_notices() at startup -- async and throttled
    like Updater.check_for_update(). pending_notice holds the
    current one to show; call dismiss_notice() once seen. """
    def __init__(self, gh_owner:str, gh_project:str, gh_branch:str = 'main') -> None:
        self.gh_owner:str = gh_owner
        self.gh_project:str = gh_project
        self.gh_branch:str = gh_branch
        self.notice_id:int = 0
        self.notice:str = ""

    def _check_notices(self) -> None:
        try:
            session:requests.Session = new_session(timeout=TIMEOUT)
            url:str = f'https://raw.githubusercontent.com/{self.gh_owner}/{self.gh_project}/{self.gh_branch}/NOTICES.md'
            r:requests.Response = session.get(url, headers=_headers(self.gh_project), timeout=TIMEOUT)
            r.raise_for_status()
        except Exception as e:
            Debug.logger.error("Failed to fetch notices, exception info:", exc_info=e)
            return

        notices:list[tuple[int, str]] = self._parse_notices(r.text)
        if notices:
            self.notice_id, self.notice = notices[0]

    def check_for_notices(self, interval:int = CHECK_INTERVAL) -> None:
        """ Start a notices-check thread, throttled like updates. """
        last:int = config.get_int(f"{self.gh_project}_last_notice_check", 0)
        if last >= int(time.time()) - interval:
           return

        config.set(f"{self.gh_project}_last_notice_check", int(time.time()))
        thread:Thread = Thread(target=self._check_notices, args=[], name=f"{self.gh_project} notice checker")
        thread.start()

    @property
    def pending_notice(self) -> str|None:
        """ The current notice's body, or None if dismissed/none seen. """
        if self.notice_id == 0:
            return None
        dismissed:int = config.get_int(f"{self.gh_project}_dismissed_notice", 0)
        return self.notice if self.notice_id > dismissed else None

    def dismiss_notice(self) -> None:
        """ Never show this notice, or any older one, again. """
        config.set(f"{self.gh_project}_dismissed_notice", self.notice_id)

    @staticmethod
    def _parse_notices(text:str) -> list[tuple[int, str]]:
        """ (id, body) for every "## N" heading, highest id first. """
        matches:list = list(_NOTICE_HEADING.finditer(text))
        notices:list[tuple[int, str]] = []
        for i, m in enumerate(matches):
            start:int = m.end()
            end:int = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            notices.append((int(m.group(1)), text[start:end].strip()))
        notices.sort(key=lambda n: -n[0])
        return notices
