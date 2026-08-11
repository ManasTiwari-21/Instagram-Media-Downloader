from pathlib import Path

from bs4 import BeautifulSoup

from .models import Collection, MediaItem


class HTMLParser:
    """Parses Instagram saved collections HTML."""

    def __init__(self, html_file: str | Path):
        self.html_file = Path(html_file)

    def parse(self) -> list[Collection]:
        """Parse all collections from the exported Instagram HTML."""

        if not self.html_file.exists():
            raise FileNotFoundError(
                f"HTML file not found: {self.html_file}"
            )

        with self.html_file.open("r", encoding="utf-8") as file:
            soup = BeautifulSoup(file, "html.parser")

        collections = []

        for table in soup.find_all("table"):
            collection_name = self._get_collection_name(table)

            if not collection_name:
                continue

            items = self._get_media_items(table)

            collections.append(
                Collection(
                    name=collection_name,
                    items=items
                )
            )

        return collections

    @staticmethod
    def _get_collection_name(table) -> str | None:
        """Return the collection name if this table is a collection table."""

        metadata = {}

        for row in table.find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)

            if len(cells) != 2:
                continue

            key = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)

            if key in {"Name", "Type", "Privacy", "Update time"}:
                metadata[key] = value

        required_fields = {
            "Name",
            "Type",
            "Privacy",
            "Update time",
        }

        if required_fields.issubset(metadata):
            return metadata["Name"]

        return None

    @staticmethod
    def _get_media_items(table) -> list[MediaItem]:
        """Extract Instagram media URLs from a collection table."""

        items = []
        seen_urls = set()

        for link in table.find_all("a", href=True):
            url = link["href"].strip()

            if not HTMLParser._is_instagram_media_url(url):
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            items.append(
                MediaItem(
                    url=url,
                    media_type=HTMLParser._detect_media_type(url)
                )
            )

        return items

    @staticmethod
    def _is_instagram_media_url(url: str) -> bool:
        """Check whether a URL points to an Instagram post or reel."""

        return (
            "instagram.com/reel/" in url
            or "instagram.com/p/" in url
            or "instagram.com/tv/" in url
        )

    @staticmethod
    def _detect_media_type(url: str) -> str:
        """Determine the Instagram media type."""

        if "/reel/" in url:
            return "reel"

        if "/p/" in url:
            return "post"

        if "/tv/" in url:
            return "video"

        return "unknown"