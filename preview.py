"""
preview.py
Tkinter widget that displays a Pillow image as a barcode preview.

Handles the Pillow → ImageTk conversion that plain tk.PhotoImage cannot do,
plus centering, a placeholder state, a save-to-PNG helper, and a
save-to-PDF helper.  Canvas dimensions are imported from settings so that
preview and exported PDFs are always the same size.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from PIL import Image, ImageTk

from settings import PREVIEW_MAX_WIDTH, PREVIEW_MAX_HEIGHT


class BarcodePreview(ttk.Frame):
    """
    A self-contained frame that shows a PDF417 barcode image.

    Usage
    -----
        preview = BarcodePreview(parent)
        preview.pack(fill="both", expand=True)

        # Later, after generating a barcode:
        preview.show(pil_image)

        # To clear back to placeholder:
        preview.clear()
    """

    # Placeholder appearance
    PLACEHOLDER_TEXT = "Barcode will appear here"
    PLACEHOLDER_BG   = "#f0f0f0"
    PLACEHOLDER_FG   = "#999999"

    # Maximum display size — pulled from settings so exporter matches exactly
    MAX_WIDTH  = PREVIEW_MAX_WIDTH
    MAX_HEIGHT = PREVIEW_MAX_HEIGHT

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self._pil_image: Optional[Image.Image] = None   # current full-res image
        self._tk_image:  Optional[ImageTk.PhotoImage] = None  # kept alive (no GC)

        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, pil_image: Image.Image) -> None:
        """Display *pil_image* scaled to fit the preview area."""
        self._pil_image = pil_image.copy()

        display = self._fit(pil_image, self.MAX_WIDTH, self.MAX_HEIGHT)

        # ImageTk.PhotoImage must stay referenced or it gets garbage-collected
        self._tk_image = ImageTk.PhotoImage(display)

        self._canvas.config(
            width=display.width,
            height=display.height,
            bg="white",
        )
        self._canvas.delete("all")
        self._canvas.create_image(
            display.width // 2,
            display.height // 2,
            anchor="center",
            image=self._tk_image,
        )

        self._save_img_btn.config(state="normal")
        self._save_pdf_btn.config(state="normal")
        self._status_var.set(
            f"{pil_image.width} × {pil_image.height} px  "
            f"(displayed at {display.width} × {display.height})"
        )

    def clear(self) -> None:
        """Reset to placeholder state."""
        self._pil_image = None
        self._tk_image  = None
        self._canvas.delete("all")
        self._canvas.config(
            width=self.MAX_WIDTH,
            height=self.MAX_HEIGHT,
            bg=self.PLACEHOLDER_BG,
        )
        self._canvas.create_text(
            self.MAX_WIDTH  // 2,
            self.MAX_HEIGHT // 2,
            text=self.PLACEHOLDER_TEXT,
            fill=self.PLACEHOLDER_FG,
            font=("Helvetica", 13),
        )
        self._save_img_btn.config(state="disabled")
        self._save_pdf_btn.config(state="disabled")
        self._status_var.set("")

    def save_image(self) -> None:
        """Open a file-save dialog and write the current image to disk as PNG/JPG/BMP."""
        if self._pil_image is None:
            messagebox.showwarning("No image", "Generate a barcode first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG image",  "*.png"),
                ("JPEG image", "*.jpg"),
                ("BMP image",  "*.bmp"),
                ("All files",  "*.*"),
            ],
            title="Save barcode image",
        )
        if not path:
            return  # user cancelled

        try:
            self._pil_image.save(path)
            self._status_var.set(f"Saved → {path}")
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def save_pdf(self) -> None:
        """Export the current barcode as a single-page PDF."""
        if self._pil_image is None:
            messagebox.showwarning("No image", "Generate a barcode first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[
                ("PDF document", "*.pdf"),
                ("All files",    "*.*"),
            ],
            title="Export barcode as PDF",
        )
        if not path:
            return  # user cancelled

        try:
            from exporter import export_pdf
            export_pdf(self._pil_image, path)
            self._status_var.set(f"PDF saved → {path}")
        except Exception as exc:
            messagebox.showerror("PDF export failed", str(exc))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct child widgets."""
        # Canvas — holds the barcode image (or placeholder text)
        self._canvas = tk.Canvas(
            self,
            width=self.MAX_WIDTH,
            height=self.MAX_HEIGHT,
            bd=1,
            relief="sunken",
            highlightthickness=0,
        )
        self._canvas.pack(pady=(0, 6))

        # Bottom row: status label + action buttons
        bottom = ttk.Frame(self)
        bottom.pack(fill="x")

        self._status_var = tk.StringVar()
        ttk.Label(bottom, textvariable=self._status_var, foreground="#555555") \
            .pack(side="left")

        self._save_pdf_btn = ttk.Button(
            bottom,
            text="Download PDF…",
            command=self.save_pdf,
            state="disabled",
        )
        self._save_pdf_btn.pack(side="right", padx=(4, 0))

        self._save_img_btn = ttk.Button(
            bottom,
            text="Save Image…",
            command=self.save_image,
            state="disabled",
        )
        self._save_img_btn.pack(side="right")

        # Draw initial placeholder
        self.clear()

    @staticmethod
    def _fit(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
        """
        Return a copy of *image* scaled down (NEAREST) so it fits within
        *max_w* × *max_h*.  Never scales up.
        """
        w, h = image.size
        if w <= max_w and h <= max_h:
            return image.copy()

        ratio = min(max_w / w, max_h / h)
        new_size = (int(w * ratio), int(h * ratio))
        return image.resize(new_size, Image.NEAREST)