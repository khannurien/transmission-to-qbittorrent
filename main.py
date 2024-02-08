import json
import os
import sys
import time

from pathlib import Path
from typing import Any, Dict, Literal
from urllib.parse import urlparse

import qbittorrentapi
import transmission_rpc

# Get config from config.json.
with open("config.json", "r") as infile:
    config: Dict[str, Any] = json.load(infile)


def get_qbit() -> qbittorrentapi.Client:
    # qBittorrent settings.
    qb_host: str = config["qbittorrent"]["host"]
    qb_port: int = config["qbittorrent"]["port"]
    qb_username: str | None = config["qbittorrent"]["username"] or None
    qb_password: str | None = config["qbittorrent"]["password"] or None

    # Connect qBittorrent.
    client = qbittorrentapi.Client(
        host=qb_host, port=qb_port, username=qb_username, password=qb_password
    )

    # Check if login is successful.
    client.auth_log_in()
    print(f"Connected to qBittorrent {client.app.version}, {client.app.webapiVersion}.")

    return client


def get_transmission() -> transmission_rpc.Client:
    # Transmission settings.
    tr_protocol: Literal["http", "https"] = config["transmission"]["protocol"]
    tr_host: str = config["transmission"]["host"]
    tr_port: int = config["transmission"]["port"]
    tr_path: str = config["transmission"]["path"]
    tr_username: str | None = config["transmission"]["username"] or None
    tr_password: str | None = config["transmission"]["password"] or None

    # Connect Transmission.
    client = transmission_rpc.Client(
        protocol=tr_protocol,
        username=tr_username,
        password=tr_password,
        host=tr_host,
        port=tr_port,
        path=tr_path,
    )

    # Check if login is successful.
    print(
        f"Connected to Transmission {client.server_version}, {client.protocol_version}."
    )

    return client


qb_client = get_qbit()
tr_client = get_transmission()


def main() -> int:
    # Skip check or not.
    skip_check: bool = config["skip_check"]

    # Get all hashes of torrents in qBittorrent.
    qb_torrents = qb_client.torrents_info()
    qb_torrent_hashes: list[str] = [torrent.hash for torrent in qb_torrents]
    print(f"Found {len(qb_torrent_hashes)} torrents in qBittorrent.")

    # Get all torrents in Transmission.
    tr_torrents = tr_client.get_torrents()
    print(
        f"Fetched {len(tr_torrents)} torrents in Transmission. Transfer them to qBittorrent..."
    )

    for tr_torrent in tr_torrents:
        # Pause the torrent in Transmission.
        tr_client.stop_torrent(tr_torrent.id)

        # Skip torrents that already exist in qBittorrent.
        if tr_torrent.hashString in qb_torrent_hashes:
            print(f"Torrent {tr_torrent.name} already exists in qBittorrent, skipping.")
            continue

        # Check if torrent has a download directory set in Transmission.
        if tr_torrent.download_dir is None:
            print(f"Torrent {tr_torrent.name} has no download directory, skipping.")
            continue

        # Retrieve last part of torrent download path, i.e. its parent folder name.
        download_path: str = Path(tr_torrent.download_dir).name

        # Check if torrent needs to be ignored following user configuration.
        if download_path in config["ignore_categories"]:
            print(
                f"Torrent {tr_torrent.name} in ignored category {download_path}, skipping."
            )
            continue

        # Check user configuration for a destination category, otherwise fall back to folder name.
        category: str
        try:
            path_to_category: Dict[str, str] = config["path_to_category"]
            category = (
                path_to_category[download_path]
                if download_path in path_to_category
                else download_path
            )
        except KeyError:
            category = download_path

        # Add torrent to qBittorrent.
        qb_client.torrents_add(
            torrent_files=open(tr_torrent.torrent_file, "rb"),
            save_path=tr_torrent.download_dir,
            rename=tr_torrent.name,
            category=category,
            tags=tr_torrent.labels,
            is_skip_checking=skip_check,
            is_paused=True,
        )

        tr_torrent_tracker_domain = urlparse(tr_torrent.trackers[0].announce).netloc
        print(
            f"Torrent: {tr_torrent.name} Path: {tr_torrent.download_dir} Tracker: {tr_torrent_tracker_domain}"
        )

        time.sleep(1)

    return os.EX_OK


def fix_renamed() -> None:
    torrent: qbittorrentapi.TorrentDictionary

    for torrent in qb_client.torrents.info():
        files = torrent.files
        if len(files) == 1:
            file: qbittorrentapi.TorrentFile = torrent.files[0]
            torrent.rename_file(file.id, torrent.info.name)


if __name__ == "__main__":
    sys.exit(main())
    # fix_renamed()
