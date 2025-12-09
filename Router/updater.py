import json
import os
import requests
import zipfile

from .context import Context


class Updater():
    def __init__(self, version, plugin_dir):
        self.version = version
        self.zip_name = "EDMC-SpanshRouterRE-" + version + ".zip"
        self.plugin_dir = plugin_dir
        self.zip_path = os.path.join(self.plugin_dir, self.zip_name)
        self.zip_downloaded = False
        self.changelogs = self.get_changelog()

    def download_zip(self):
        url = 'https://github.com/rinkulu/EDMC-SpanshRouterRE/releases/download/v' + self.version + '/' + self.zip_name
        try:
            r = requests.get(url)
            r.raise_for_status()
        except Exception:
            Context.logger.error(f"Failed to download SpanshRouterRE update (status code {r.status_code}).)")
            self.zip_downloaded = False
        else:
            with open(self.zip_path, 'wb') as f:
                Context.logger.info("Downloading SpanshRouterRE to " + self.zip_path)
                f.write(os.path.join(r.content))
            self.zip_downloaded = True

        return self.zip_downloaded

    def install(self):
        return

        if not self.download_zip():
            return
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.plugin_dir)
            os.remove(self.zip_path)
        except Exception as e:
            Context.logger.error("Failed to install update, exception info:", exc_info=e)


    def get_changelog(self) -> str:
        try:
            url = "https://api.github.com/repos/rinkulu/EDMC-SpanshRouterRE/releases/latest"
            r = requests.get(url, timeout=2)
            r.raise_for_status()
        except requests.RequestException as e:
            Context.logger.error("Failed to get changelog, exception info:", exc_info=e)
            return ""

        # Get the changelog and replace all breaklines with simple ones
        changelogs = json.loads(r.content)["body"]
        changelogs = "\n".join(changelogs.splitlines())
        return changelogs
