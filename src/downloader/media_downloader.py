from pathlib import Path
from typing import Callable

import yt_dlp

from ..core.models import MediaItem


class MediaDownloader:
    """Downloads Instagram media using yt-dlp."""

    def __init__(
        self,
        download_directory: str | Path = "downloads",
        progress_callback: Callable[[dict], None] | None = None,
    ):
        self.download_directory = Path(download_directory)
        self.download_directory.mkdir(parents=True, exist_ok=True)

        self.progress_callback = progress_callback

    def download(
        self,
        item: MediaItem,
        filename: str | None = None
    ) -> Path:
        """Download a single media item."""

        output_template = self._build_output_template(filename)

        options = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "progress_hooks": [self._progress_hook],
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(item.url, download=True)

                downloaded_file = Path(
                    ydl.prepare_filename(info)
                )

            item.downloaded = True
            item.file_path = str(downloaded_file)

            return downloaded_file

        except Exception as error:
            raise RuntimeError(
                f"Failed to download {item.url}: {error}"
            ) from error

    def _progress_hook(self, data: dict) -> None:
        """Receive and forward useful progress information."""

        if self.progress_callback is None:
            return

        progress = {
            "status": data.get("status"),
            "downloaded_bytes": data.get("downloaded_bytes", 0),
            "total_bytes": (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            ),
            "speed": data.get("speed"),
            "eta": data.get("eta"),
            "filename": data.get("filename"),
        }

        self.progress_callback(progress)

    def _build_output_template(
        self,
        filename: str | None
    ) -> str:
        """Build the yt-dlp output path."""

        if filename:
            return str(self.download_directory / filename)

        return str(
            self.download_directory / "%(title)s.%(ext)s"
        )