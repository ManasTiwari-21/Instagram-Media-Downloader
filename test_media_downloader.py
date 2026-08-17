import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.models import MediaItem
from src.downloader.media_downloader import MediaDownloader


class FakeYoutubeDL:
    instances = []
    info = {}
    downloaded_files = []

    def __init__(self, options):
        self.options = options
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, url, download):
        if download:
            for filename in self.downloaded_files:
                for hook in self.options["progress_hooks"]:
                    hook({"status": "finished", "filename": filename})
        return self.info


class FakeHeaders:
    def get(self, name):
        return "3" if name == "Content-Length" else None


class FakeResponse:
    def __init__(self):
        self.headers = FakeHeaders()
        self.content = b"img"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        content, self.content = self.content, b""
        return content


def fake_urlopen(request):
    return FakeResponse()


class MediaDownloaderTests(unittest.TestCase):
    def setUp(self):
        FakeYoutubeDL.instances = []

    @patch("src.downloader.media_downloader.yt_dlp.YoutubeDL", FakeYoutubeDL)
    def test_reel_is_downloaded_as_a_single_file(self):
        FakeYoutubeDL.info = {"id": "reel-id"}
        FakeYoutubeDL.downloaded_files = ["downloads/reel.mp4"]

        item = MediaItem("https://www.instagram.com/reel/reel-id/", "reel")
        path = MediaDownloader("downloads").download(item)

        self.assertEqual(path, Path("downloads/reel.mp4"))
        self.assertTrue(FakeYoutubeDL.instances[1].options["noplaylist"])
        self.assertEqual(item.file_paths, [str(Path("downloads/reel.mp4"))])
        self.assertEqual(
            FakeYoutubeDL.instances[1].options["outtmpl"],
            "downloads" + "\\%(title)s.%(ext)s",
        )

    @patch("src.downloader.media_downloader.yt_dlp.YoutubeDL", FakeYoutubeDL)
    def test_reel_never_creates_a_subfolder_in_a_collection_download(self):
        FakeYoutubeDL.info = {"id": "reel-id", "channel": "creator"}
        FakeYoutubeDL.downloaded_files = ["downloads/reel.mp4"]

        with TemporaryDirectory() as directory:
            root = Path(directory)
            item = MediaItem("https://www.instagram.com/reel/reel-id/", "reel")
            MediaDownloader(
                root,
                collection_directory=root / "Saved",
            ).download(item)

            outtmpl = Path(FakeYoutubeDL.instances[1].options["outtmpl"])
            self.assertEqual(outtmpl.parent, root / "Saved")
            self.assertFalse((root / "Saved" / "creator").exists())

    @patch("src.downloader.media_downloader.urlopen", fake_urlopen)
    @patch("src.downloader.media_downloader.yt_dlp.YoutubeDL", FakeYoutubeDL)
    def test_carousel_is_downloaded_to_an_ordered_post_folder(self):
        FakeYoutubeDL.info = {
            "id": "post:123",
            "entries": [
                {"thumbnails": [{"url": "https://cdn.example/image", "width": 1080}]},
                {"formats": [{"url": "https://cdn.example/video", "ext": "mp4", "height": 1080}]},
            ],
        }

        with TemporaryDirectory() as directory:
            download_directory = Path(directory)
            item = MediaItem("https://www.instagram.com/p/post-123/", "post")
            path = MediaDownloader(download_directory).download(item)

            self.assertEqual(path, download_directory / "post_123")
            self.assertEqual(
                item.file_paths,
                [
                    str(download_directory / "post_123" / "001.jpg"),
                    str(download_directory / "post_123" / "002.mp4"),
                ],
            )
            self.assertEqual(
                (download_directory / "post_123" / "001.jpg").read_bytes(),
                b"img",
            )

    @patch("src.downloader.media_downloader.urlopen", fake_urlopen)
    @patch("src.downloader.media_downloader.yt_dlp.YoutubeDL", FakeYoutubeDL)
    def test_single_image_post_is_saved_in_its_post_folder(self):
        FakeYoutubeDL.info = {
            "id": "image-post",
            "thumbnails": [{"url": "https://cdn.example/image", "width": 1080}],
        }

        with TemporaryDirectory() as directory:
            download_directory = Path(directory)
            item = MediaItem("https://www.instagram.com/p/image-post/", "post")
            path = MediaDownloader(download_directory).download(item)

            self.assertEqual(path, download_directory / "image-post" / "001.jpg")
            self.assertTrue((download_directory / "image-post" / "001.jpg").exists())

    def test_post_uses_a_sanitized_channel_directory(self):
        downloader = MediaDownloader(
            Path("root"),
            collection_directory=Path("root") / "Saved: posts",
        )

        target = downloader._target_directory({"channel": "creator: name"})

        self.assertEqual(target, Path("root") / "Saved: posts" / "creator_ name")

    def test_windows_device_names_are_not_used_as_path_segments(self):
        self.assertEqual(MediaDownloader._sanitize_path_segment("CON.txt"), "unnamed")


if __name__ == "__main__":
    unittest.main()
