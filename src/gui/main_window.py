import threading
import tkinter as tk
from os import startfile
from pathlib import Path
from tkinter import messagebox, ttk

from ..core.collection_manager import CollectionManager
from ..core.models import Collection
from ..downloader.collection_downloader import CollectionDownloader, DownloadResult


class MainWindow:
    """Desktop UI for selecting and downloading saved Instagram collections."""

    BACKGROUND = "#100d24"
    PANEL = "#1c1837"
    PANEL_ALT = "#28234b"
    TEXT = "#f5f2ff"
    MUTED = "#b9b4d3"
    ACCENT = "#ff719a"
    ACCENT_DARK = "#ba466d"
    MINT = "#79e5d1"
    BLUE = "#65bdf5"
    GOLD = "#ffc978"
    RED = "#f05b5b"
    YELLOW = "#ffd34e"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Instagram Archive Studio")
        self.root.geometry("980x820")
        self.root.minsize(860, 700)

        self.manager = CollectionManager()
        self.collections: list[Collection] = []
        self.pause_event = threading.Event()
        self.is_downloading = False
        self.last_queue: list[Collection] = []
        self.failed_collections: list[Collection] = []
        self._build_ui()
        self._load_collections()

    def _build_ui(self) -> None:
        """Create the twilight anime-inspired desktop layout."""

        self.background = tk.Canvas(
            self.root,
            background=self.BACKGROUND,
            highlightthickness=0,
        )
        self.background.pack(fill="both", expand=True)
        self.background.bind("<Configure>", self._draw_background)

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Download.Horizontal.TProgressbar",
            troughcolor="#39325f",
            background=self.ACCENT,
            bordercolor="#39325f",
            lightcolor=self.ACCENT,
            darkcolor=self.ACCENT,
        )

        self.content = tk.Frame(self.background, bg=self.BACKGROUND)
        self.content_window = self.background.create_window(
            0, 0, anchor="nw", window=self.content
        )
        self.content.bind("<Configure>", self._fit_content)

        self._build_header()
        self._build_selection_panel()
        self._build_progress_panel()
        self._build_controls()

    def _draw_background(self, event=None) -> None:
        """Draw a lightweight original anime-inspired night scene behind the UI."""

        width = self.background.winfo_width()
        height = self.background.winfo_height()
        if hasattr(self, "content_window"):
            self.background.itemconfigure(self.content_window, width=width)
        self.background.delete("scene")
        self.background.create_rectangle(0, 0, width, height, fill="#100d24", outline="", tags="scene")
        self.background.create_rectangle(0, 0, width, height * 0.30, fill="#202a66", outline="", tags="scene")
        self.background.create_rectangle(0, height * 0.30, width, height * 0.62, fill="#30245c", outline="", tags="scene")
        self.background.create_oval(width - 260, 28, width - 90, 198, fill="#ffcf9e", outline="", tags="scene")
        self.background.create_oval(width - 220, 48, width - 100, 168, fill="#fff1d7", outline="", tags="scene")
        for x, y, size, color in ((70, 80, 2, "#f7e5ff"), (150, 145, 3, "#79e5d1"), (310, 70, 2, "#ffc978"), (520, 115, 3, "#f7e5ff"), (710, 60, 2, "#79e5d1"), (850, 205, 2, "#ffc978")):
            self.background.create_oval(x, y, x + size, y + size, fill=color, outline="", tags="scene")
        self.background.create_polygon(0, height, 0, height - 200, 250, height - 330, 450, height - 170, 680, height - 320, width, height - 180, width, height, fill="#171434", outline="", tags="scene")
        self.background.create_polygon(0, height, 0, height - 105, 240, height - 185, 420, height - 90, 690, height - 190, width, height - 100, width, height, fill="#25204a", outline="", tags="scene")
        self.background.tag_lower("scene")

    def _fit_content(self, event=None) -> None:
        self.background.itemconfigure(self.content_window, width=self.background.winfo_width())

    def _panel(self, parent) -> tk.Frame:
        return tk.Frame(parent, bg=self.PANEL, highlightbackground="#4e4676", highlightthickness=1)

    def _label(self, parent, text, size=10, bold=False, color=None, **kwargs) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=color or self.TEXT,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            **kwargs,
        )

    def _button(self, parent, text, command, color=None, **kwargs) -> tk.Button:
        padding_x = kwargs.pop("padx", 14)
        padding_y = kwargs.pop("pady", 8)
        color = color or self.PANEL_ALT
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg=self.TEXT,
            activebackground=self.ACCENT_DARK if color == self.ACCENT else "#39325f",
            activeforeground=self.TEXT,
            relief="flat",
            bd=0,
            padx=padding_x,
            pady=padding_y,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
            **kwargs,
        )

    def _build_header(self) -> None:
        header = tk.Frame(self.content, bg=self.BACKGROUND)
        header.pack(fill="x", padx=42, pady=(30, 16))
        self._label(header, "INSTAGRAM", 11, True, self.MINT).pack(anchor="w")
        self._label(header, "Archive Studio", 28, True).pack(anchor="w")
        self._label(
            header,
            "Queue collections, preserve every slide, and keep your library tidy.",
            10,
            color=self.MUTED,
        ).pack(anchor="w", pady=(2, 0))

    def _build_selection_panel(self) -> None:
        panel = self._panel(self.content)
        panel.pack(fill="x", padx=42, pady=(0, 14))
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)

        left = tk.Frame(panel, bg=self.PANEL)
        left.grid(row=0, column=0, sticky="nsew", padx=(18, 10), pady=16)
        self._label(left, "Collections", 12, True).pack(anchor="w")
        self._label(left, "Select one or more saved collections.", 9, color=self.MUTED).pack(anchor="w", pady=(2, 8))

        list_frame = tk.Frame(left, bg=self.PANEL)
        list_frame.pack(fill="both", expand=True)
        self.collection_list = tk.Listbox(
            list_frame,
            height=8,
            selectmode="extended",
            exportselection=False,
            bg="#141128",
            fg=self.TEXT,
            selectbackground=self.ACCENT,
            selectforeground=self.TEXT,
            highlightthickness=0,
            activestyle="none",
            font=("Segoe UI", 10),
        )
        scrollbar = tk.Scrollbar(list_frame, command=self.collection_list.yview)
        self.collection_list.configure(yscrollcommand=scrollbar.set)
        self.collection_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.collection_list.bind("<<ListboxSelect>>", self._selection_changed)

        selection_actions = tk.Frame(left, bg=self.PANEL)
        selection_actions.pack(fill="x", pady=(8, 0))
        self._button(selection_actions, "Select all", self._select_all, color=self.BLUE, padx=9, pady=5).pack(side="left")
        self._button(selection_actions, "Invert", self._invert_selection, color=self.MINT, padx=9, pady=5).pack(side="left", padx=(7, 0))
        self._button(selection_actions, "Clear", self._clear_selection, padx=9, pady=5).pack(side="left", padx=(7, 0))

        right = tk.Frame(panel, bg=self.PANEL)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 18), pady=16)
        self._label(right, "Download Range", 12, True).pack(anchor="w")
        self._label(right, "Items to take from each selected collection.", 9, color=self.MUTED).pack(anchor="w", pady=(2, 12))
        self.all_collections_var = tk.BooleanVar(value=False)
        self.all_collections_check = tk.Checkbutton(
            right,
            text="Download every collection",
            variable=self.all_collections_var,
            command=self._toggle_all_collections,
            bg=self.PANEL,
            fg=self.YELLOW,
            activebackground=self.PANEL,
            activeforeground=self.YELLOW,
            selectcolor="#141128",
            font=("Segoe UI", 10, "bold"),
        )
        self.all_collections_check.pack(anchor="w", pady=(0, 8))
        range_row = tk.Frame(right, bg=self.PANEL)
        range_row.pack(anchor="w")
        self._label(range_row, "First", 11).pack(side="left")
        self.limit_var = tk.StringVar(value="5")
        self.limit_input = tk.Spinbox(
            range_row,
            from_=1,
            to=99999,
            textvariable=self.limit_var,
            width=7,
            bg="#141128",
            fg=self.TEXT,
            buttonbackground=self.PANEL_ALT,
            insertbackground=self.TEXT,
            relief="flat",
            font=("Segoe UI", 11, "bold"),
        )
        self.limit_input.pack(side="left", padx=8)
        self._label(range_row, "items", 11).pack(side="left")
        self.all_items_var = tk.BooleanVar(value=False)
        self.all_items_check = tk.Checkbutton(
            right,
            text="Download all items in each collection",
            variable=self.all_items_var,
            command=self._toggle_all_items,
            bg=self.PANEL,
            fg=self.GOLD,
            activebackground=self.PANEL,
            activeforeground=self.GOLD,
            selectcolor="#141128",
            font=("Segoe UI", 10, "bold"),
        )
        self.all_items_check.pack(anchor="w", pady=(12, 0))
        self.selection_summary = self._label(right, "No collections selected", 10, color=self.MINT, wraplength=330, justify="left")
        self.selection_summary.pack(anchor="w", pady=(18, 0))
        self._label(right, "Existing URLs are skipped automatically.", 9, color=self.MUTED).pack(anchor="w", pady=(4, 0))

    def _build_progress_panel(self) -> None:
        panel = self._panel(self.content)
        panel.pack(fill="x", padx=42, pady=(0, 14))
        self._label(panel, "Download Progress", 12, True).pack(anchor="w", padx=18, pady=(15, 4))
        self.status_label = self._label(panel, "Load collections to begin.", 10, color=self.MUTED)
        self.status_label.pack(anchor="w", padx=18)

        self.overall_progress = ttk.Progressbar(panel, style="Download.Horizontal.TProgressbar", mode="determinate")
        self.overall_progress.pack(fill="x", padx=18, pady=(12, 4))
        self.overall_status = self._label(panel, "0 / 0 items", 9, color=self.MUTED)
        self.overall_status.pack(anchor="w", padx=18)

        self.current_file_label = self._label(panel, "Waiting for a queue.", 10, color=self.TEXT, wraplength=820, justify="left")
        self.current_file_label.pack(anchor="w", padx=18, pady=(12, 3))
        self.current_progress = ttk.Progressbar(panel, style="Download.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.current_progress.pack(fill="x", padx=18, pady=(0, 4))
        self.current_details = self._label(panel, "0% | 0 MB / 0 MB", 9, color=self.MUTED)
        self.current_details.pack(anchor="w", padx=18, pady=(0, 15))

    def _build_controls(self) -> None:
        controls = tk.Frame(self.content, bg=self.BACKGROUND)
        controls.pack(fill="x", padx=42, pady=(0, 26))
        self.download_button = self._button(controls, "Start Download", self._start_download, color=self.ACCENT, state="disabled")
        self.download_button.pack(side="left")
        self.pause_button = self._button(controls, "Pause", self._toggle_pause, color=self.YELLOW, state="disabled")
        self.pause_button.pack(side="left", padx=8)
        self.restart_button = self._button(controls, "Restart Queue", self._restart_queue, state="disabled")
        self.restart_button.pack(side="left")
        self.retry_button = self._button(controls, "Retry Failed", self._retry_failed, color=self.RED, state="disabled")
        self.retry_button.pack(side="left", padx=8)
        self.open_downloads_button = self._button(controls, "Open Downloads", self._open_downloads, color=self.BLUE)
        self.open_downloads_button.pack(side="right")

    def _load_collections(self) -> None:
        html_file = Path("data/saved_collections.html")
        if not html_file.exists():
            messagebox.showerror("File Not Found", f"Could not find:\n{html_file}")
            return
        try:
            self.collections = self.manager.load_from_html(html_file)
            for collection in self.collections:
                self.collection_list.insert("end", f"{collection.name}  ({collection.item_count})")
            self.status_label.config(text=f"{len(self.collections)} collections loaded. Select one or more to build a queue.")
        except Exception as error:
            messagebox.showerror("Loading Error", str(error))

    def _selected_collections(self) -> list[Collection]:
        return [self.collections[index] for index in self.collection_list.curselection()]

    def _selection_changed(self, event=None) -> None:
        selected = self._selected_collections()
        if self.all_collections_var.get() and len(selected) != len(self.collections):
            self.all_collections_var.set(False)
        item_count = sum(collection.item_count for collection in selected)
        if self.all_items_var.get():
            range_text = f"all {item_count} item(s)"
        else:
            range_text = f"up to {min(item_count, self._current_limit())} item(s) per collection"
        self.selection_summary.config(text=f"{len(selected)} collection(s), {range_text}")
        if not self.is_downloading:
            self.download_button.config(state="normal" if selected else "disabled")

    def _select_all(self) -> None:
        self.collection_list.selection_set(0, "end")
        self._selection_changed()

    def _clear_selection(self) -> None:
        self.all_collections_var.set(False)
        self.collection_list.selection_clear(0, "end")
        self._selection_changed()

    def _invert_selection(self) -> None:
        self.all_collections_var.set(False)
        selected = set(self.collection_list.curselection())
        self.collection_list.selection_clear(0, "end")
        for index in range(len(self.collections)):
            if index not in selected:
                self.collection_list.selection_set(index)
        self._selection_changed()

    def _toggle_all_items(self) -> None:
        self.limit_input.config(state="disabled" if self.all_items_var.get() else "normal")
        self._selection_changed()

    def _toggle_all_collections(self) -> None:
        if self.all_collections_var.get():
            self.collection_list.selection_set(0, "end")
        else:
            self.collection_list.selection_clear(0, "end")
        self._selection_changed()

    def _current_limit(self) -> int:
        try:
            return max(1, int(self.limit_var.get()))
        except ValueError:
            return 0

    def _download_limit(self) -> int | None:
        try:
            limit = int(self.limit_var.get())
            if limit < 1:
                raise ValueError
            return limit
        except ValueError:
            messagebox.showerror("Invalid Range", "Enter a whole number greater than zero.")
            return None

    def _start_download(self) -> None:
        limit = self._download_limit()
        selected = self._selected_collections()
        if limit is None or not selected:
            return
        queue = [
            Collection(
                collection.name,
                list(collection.items if self.all_items_var.get() else collection.items[:limit]),
            )
            for collection in selected
        ]
        queue = [collection for collection in queue if collection.items]
        if not queue:
            messagebox.showinfo("No Media", "The selected collections do not contain media.")
            return
        self.last_queue = queue
        self._begin_download(queue, "Downloading selected collections")

    def _begin_download(self, queue: list[Collection], status: str) -> None:
        self.is_downloading = True
        self.pause_event.clear()
        total = sum(len(collection.items) for collection in queue)
        self.overall_progress.config(maximum=total, value=0)
        self.current_progress.config(value=0)
        self.overall_status.config(text=f"0 / {total} items")
        self.status_label.config(text=status)
        self.collection_list.config(state="disabled")
        self.limit_input.config(state="disabled")
        self.all_items_check.config(state="disabled")
        self.all_collections_check.config(state="disabled")
        self.download_button.config(state="disabled")
        self.pause_button.config(state="normal", text="Pause")
        self.restart_button.config(state="disabled")
        self.retry_button.config(state="disabled")
        threading.Thread(target=self._download_worker, args=(queue, total), daemon=True).start()

    def _download_worker(self, queue: list[Collection], total: int) -> None:
        results: list[DownloadResult] = []
        offset = 0
        for collection in queue:
            callback = lambda event, offset=offset: self._handle_progress(event, offset, total)
            downloader = CollectionDownloader("downloads", callback, self.pause_event)
            results.append(downloader.download(collection))
            offset += len(collection.items)
        self.root.after(0, self._download_finished, results, total)

    def _handle_progress(self, event: dict, offset: int, total: int) -> None:
        event = dict(event)
        if "index" in event:
            event["index"] += offset
        event["total"] = total
        self.root.after(0, self._update_progress, event)

    def _update_progress(self, event: dict) -> None:
        event_type = event.get("type")
        index = event.get("index", 0)
        total = event.get("total", 0)
        if event_type == "item_start":
            self.current_progress.config(value=0)
            self.current_file_label.config(text=f"Downloading {event.get('media_type', 'media')} {index} of {total}")
            self.overall_status.config(text=f"{index - 1} / {total} items")
        elif event_type == "media_progress":
            downloaded = event.get("downloaded_bytes", 0)
            size = event.get("total_bytes", 0)
            percentage = downloaded / size * 100 if size else 0
            speed = event.get("speed") or 0
            eta = event.get("eta")
            self.current_progress.config(value=percentage)
            eta_text = f" | ETA {eta}s" if eta is not None else ""
            self.current_details.config(
                text=(
                    f"{percentage:.1f}% | {downloaded / 1048576:.2f} MB / "
                    f"{size / 1048576:.2f} MB | Down {speed / 1048576:.2f} MB/s | "
                    f"Up 0.00 MB/s"
                    f"{eta_text}"
                )
            )
        elif event_type in {"item_complete", "item_skipped", "item_failed"}:
            self.overall_progress.config(value=index)
            self.overall_status.config(text=f"{index} / {total} items")
            if event_type == "item_complete":
                self.current_progress.config(value=100)
                self.current_file_label.config(text=f"Saved: {Path(event.get('file_path', '')).name}")
            elif event_type == "item_skipped":
                self.current_file_label.config(text="Skipped duplicate URL")
            else:
                self.current_file_label.config(text=f"Failed: {event.get('error', 'Unknown error')}")

    def _download_finished(self, results: list[DownloadResult], total: int) -> None:
        self.is_downloading = False
        self.failed_collections = [
            Collection(result.collection_name, list(result.failed))
            for result in results
            if result.failed
        ]
        successful = sum(result.success_count for result in results)
        skipped = sum(result.skipped_count for result in results)
        failed = sum(result.failure_count for result in results)
        self.overall_progress.config(value=total)
        self.status_label.config(text=f"Complete: {successful} saved | {skipped} duplicates skipped | {failed} failed")
        self.collection_list.config(state="normal")
        self.all_items_check.config(state="normal")
        self.all_collections_check.config(state="normal")
        self._toggle_all_items()
        self.pause_button.config(state="disabled", text="Pause")
        self.restart_button.config(state="normal" if self.last_queue else "disabled")
        self.retry_button.config(state="normal" if self.failed_collections else "disabled")
        self._selection_changed()

    def _toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.config(text="Pause")
            self.status_label.config(text="Resuming after the current item.")
        else:
            self.pause_event.set()
            self.pause_button.config(text="Resume")
            self.status_label.config(text="Paused. The current file will finish before the queue stops.")

    def _restart_queue(self) -> None:
        if self.last_queue and not self.is_downloading:
            self._begin_download(self.last_queue, "Restarting previous queue")

    def _retry_failed(self) -> None:
        if self.failed_collections and not self.is_downloading:
            self._begin_download(self.failed_collections, "Retrying failed items")

    def _open_downloads(self) -> None:
        downloads = Path("downloads").resolve()
        downloads.mkdir(parents=True, exist_ok=True)
        startfile(downloads)
