from dataclasses import dataclass, field
from pathlib import Path
import json
import time
from threading import Event
from typing import Callable

from ..core.models import Collection, MediaItem
from .media_downloader import MediaDownloader


@dataclass
class DownloadResult:
    """Stores the result of downloading a collection."""

    successful: list[Path] = field(default_factory=list)
    failed: list[MediaItem] = field(default_factory=list)
    skipped: list[MediaItem] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    collection_name: str = ""

    @property
    def total(self) -> int:
        return len(self.successful) + len(self.failed) + len(self.skipped)

    @property
    def success_count(self) -> int:
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


class CollectionDownloader:
    """Downloads all media items in a collection."""

    def __init__(
        self,
        download_directory: str | Path = "downloads",
        progress_callback: Callable[[dict], None] | None = None,
        pause_event: Event | None = None,
    ):
        self.download_directory = Path(download_directory)
        self.download_directory.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback
        self.pause_event = pause_event

    def download(
        self,
        collection: Collection,
        pause_event: Event | None = None,
    ) -> DownloadResult:
        """Download every media item in the collection."""

        collection_directory = self.download_directory / MediaDownloader._sanitize_path_segment(
            collection.name
        )

        downloader = MediaDownloader(
            self.download_directory,
            progress_callback=self._media_progress,
            collection_directory=collection_directory,
        )

        result = DownloadResult(collection_name=collection.name)
        downloaded_urls = self._load_manifest()

        total = len(collection.items)

        self._send_progress({
            "type": "collection_start",
            "collection": collection.name,
            "total": total,
        })

        for index, item in enumerate(collection.items, start=1):
            self._wait_while_paused(pause_event or self.pause_event)

            item_url = self._normalize_url(item.url)
            if item_url in downloaded_urls:
                result.skipped.append(item)
                self._send_progress({
                    "type": "item_skipped",
                    "index": index,
                    "total": total,
                    "url": item.url,
                    "skipped_count": result.skipped_count,
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                    "failed_items": list(result.failed),
                })
                continue

            self._send_progress({
                "type": "item_start",
                "index": index,
                "total": total,
                "media_type": item.media_type,
                "url": item.url,
            })

            try:
                file_path = downloader.download(item)

                result.successful.append(file_path)
                downloaded_urls.add(item_url)
                self._save_manifest(downloaded_urls)

                self._send_progress({
                    "type": "item_complete",
                    "index": index,
                    "total": total,
                    "file_path": str(file_path),
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                    "skipped_count": result.skipped_count,
                    "failed_items": list(result.failed),
                })

            except Exception as error:

                result.failed.append(item)
                result.errors[item.url] = str(error)

                self._send_progress({
                    "type": "item_failed",
                    "index": index,
                    "total": total,
                    "url": item.url,
                    "error": str(error),
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                    "skipped_count": result.skipped_count,
                    "failed_items": list(result.failed),
                })

        self._send_progress({
            "type": "collection_complete",
            "total": total,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "skipped_count": result.skipped_count,
            "failed_items": list(result.failed),
        })

        return result

    def retry_failed(
        self,
        result: DownloadResult,
        pause_event: Event | None = None,
    ) -> DownloadResult:
        """Retry only the items that failed in a prior collection download."""

        return self.download(
            Collection(name=result.collection_name, items=list(result.failed)),
            pause_event=pause_event,
        )

    def _manifest_path(self) -> Path:
        return self.download_directory / ".download_manifest.json"

    def _load_manifest(self) -> set[str]:
        """Read successfully downloaded source URLs from prior runs."""

        path = self._manifest_path()
        if not path.exists():
            return set()
        try:
            with path.open("r", encoding="utf-8") as file:
                urls = json.load(file)
            return {
                self._normalize_url(url)
                for url in urls
                if isinstance(url, str)
            }
        except (OSError, json.JSONDecodeError):
            return set()

    def _save_manifest(self, urls: set[str]) -> None:
        """Atomically persist only URLs whose downloads completed."""

        path = self._manifest_path()
        temporary_path = path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(sorted(urls), file, indent=2)
        temporary_path.replace(path)

    @staticmethod
    def _wait_while_paused(pause_event: Event | None) -> None:
        """Treat a set event as paused, checking only between media items."""

        while pause_event is not None and pause_event.is_set():
            time.sleep(0.05)

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Treat Instagram links with tracking parameters as the same media."""

        return url.split("?", 1)[0].rstrip("/")

    def _media_progress(self, progress: dict) -> None:
        """Forward current media download progress."""

        self._send_progress({
            "type": "media_progress",
            **progress,
        })

    def _send_progress(self, event: dict) -> None:
        """Send a progress event to the caller."""

        if self.progress_callback is not None:
            self.progress_callback(event)
