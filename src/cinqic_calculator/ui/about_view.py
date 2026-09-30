"""About view: honest product and Juniper-relationship copy. No popups, no nagging."""

import tkinter as tk
import webbrowser

from ..constants import APP_VERSION
from .components import section_label

_LINKS = {
    "Cinqic website": "https://cinqic.com",
    "Source repository": "https://github.com/Cinqic-Research/Cinqic-Calculator",
    "License (Apache-2.0)": "https://github.com/Cinqic-Research/Cinqic-Calculator/blob/main/LICENSE",
    "Privacy information": "https://github.com/Cinqic-Research/Cinqic-Calculator/blob/main/PRIVACY.md",
    "Third-party notices": "https://github.com/Cinqic-Research/Cinqic-Calculator/blob/main/THIRD_PARTY_NOTICES.md",
}


class AboutView(tk.Frame):
    def __init__(self, parent, colors):
        super().__init__(parent, bg=colors["background"])
        self.colors = colors
        self._build()

    def _build(self):
        c = self.colors
        section_label(self, f"Cinqic Calculator {APP_VERSION}", c, size=16).pack(anchor="w", padx=16, pady=(16, 8))

        self._paragraph(
            "Cinqic Calculator is a private, offline-first calculator for Windows, "
            "Linux, and Android, designed to work locally without accounts, cloud "
            "services, or artificial intelligence."
        )

        section_label(self, "Juniper", c).pack(anchor="w", padx=16, pady=(16, 4))
        self._paragraph(
            "Juniper, Cinqic's local-first assistant, is a separate app. It is not "
            "integrated into Cinqic Calculator, which works fully without AI."
        )

        section_label(self, "Product principle", c).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(
            self,
            text="AI should remain a choice.",
            font=("Segoe UI", 12, "italic"),
            bg=c["background"],
            fg=c["accent"],
            anchor="w",
        ).pack(anchor="w", padx=16)

        links_frame = tk.Frame(self, bg=c["background"])
        links_frame.pack(anchor="w", padx=16, pady=(20, 16))
        for label, url in _LINKS.items():
            link = tk.Label(
                links_frame,
                text=label,
                font=("Segoe UI", 10, "underline"),
                bg=c["background"],
                fg=c["accent"],
                cursor="hand2",
            )
            link.pack(anchor="w", pady=2)
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

    def _paragraph(self, text: str):
        c = self.colors
        tk.Label(
            self,
            text=text,
            font=("Segoe UI", 10),
            bg=c["background"],
            fg=c["text_primary"],
            wraplength=380,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=16)
