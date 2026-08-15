import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

from ..core.collection_manager import CollectionManager
from ..downloader.collection_downloader import CollectionDownloader


class MainWindow:
    """Main application window."""

    def __init__(self, root: tk.Tk):
        self.root = root

        self.root.title("Instagram Media Downloader")
        self.root.geometry("700x500")
        self.root.resizable(False, False)

        self.manager = CollectionManager()
        self.collections = []
        self.selected_collection = None

        self._build_ui()
        self._load_collections()

    def _build_ui(self):
        """Build the application interface."""

        main_frame = ttk.Frame(
            self.root,
            padding=30
        )
        main_frame.pack(
            fill="both",
            expand=True
        )

        title = ttk.Label(
            main_frame,
            text="Instagram Media Downloader",
            font=("Segoe UI", 20, "bold")
        )
        title.pack(pady=(5, 25))

        # Collection selection
        ttk.Label(
            main_frame,
            text="Select Collection",
            font=("Segoe UI", 11)
        ).pack(anchor="w")

        self.collection_var = tk.StringVar()

        self.collection_dropdown = ttk.Combobox(
            main_frame,
            textvariable=self.collection_var,
            state="readonly",
            width=55
        )
        self.collection_dropdown.pack(
            fill="x",
            pady=(5, 15)
        )

        self.collection_dropdown.bind(
            "<<ComboboxSelected>>",
            self._on_collection_selected
        )

        # Collection information
        self.info_label = ttk.Label(
            main_frame,
            text="Select a collection to continue.",
            font=("Segoe UI", 11)
        )
        self.info_label.pack(pady=(10, 20))

        # Overall progress
        self.overall_label = ttk.Label(
            main_frame,
            text="Overall Progress",
            font=("Segoe UI", 10, "bold")
        )
        self.overall_label.pack(anchor="w")

        self.overall_progress = ttk.Progressbar(
            main_frame,
            orient="horizontal",
            length=640,
            mode="determinate"
        )
        self.overall_progress.pack(
            fill="x",
            pady=(5, 15)
        )

        self.overall_status = ttk.Label(
            main_frame,
            text="0 / 0"
        )
        self.overall_status.pack(anchor="w")

        # Current download
        self.current_label = ttk.Label(
            main_frame,
            text="Current Download",
            font=("Segoe UI", 10, "bold")
        )
        self.current_label.pack(
            anchor="w",
            pady=(20, 5)
        )

        self.current_file_label = ttk.Label(
            main_frame,
            text="Waiting..."
        )
        self.current_file_label.pack(anchor="w")

        self.current_progress = ttk.Progressbar(
            main_frame,
            orient="horizontal",
            length=640,
            mode="determinate"
        )
        self.current_progress.pack(
            fill="x",
            pady=(5, 5)
        )

        self.current_details = ttk.Label(
            main_frame,
            text="0% | 0 MB / 0 MB | Speed: -- | ETA: --"
        )
        self.current_details.pack(anchor="w")

        # Download button
        self.download_button = ttk.Button(
            main_frame,
            text="Download First 5",
            command=self._start_download,
            state="disabled"
        )
        self.download_button.pack(
            pady=(25, 10)
        )

        # Status
        self.status_label = ttk.Label(
            main_frame,
            text="Status: Ready"
        )
        self.status_label.pack()

    def _load_collections(self):
        """Load collections from the saved HTML file."""

        html_file = Path("data/saved_collections.html")

        if not html_file.exists():
            messagebox.showerror(
                "File Not Found",
                f"Could not find:\n{html_file}"
            )
            return

        try:
            self.collections = self.manager.load_from_html(
                html_file
            )

            collection_names = [
                collection.name
                for collection in self.collections
            ]

            self.collection_dropdown["values"] = (
                collection_names
            )

            self.status_label.config(
                text=(
                    f"Status: Loaded "
                    f"{len(collection_names)} collections"
                )
            )

        except Exception as error:
            messagebox.showerror(
                "Loading Error",
                str(error)
            )

    def _on_collection_selected(self, event=None):
        """Handle collection selection."""

        selected_name = self.collection_var.get()

        self.selected_collection = next(
            (
                collection
                for collection in self.collections
                if collection.name == selected_name
            ),
            None
        )

        if self.selected_collection is None:
            return

        total_items = len(
            self.selected_collection.items
        )

        self.info_label.config(
            text=(
                f"Collection: {self.selected_collection.name}    "
                f"Media items: {total_items}"
            )
        )

        self.overall_progress["value"] = 0
        self.overall_status.config(
            text=f"0 / 5"
        )

        self.current_progress["value"] = 0
        self.current_file_label.config(
            text="Waiting..."
        )

        self.download_button.config(
            state="normal"
        )

        self.status_label.config(
            text="Status: Ready to download"
        )

    def _start_download(self):
        """Start downloading in a background thread."""

        if self.selected_collection is None:
            return

        # Only download the first 5 for now.
        collection = self.selected_collection
        collection.items = collection.items[:5]

        self.download_button.config(
            state="disabled"
        )

        self.collection_dropdown.config(
            state="disabled"
        )

        self.status_label.config(
            text="Status: Downloading..."
        )

        # Reset progress
        self.overall_progress["maximum"] = 5
        self.overall_progress["value"] = 0

        self.current_progress["maximum"] = 100
        self.current_progress["value"] = 0

        download_thread = threading.Thread(
            target=self._download_worker,
            args=(collection,),
            daemon=True
        )

        download_thread.start()

    def _download_worker(self, collection):
        """Run the downloader outside the GUI thread."""

        downloader = CollectionDownloader(
            "downloads",
            progress_callback=self._handle_progress
        )

        try:
            downloader.download(collection)

        except Exception as error:
            self.root.after(
                0,
                self._download_failed,
                str(error)
            )

    def _handle_progress(self, event: dict):
        """Receive downloader events."""

        # Tkinter widgets must be updated from the
        # main GUI thread.
        self.root.after(
            0,
            self._update_progress,
            event
        )

    def _update_progress(self, event: dict):
        """Update the GUI using a downloader event."""

        event_type = event.get("type")

        if event_type == "collection_start":

            total = event.get("total", 0)

            self.overall_progress["maximum"] = total
            self.overall_progress["value"] = 0

            self.overall_status.config(
                text=f"0 / {total}"
            )

        elif event_type == "item_start":

            index = event.get("index", 0)
            total = event.get("total", 0)
            media_type = event.get(
                "media_type",
                "media"
            )

            self.current_file_label.config(
                text=f"Downloading {media_type}..."
            )

            self.current_progress["value"] = 0

            self.current_details.config(
                text=(
                    f"0% | 0 MB / 0 MB | "
                    f"Speed: -- | ETA: --"
                )
            )

            self.overall_status.config(
                text=f"{index - 1} / {total}"
            )

        elif event_type == "media_progress":

            status = event.get("status")

            if status != "downloading":
                return

            downloaded = event.get(
                "downloaded_bytes",
                0
            )

            total = event.get(
                "total_bytes",
                0
            )

            speed = event.get("speed")
            eta = event.get("eta")

            if total:
                percentage = (
                    downloaded / total * 100
                )
            else:
                percentage = 0

            self.current_progress["value"] = (
                percentage
            )

            downloaded_mb = (
                downloaded / (1024 * 1024)
            )

            total_mb = (
                total / (1024 * 1024)
                if total
                else 0
            )

            if speed:
                speed_text = (
                    f"{speed / (1024 * 1024):.2f} MB/s"
                )
            else:
                speed_text = "--"

            eta_text = (
                f"{eta}s"
                if eta is not None
                else "--"
            )

            self.current_details.config(
                text=(
                    f"{percentage:.1f}% | "
                    f"{downloaded_mb:.2f} MB / "
                    f"{total_mb:.2f} MB | "
                    f"Speed: {speed_text} | "
                    f"ETA: {eta_text}"
                )
            )

        elif event_type == "item_complete":

            index = event.get("index", 0)
            total = event.get("total", 0)

            self.overall_progress["value"] = index

            self.overall_status.config(
                text=f"{index} / {total}"
            )

            self.current_progress["value"] = 100

            file_path = event.get(
                "file_path",
                ""
            )

            filename = Path(file_path).name

            self.current_file_label.config(
                text=f"Completed: {filename}"
            )

        elif event_type == "item_failed":

            index = event.get("index", 0)
            total = event.get("total", 0)
            error = event.get("error", "Unknown error")

            self.overall_status.config(
                text=f"{index} / {total}"
            )

            self.current_file_label.config(
                text=f"Failed: {error}"
            )

        elif event_type == "collection_complete":

            total = event.get("total", 0)
            success = event.get(
                "success_count",
                0
            )
            failed = event.get(
                "failure_count",
                0
            )

            self.overall_progress["value"] = total

            self.overall_status.config(
                text=f"{total} / {total}"
            )

            self.status_label.config(
                text=(
                    f"Completed | "
                    f"Successful: {success} | "
                    f"Failed: {failed}"
                )
            )

            self.download_button.config(
                state="normal"
            )

            self.collection_dropdown.config(
                state="readonly"
            )

    def _download_failed(self, error):
        """Handle a download-level error."""

        self.status_label.config(
            text=f"Download failed: {error}"
        )

        self.download_button.config(
            state="normal"
        )

        self.collection_dropdown.config(
            state="readonly"
        )

        messagebox.showerror(
            "Download Error",
            error
        )