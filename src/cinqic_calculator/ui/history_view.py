"""Local calculation history view."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..expression import tidy_literal
from .components import make_button, section_label


class HistoryView(tk.Frame):
    def __init__(self, parent, colors, history, on_status=None, on_reuse=None):
        super().__init__(parent, bg=colors["background"])
        self.colors = colors
        self.history = history
        self.on_status = on_status or (lambda text: None)
        self.on_reuse = on_reuse or (lambda text: None)
        self._build()
        self.refresh()

    def _build(self):
        c = self.colors
        header = tk.Frame(self, bg=c["background"])
        header.pack(fill="x", padx=16, pady=(8, 4))
        section_label(header, "History", c, size=16).pack(side="left")
        make_button(header, "Clear all", self._clear_all, c, kind="function", width=10, height=1, font_size=10).pack(
            side="right"
        )

        columns = ("expression", "result", "timestamp")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", style="Cinqic.Treeview", selectmode="browse")
        self.tree.heading("expression", text="Expression")
        self.tree.heading("result", text="Result")
        self.tree.heading("timestamp", text="Time")
        self.tree.column("expression", width=180)
        self.tree.column("result", width=100)
        self.tree.column("timestamp", width=140)
        self.tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        # Double-clicking a calculation is the obvious way to pick it back
        # up; the Reuse button stays for keyboard and discoverability.
        self.tree.bind("<Double-Button-1>", lambda _event: self._reuse_selected())
        self.tree.bind("<Return>", lambda _event: self._reuse_selected())

        actions = tk.Frame(self, bg=c["background"])
        actions.pack(fill="x", padx=16, pady=(0, 16))
        make_button(actions, "Copy result", self._copy_selected, c, kind="function", width=12, height=1, font_size=10).pack(
            side="left", padx=(0, 6)
        )
        make_button(actions, "Reuse", self._reuse_selected, c, kind="function", width=8, height=1, font_size=10).pack(
            side="left", padx=(0, 6)
        )
        make_button(actions, "Delete", self._delete_selected, c, kind="function", width=8, height=1, font_size=10).pack(
            side="left"
        )

    def refresh(self):
        """Redraw the list, newest first.

        The row id stays the entry's real index in ``history.entries`` so
        reuse/copy/delete keep addressing the right entry regardless of the
        order rows are displayed in.
        """
        self.tree.delete(*self.tree.get_children())
        for index in reversed(range(len(self.history.entries))):
            entry = self.history.entries[index]
            values = (entry["expression"], tidy_literal(entry["result"]), entry["timestamp"])
            self.tree.insert("", "end", iid=str(index), values=values)

    def _selected_index(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _copy_selected(self):
        index = self._selected_index()
        if index is None:
            return
        self.clipboard_clear()
        self.clipboard_append(self.history.entries[index]["result"])
        self.on_status("Result copied from history")

    def _reuse_selected(self):
        index = self._selected_index()
        if index is None:
            return
        self.on_reuse(self.history.entries[index]["result"])
        self.on_status("Result loaded into calculator")

    def _delete_selected(self):
        index = self._selected_index()
        if index is None:
            return
        self.history.delete_at(index)
        self.refresh()

    def _clear_all(self):
        if not self.history.entries:
            return
        if messagebox.askyesno("Clear history", "Delete all calculation history? This cannot be undone."):
            self.history.clear()
            self.refresh()
            self.on_status("History cleared")
