from pathlib import Path

from src.core.collection_manager import CollectionManager
from src.downloader.media_downloader import MediaDownloader


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

    item = collection.items[0]

    print("Testing downloader")
    print("=" * 30)
    print(f"Collection : {collection.name}")
    print(f"Media type : {item.media_type}")
    print(f"URL        : {item.url}")
    print()
    print("Downloading...")

    downloader = MediaDownloader(
        Path("downloads") / collection.name
    )

    try:
        file_path = downloader.download(item)

        print()
        print("Download successful!")
        print(f"Saved to: {file_path}")

    except Exception as error:
        print()
        print(f"Download failed:")
        print(error)


if __name__ == "__main__":
    main()