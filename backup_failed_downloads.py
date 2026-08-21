"""Backup-download Instagram reels that the main downloader could not fetch.

This is a standalone, manual tool. It does not touch the normal download
workflow: it only reads which URLs are still missing, asks a third-party
online downloader backend for a direct video link, and saves the file to
downloads/_backup/<collection>/<shortcode>.mp4. No Instagram login is used.

Successful backups are added to the download manifest so the main app treats
them as resolved. URLs the service still cannot fetch are appended to
downloads/failed_downloads.csv for later manual handling.

Usage:
    python backup_failed_downloads.py
"""

import csv
import json
import sys
import time
from pathlib import Path

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from src.core.collection_manager import CollectionManager
from src.downloader.failure_log import FailureLog

PROJECT_ROOT = Path(__file__).resolve().parent

ZORA_API = "https://api.zoraahub.com/fetch.php"
ZORA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Origin": "https://downreels.com",
    "Referer": "https://downreels.com/",
}

VIDEODROPPER_API = "https://api.videodropper.app/allinone"
VIDEODROPPER_DL = "https://dl.videodropper.app/?url="
VIDEODROPPER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Origin": "https://fastvideosave.net",
    "Referer": "https://fastvideosave.net/",
    "Accept": "application/json",
}
VIDEODROPPER_KEY = b"qwertyuioplkjhgf"

MANIFEST_PATH = PROJECT_ROOT / "downloads" / ".download_manifest.json"
BACKUP_ROOT = PROJECT_ROOT / "downloads" / "_backup"
HTML_PATH = PROJECT_ROOT / "data" / "saved_collections.html"
FAILURE_LOG_PATH = PROJECT_ROOT / "downloads" / "failed_downloads.csv"


def normalize_url(url: str) -> str:
    """Match the manifest normalization used by the main downloader."""

    return url.split("?", 1)[0].rstrip("/")


def load_manifest() -> set[str]:
    if not MANIFEST_PATH.exists():
        return set()
    try:
        urls = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return {normalize_url(url) for url in urls if isinstance(url, str)}
    except (OSError, json.JSONDecodeError):
        return set()


def save_manifest(urls: set[str]) -> None:
    temporary_path = MANIFEST_PATH.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(sorted(urls), file, indent=2)
    temporary_path.replace(MANIFEST_PATH)


def missing_items() -> list[tuple[str, str]]:
    """Return (collection_name, url) for every collection item not yet in the manifest."""

    manager = CollectionManager()
    manager.load_from_html(HTML_PATH)
    manifest = load_manifest()
    return [
        (collection.name, item.url)
        for collection in manager.collections
        for item in collection.items
        if normalize_url(item.url) not in manifest
    ]


def _zora_fetch(url: str) -> tuple[str, dict]:
    """Ask the downreels/zoraahub backend for a direct video link."""

    response = requests.post(ZORA_API, json={"url": url}, headers=ZORA_HEADERS, timeout=90)
    data = response.json()
    videos = data.get("videos") or []
    if data.get("status") != "ok" or not videos:
        raise RuntimeError((data.get("message") or "service could not fetch this reel").strip())
    return videos[0]["url"], ZORA_HEADERS


def _videodropper_fetch(url: str) -> tuple[str, dict]:
    """Ask the fastvideosave/videodropper backend for a direct video link.

    The backend expects the Instagram URL encrypted with AES-128-ECB (PKCS7)
    and hex-encoded in the ``url`` header. Videos are served through the
    dl.videodropper.app proxy.
    """

    encrypted = AES.new(VIDEODROPPER_KEY, AES.MODE_ECB).encrypt(
        pad(url.encode("utf-8"), 16)
    ).hex()
    response = requests.get(
        VIDEODROPPER_API, headers={**VIDEODROPPER_HEADERS, "url": encrypted}, timeout=90
    )
    if response.status_code != 200:
        raise RuntimeError("service could not fetch this reel")
    data = response.json()
    videos = data.get("video") or []
    if not videos or not videos[0].get("video"):
        raise RuntimeError("service could not fetch this reel")
    return VIDEODROPPER_DL + requests.utils.quote(videos[0]["video"], safe=""), VIDEODROPPER_HEADERS


def fetch_video_link(url: str) -> tuple[str, dict]:
    """Return (direct video URL, headers) from the first backend that answers."""

    for backend in (_zora_fetch, _videodropper_fetch):
        try:
            return backend(url)
        except Exception:
            continue
    raise RuntimeError("all backends could not fetch this reel")


def download_to(video_url: str, headers: dict, destination: Path) -> None:
    """Stream a video URL to disk and confirm it is a real video file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(video_url, headers=headers, timeout=180, stream=True) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_content(1 << 20):
                file.write(chunk)
    if destination.stat().st_size < 1000:
        destination.unlink()
        raise RuntimeError("downloaded file was empty or too small")


def main() -> None:
    items = missing_items()
    if not items:
        print("No missing items. Nothing to back up.")
        return

    manifest = load_manifest()
    failure_log = FailureLog(FAILURE_LOG_PATH)
    print(f"Backing up {len(items)} reels without any Instagram login...\n")

    successful: list[tuple[str, str]] = []
    still_failing: list[tuple[str, str, str]] = []

    for index, (collection_name, url) in enumerate(items, start=1):
        shortcode = url.rstrip("/").rsplit("/", 1)[-1]
        destination = BACKUP_ROOT / collection_name / f"{shortcode}.mp4"

        if destination.exists():
            successful.append((collection_name, url))
            print(f"[{index:3d}/{len(items)}] {shortcode} already backed up")
            continue

        try:
            video_url, headers = fetch_video_link(url)
            download_to(video_url, headers, destination)
            successful.append((collection_name, url))
            print(f"[{index:3d}/{len(items)}] {shortcode} OK  {destination.name}")
        except Exception as error:
            reason = str(error)
            still_failing.append((collection_name, url, reason))
            failure_log.record(url, "reel", reason)
            print(f"[{index:3d}/{len(items)}] {shortcode} FAIL  {reason}")
        time.sleep(2)

    for _, url in successful:
        manifest.add(normalize_url(url))
    save_manifest(manifest)

    rewrite_failure_log(still_failing)

    print("\nDone.")
    print(f"  Backed up:       {len(successful)}")
    print(f"  Still failing:   {len(still_failing)}")
    if still_failing:
        print(f"  Logged to:       downloads/failed_downloads.csv")
        for _, url, reason in still_failing:
            print(f"    - {url}  ({reason})")


def rewrite_failure_log(still_failing: list[tuple[str, str, str]]) -> None:
    """Keep downloads/failed_downloads.csv limited to the URLs still failing.

    URLs that are now backed up are removed so the log only reflects reels the
    backends genuinely cannot fetch (no duplicates across runs).
    """

    rows = {(url, "reel", reason) for _, url, reason in still_failing}
    with FAILURE_LOG_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(FailureLog.FIELDS)
        writer.writerows(sorted(rows))


if __name__ == "__main__":
    sys.exit(main())