from pathlib import Path

import requests

from ..core.models import MediaItem


class MediaDownloader:
    """Downloads Instagram media files."""

    def __init__(self, download_directory: str | Path = "downloads"):
        self.download_directory = Path(download_directory)
        self.download_directory.mkdir(parents=True, exist_ok=True)

    def download(self, item: MediaItem, filename: str) -> Path:
        """Download a media item and return the saved file path."""

        output_path = self.download_directory / filename

        response = requests.get(
            item.url,
            stream=True,
            timeout=30
        )

        response.raise_for_status()

        with output_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

        item.downloaded = True
        item.file_path = str(output_path)

        return output_path