from pathlib import Path

from src.core.collection_manager import CollectionManager
from src.downloader.collection_downloader import CollectionDownloader


def main():
    html_file = Path("data/saved_collections.html")

    manager = CollectionManager()
    manager.load_from_html(html_file)

    collection = manager.get_collection("K drama")

    if collection is None:
        print("K drama collection not found.")
        return

    if not collection.items:
        print("K drama collection contains no media.")
        return

    print("Collection Downloader Test")
    print("=" * 40)
    print(f"Collection : {collection.name}")
    print(f"Total items: {len(collection.items)}")
    print()

    collection.items = collection.items[:5] 
    downloader = CollectionDownloader("downloads")

    result = downloader.download(collection)

    print()
    print("=" * 40)
    print("Download complete")
    print(f"Total    : {result.total}")
    print(f"Success  : {result.success_count}")
    print(f"Failed   : {result.failure_count}")


if __name__ == "__main__":
    main()