import csv
from pathlib import Path


class FailureLog:
    """Append failed downloads to a persistent CSV file, one row per failure."""

    FIELDS = ["url", "media_type", "error"]

    def __init__(self, path: str | Path = "downloads/failed_downloads.csv"):
        self.path = Path(path)

    def record(self, url: str, media_type: str, error: str) -> None:
        """Write a single failure row immediately so it survives a stopped run."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "url": url,
                "media_type": media_type,
                "error": error,
            })