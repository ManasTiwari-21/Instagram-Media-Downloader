import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.models import Collection, MediaItem
from src.downloader.collection_downloader import CollectionDownloader


class FakeMediaDownloader:
    calls = []
    failures = set()

    def __init__(self, download_directory, progress_callback=None, collection_directory=None):
        self.download_directory = Path(download_directory)
        self.collection_directory = Path(collection_directory)
        self.progress_callback = progress_callback

    @staticmethod
    def _sanitize_path_segment(value):
        return value.replace(":", "_")

    def download(self, item):
        self.__class__.calls.append((item.url, self.collection_directory))
        if item.url in self.failures:
            raise RuntimeError("temporary failure")
        item.downloaded = True
        return self.collection_directory / "channel" / "file.mp4"


class CollectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        FakeMediaDownloader.calls = []
        FakeMediaDownloader.failures = set()

    @patch("src.downloader.collection_downloader.MediaDownloader", FakeMediaDownloader)
    def test_manifest_skips_urls_across_collections_and_runs(self):
        events = []
        with TemporaryDirectory() as directory:
            downloader = CollectionDownloader(directory, events.append)
            first = downloader.download(Collection("Summer: 2026", [MediaItem("one")]))
            second = downloader.download(Collection("Other", [MediaItem("one")]))

            self.assertEqual(first.success_count, 1)
            self.assertEqual(second.skipped_count, 1)
            self.assertEqual(second.total, 1)
            self.assertEqual(len(FakeMediaDownloader.calls), 1)
            self.assertEqual(
                FakeMediaDownloader.calls[0][1],
                Path(directory) / "Summer_ 2026",
            )
            self.assertEqual(
                json.loads((Path(directory) / ".download_manifest.json").read_text()),
                ["one"],
            )
            skipped = next(event for event in events if event["type"] == "item_skipped")
            self.assertEqual(skipped["skipped_count"], 1)

    @patch("src.downloader.collection_downloader.MediaDownloader", FakeMediaDownloader)
    def test_failures_are_retryable_and_never_written_to_manifest(self):
        with TemporaryDirectory() as directory:
            item = MediaItem("will-retry")
            FakeMediaDownloader.failures = {item.url}
            downloader = CollectionDownloader(directory)
            failed = downloader.download(Collection("Saved", [item]))

            self.assertEqual(failed.failed, [item])
            self.assertEqual(failed.errors[item.url], "temporary failure")
            self.assertFalse((Path(directory) / ".download_manifest.json").exists())

            FakeMediaDownloader.failures = set()
            retried = downloader.retry_failed(failed)

            self.assertEqual(retried.success_count, 1)
            self.assertEqual(retried.failure_count, 0)
            self.assertEqual(len(FakeMediaDownloader.calls), 2)

    @patch("src.downloader.collection_downloader.MediaDownloader", FakeMediaDownloader)
    def test_pause_event_waits_before_the_next_item(self):
        pause_event = threading.Event()
        pause_event.set()
        completed = []
        with TemporaryDirectory() as directory:
            downloader = CollectionDownloader(
                directory,
                lambda event: completed.append(event),
                pause_event=pause_event,
            )
            collection = Collection("Saved", [MediaItem("paused")])

            worker = threading.Thread(target=lambda: downloader.download(collection))
            worker.start()
            time.sleep(0.1)
            self.assertTrue(worker.is_alive())
            self.assertEqual(FakeMediaDownloader.calls, [])

            pause_event.clear()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(FakeMediaDownloader.calls), 1)


if __name__ == "__main__":
    unittest.main()
