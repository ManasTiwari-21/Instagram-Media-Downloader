from pathlib import Path

from src.core.collection_manager import CollectionManager


def main():
    print("Instagram Media Downloader")
    print("=" * 30)

    html_file = Path("data/saved_collections.html")

    if not html_file.exists():
        print(f"\nHTML file not found: {html_file}")
        print("Place your Instagram exported HTML file inside the data folder.")
        return

    manager = CollectionManager()

    try:
        collections = manager.load_from_html(html_file)

    except Exception as error:
        print(f"\nError while parsing HTML: {error}")
        return

    print(f"\nCollections found: {len(collections)}")
    print(f"Media items found: {manager.total_items()}")

    print("\nCollections:")
    print("-" * 30)

    for collection in collections:
        print(
            f"{collection.name}: "
            f"{collection.item_count} items"
        )


if __name__ == "__main__":
    main()