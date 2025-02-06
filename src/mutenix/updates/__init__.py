# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
import io
import logging
import webbrowser

import hid
import requests
import semver
from mutenix.hid_commands import VersionInfo
from mutenix.updates.device_update import perform_upgrade_with_file

_logger = logging.getLogger(__name__)


def check_for_device_update(
    device: hid.device,
    device_version: VersionInfo,
    proxy: str | None = None,
):
    if proxy:
        proxies = {"https": proxy}
    else:
        proxies = {}
    try:
        result = requests.get(
            "https://api.github.com/repos/mutenix-org/firmware-macroboard/releases/latest",
            timeout=4,
            proxies=proxies,
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to fetch latest release info, status code: %s",
                result.status_code,
            )
            return False

        releases = result.json()
        latest_version = releases.get("tag_name", "v0.0.0")[1:]
        _logger.debug("Latest version: %s", latest_version)
        online_version = semver.Version.parse(latest_version)
        local_version = semver.Version.parse(device_version.version)
        if online_version.compare(local_version) <= 0:
            _logger.info("Device is up to date")
            return False

        print("Device update available, starting update, please be patient")
        assets = releases.get("assets", [])
        for asset in assets:
            if asset.get("name") == f"v{latest_version}.tar.gz":
                update_url = asset.get("browser_download_url")
                result = requests.get(update_url)
                result.raise_for_status()
                perform_upgrade_with_file(device, io.BytesIO(result.content))
                return True
    except requests.RequestException as e:
        _logger.error("Failed to check for device update availability %s", e)


# region: Update Application
def check_for_self_update(major: int, minor: int, patch: int, proxy: str | None = None):
    if proxy:
        proxies = {"https": proxy}
    else:
        proxies = {}
    try:
        result = requests.get(
            "https://api.github.com/repos/mutenix-org/software-host/releases/latest",
            timeout=4,
            proxies=proxies,
        )
        if result.status_code != 200:
            _logger.error(
                "Failed to fetch latest release info, status code: %s",
                result.status_code,
            )
            return

        releases = result.json()
        latest_version = releases.get("tag_name", "v0.0.0")[1:]
        _logger.debug("Latest version: %s", latest_version)
        online_version = semver.Version.parse(latest_version)
        local_version = semver.Version(major=major, minor=minor, patch=patch)
        if online_version.compare(local_version) <= 0:
            _logger.info("Host Software is up to date")
            return

        _logger.info("Application update available, but auto update is disabled")
        webbrowser.open(releases.get("html_url"))
    except requests.RequestException as e:
        _logger.error("Failed to check for application update availability: %s", e)


# endregion
