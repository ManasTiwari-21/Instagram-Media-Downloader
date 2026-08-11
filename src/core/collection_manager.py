from pathlib import Path

from .html_parser import HTMLParser
from .models import Collection


class CollectionManager:
    """Manages Instagram collections loaded from exported HTML."""

    def __init__(self):
        self.collections: list[Collection] = []

    def load_from_html(self, html_file: str | Path) -> list[Collection]:
        """Load collections from an Instagram HTML export."""

        parser = HTMLParser(html_file)
        self.collections = parser.parse()

        return self.collections

    def get_collection(self, name: str) -> Collection | None:
        """Find a collection by name."""

        for collection in self.collections:
            if collection.name == name:
                return collection

        return None

    def get_collection_names(self) -> list[str]:
        """Return the names of all loaded collections."""

        return [collection.name for collection in self.collections]

    def total_items(self) -> int:
        """Return the total number of media items across all collections."""

        return sum(
            collection.item_count
            for collection in self.collections
        )

    def clear(self) -> None:
        """Clear all loaded collections."""

        self.collections.clear()