from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import sys

from ..core.models import Collection
from .media_downloader import MediaDownloader


@dataclass
class DownloadResult:
    """Stores the result of downloading a collection."""

    successful: list[Path] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.successful) + len(self.failed)

    @property
    def success_count(self) -> int:
        return len(self.successful)

    @property
    def failure_count(self) -> int:
        return len(self.failed)


class CollectionDownloader:
    """Downloads all media items in a collection."""

    def __init__(
        self,
        download_directory: str | Path = "downloads",
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self.download_directory = Path(download_directory)
        self.progress_callback = progress_callback

    def download(self, collection: Collection) -> DownloadResult:
        """Download every media item in the collection."""

        collection_directory = (
            self.download_directory / collection.name
        )

        downloader = MediaDownloader(
            collection_directory,
            progress_callback=self._media_progress,
        )

        result = DownloadResult()

        total = len(collection.items)

        self._send_progress({
            "type": "collection_start",
            "collection": collection.name,
            "total": total,
        })

        for index, item in enumerate(collection.items, start=1):

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

                self._send_progress({
                    "type": "item_complete",
                    "index": index,
                    "total": total,
                    "file_path": str(file_path),
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                })

            except Exception as error:

                result.failed.append(
                    (item.url, str(error))
                )

                self._send_progress({
                    "type": "item_failed",
                    "index": index,
                    "total": total,
                    "url": item.url,
                    "error": str(error),
                    "success_count": result.success_count,
                    "failure_count": result.failure_count,
                })

        self._send_progress({
            "type": "collection_complete",
            "total": total,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
        })

        return result

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