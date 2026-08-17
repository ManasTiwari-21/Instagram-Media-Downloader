from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MediaItem:
    url: str
    media_type: str = "unknown"
    downloaded: bool = False
    file_path: Optional[str] = None
    file_paths: list[str] = field(default_factory=list)


@dataclass
class Collection:
    name: str
    items: list[MediaItem] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.items)
