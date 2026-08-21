from pathlib import Path
import time
from typing import Callable
from urllib.request import Request, urlopen

import yt_dlp

from ..core.models import MediaItem


class _SilentLogger:
    """Consume yt-dlp messages so retry noise never reaches the console."""

    def debug(self, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


class MediaDownloader:
    """Downloads Instagram media without an account or authenticated session."""

    def __init__(
        self,
        download_directory: str | Path = "downloads",
        progress_callback: Callable[[dict], None] | None = None,
        collection_directory: str | Path | None = None,
    ):
        self.download_directory = Path(download_directory)
        self.download_directory.mkdir(parents=True, exist_ok=True)
        self.collection_directory = (
            Path(collection_directory) if collection_directory is not None else None
        )

        self.progress_callback = progress_callback

    def download(
        self,
        item: MediaItem,
        filename: str | None = None
    ) -> Path:
        """Download a single media item."""

        if item.media_type == "post":
            try:
                info = self._extract_info(item.url)
                is_carousel = bool(info.get("entries"))
                target_directory = self._target_directory(info)
                self._downloaded_files = self._download_post_media(info, target_directory)
                downloaded_file = (
                    target_directory / self._post_directory_name(info)
                    if is_carousel
                    else self._downloaded_files[0]
                )
            except Exception as error:
                raise RuntimeError(
                    f"Failed to download {item.url}: {error}"
                ) from error
            item.downloaded = True
            item.file_path = str(downloaded_file)
            item.file_paths = [str(path) for path in self._downloaded_files]
            return downloaded_file

        # Reels download directly without a separate metadata request, which
        # halves the number of Instagram calls and avoids most rate-limit errors.
        target_directory = self.collection_directory or self.download_directory
        output_template = self._build_output_template(
            filename,
            target_directory,
        )
        self._downloaded_files: list[Path] = []

        options = {
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "progress_hooks": [self._progress_hook],
            "logger": _SilentLogger(),
            **self._cookies_options(),
        }

        try:
            self._download_via_ytdlp(item.url, options)

            if not self._downloaded_files:
                raise RuntimeError("yt-dlp did not report a downloaded file")

            downloaded_file = self._downloaded_files[0]

        except Exception as error:
            raise RuntimeError(
                f"Failed to download {item.url}: {error}"
            ) from error

        item.downloaded = True
        item.file_path = str(downloaded_file)
        item.file_paths = [str(path) for path in self._downloaded_files]

        return downloaded_file

    @staticmethod
    def _download_via_ytdlp(url: str, options: dict) -> None:
        """Run one yt-dlp download against the given options."""

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)

    @classmethod
    def _extract_info(cls, url: str) -> dict:
        """Read metadata before deciding whether this is a carousel."""

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
            # Instagram exposes image posts as thumbnails rather than video
            # formats. Keep that metadata instead of failing the extraction.
            "ignore_no_formats_error": True,
            "logger": _SilentLogger(),
            **cls._cookies_options(),
        }

        return cls._extract_with_options(url, options)

    @staticmethod
    def _extract_with_options(url: str, options: dict) -> dict:
        """Run one metadata-only extraction against the given options."""

        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(url, download=False)

    @staticmethod
    def _cookies_options() -> dict:
        """Use a cookies.txt file if the user provided one to avoid login walls."""

        for candidate in (Path("cookies.txt"), Path("data/cookies.txt")):
            if candidate.exists():
                return {"cookies": str(candidate)}
        return {}

    def _download_post_media(
        self,
        info: dict,
        download_directory: Path,
    ) -> list[Path]:
        """Download the direct image or video URL for every post slide."""

        entries = info.get("entries") or [info]
        post_directory = download_directory / self._post_directory_name(info)
        downloaded_files = []

        for index, entry in enumerate(entries, start=1):
            url, extension = self._get_post_media_url(entry)
            destination = post_directory / f"{index:03d}.{extension}"
            self._download_url(url, destination, entry.get("http_headers"))
            downloaded_files.append(destination)

        return downloaded_files

    @staticmethod
    def _get_post_media_url(entry: dict) -> tuple[str, str]:
        """Prefer video formats; image posts provide their best image as a thumbnail."""

        formats = entry.get("formats") or []
        if formats:
            best_format = max(
                formats,
                key=lambda media: (
                    media.get("height") or 0,
                    media.get("width") or 0,
                    media.get("filesize") or 0,
                ),
            )
            if best_format.get("url"):
                return best_format["url"], best_format.get("ext") or "mp4"

        thumbnails = entry.get("thumbnails") or []
        if thumbnails:
            best_thumbnail = max(
                thumbnails,
                key=lambda image: (
                    image.get("height") or 0,
                    image.get("width") or 0,
                ),
            )
            if best_thumbnail.get("url"):
                return best_thumbnail["url"], "jpg"

        raise RuntimeError("Instagram did not provide downloadable post media")

    def _download_url(
        self,
        url: str,
        destination: Path,
        headers: dict | None,
    ) -> None:
        """Save one resolved Instagram CDN URL and report byte progress."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        request_headers = {
            "Referer": "https://www.instagram.com/",
            "User-Agent": "Mozilla/5.0",
            **(headers or {}),
        }

        with urlopen(Request(url, headers=request_headers)) as response:
            total_bytes = int(response.headers.get("Content-Length") or 0)
            downloaded_bytes = 0
            started_at = time.monotonic()

            with destination.open("wb") as file:
                while chunk := response.read(1024 * 1024):
                    file.write(chunk)
                    downloaded_bytes += len(chunk)
                    self._send_direct_progress(
                        destination,
                        downloaded_bytes,
                        total_bytes,
                        started_at,
                    )

    def _send_direct_progress(
        self,
        destination: Path,
        downloaded_bytes: int,
        total_bytes: int,
        started_at: float,
    ) -> None:
        """Report progress for post media fetched directly from Instagram's CDN."""

        if self.progress_callback is not None:
            elapsed = max(time.monotonic() - started_at, 0.001)
            speed = downloaded_bytes / elapsed
            remaining_bytes = max(total_bytes - downloaded_bytes, 0)
            self.progress_callback({
                "status": "downloading",
                "downloaded_bytes": downloaded_bytes,
                "total_bytes": total_bytes,
                "speed": speed,
                "eta": int(remaining_bytes / speed) if speed and total_bytes else None,
                "filename": str(destination),
            })

    def _progress_hook(self, data: dict) -> None:
        """Receive and forward useful progress information."""

        if data.get("status") == "finished":
            filename = data.get("filename")
            if filename:
                path = Path(filename)
                if path not in self._downloaded_files:
                    self._downloaded_files.append(path)

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
        filename: str | None,
        download_directory: Path,
    ) -> str:
        """Build a flat yt-dlp output path inside the channel directory."""

        if filename:
            return str(download_directory / filename)

        # The shortcode suffix keeps reels from the same account unique; without
        # it yt-dlp silently overwrites the earlier file when titles collide.
        return str(
            download_directory / "%(title)s [%(id)s].%(ext)s"
        )

    def _target_directory(self, info: dict) -> Path:
        """Return the channel folder for collection downloads."""

        if self.collection_directory is None:
            return self.download_directory

        channel_name = next(
            (
                str(info[field])
                for field in (
                    "channel",
                    "uploader",
                    "creator",
                    "uploader_id",
                    "channel_id",
                )
                if info.get(field)
            ),
            "unknown_channel",
        )
        return self.collection_directory / self._sanitize_path_segment(channel_name)

    @staticmethod
    def _post_directory_name(info: dict) -> str:
        """Create a stable folder name for all media in one Instagram post."""

        return MediaDownloader._sanitize_path_segment(str(info.get("id") or "post"))

    @staticmethod
    def _sanitize_path_segment(value: str) -> str:
        """Make one safe, non-reserved Windows path component."""

        sanitized = "".join(
            "_" if character in '<>:"/\\|?*' or ord(character) < 32 else character
            for character in value
        ).strip(". ")
        reserved_name = sanitized.split(".", 1)[0].upper()
        if not sanitized or reserved_name in {
            "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
            "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3",
            "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
        }:
            return "unnamed"
        return sanitized[:255]
