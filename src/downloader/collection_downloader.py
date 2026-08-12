from dataclasses import dataclass, field
from pathlib import Path

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

    def __init__(self, download_directory: str | Path = "downloads"):
        self.download_directory = Path(download_directory)

    def download(self, collection: Collection) -> DownloadResult:
        """Download every media item in the collection."""

        collection_directory = (
            self.download_directory / collection.name
        )

        downloader = MediaDownloader(collection_directory)
        result = DownloadResult()

        total = len(collection.items)

        for index, item in enumerate(collection.items, start=1):
            print(
                f"[{index}/{total}] "
                f"Downloading {item.media_type}: {item.url}"
            )

            try:
                file_path = downloader.download(item)

                result.successful.append(file_path)

                print(f"    ✓ Saved: {file_path}")

            except Exception as error:
                result.failed.append(
                    (item.url, str(error))
                )

                print(f"    ✗ Failed: {error}")

        return result