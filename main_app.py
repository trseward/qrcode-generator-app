import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
import qrcode
from qrcode.constants import (
    ERROR_CORRECT_H,
)
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
)
from qrcode.image.styles.colormasks import SolidFillColorMask
import io
import sys
import json
import os
import subprocess
from typing import TypedDict, Literal, TypeAlias
import ctypes

APP_USER_MODEL_ID = "TaNeisha.QRCodeGenerator.2.0"

# Must be called before tk.Tk() is created.
# Bump APP_USER_MODEL_ID when changing branding/icon to avoid stale taskbar cache grouping.
if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        APP_USER_MODEL_ID
    )


# ---------------------------------------------------------------------------
# Platform-aware clipboard helper
# ---------------------------------------------------------------------------

def copy_image_to_clipboard(pil_image: Image.Image) -> bool:
    """Copy a PIL image to the system clipboard as an actual image."""
    platform = sys.platform
    try:
        if platform == "win32":
            import win32clipboard
            import win32con
            output = io.BytesIO()
            pil_image.convert("RGB").save(output, "BMP")
            bmp_data = output.getvalue()[14:]          # strip BMP file header
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_DIB, bmp_data)
            win32clipboard.CloseClipboard()
            return True
        elif platform == "darwin":
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            proc = subprocess.Popen(
                ["osascript", "-e",
                 'set the clipboard to (read (POSIX file "/dev/stdin") as PNG picture)'],
                stdin=subprocess.PIPE,
            )
            proc.communicate(input=buf.getvalue())
            return proc.returncode == 0
        else:
            # Linux – try xclip then xsel
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            for cmd in (
                ["xclip", "-selection", "clipboard", "-t", "image/png"],
                ["xsel", "--clipboard", "--input"],
            ):
                try:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    proc.communicate(input=buf.getvalue())
                    if proc.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Preferences file (recent URLs)
# ---------------------------------------------------------------------------

PREFS_FILE = os.path.join(os.path.expanduser("~"), ".qr_generator_prefs.json")
MAX_RECENT = 5


class PrefsDict(TypedDict):
    recent_urls: list[str]


def load_prefs() -> PrefsDict:
    """Load saved preferences from disk, returning defaults on failure."""
    try:
        with open(PREFS_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"recent_urls": []}


def save_prefs(prefs: PrefsDict) -> None:
    """Persist preferences to disk; fail silently to keep the UI responsive."""
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class PackPadding(TypedDict, total=False):
    padx: int | tuple[int, int]
    pady: int | tuple[int, int]


PADDING: PackPadding = {"padx": 4, "pady": 6}
LEFT_PANEL_WIDTH = 360
FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else ("Helvetica" if sys.platform == "darwin" else "DejaVu Sans")
ButtonState: TypeAlias = Literal["normal", "active", "disabled"]

# Type alias for RGB color tuples
RGB: TypeAlias = tuple[int, int, int]

def _hex_to_rgb(hex_color: str) -> RGB:
    """Convert a hex color string like '#ff0000' to an (R, G, B) integer tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


class QRApp:
    def __init__(self, root: tk.Tk) -> None:
        """Initialize application state, widgets, bindings, and theme."""
        self.root = root
        self.root.title("QR Code Generator")
        self.root.geometry("960x660")
        self.root.minsize(900, 520)

        # ---- state ----
        self.theme: Literal["dark", "light"] = "dark"
        self.themes: dict[str, dict[str, str]] = {
            "dark": {
                "bg": "#1e1e1e",
                "fg": "white",
                "entry_bg": "#2d2d2d",
                "entry_fg": "white",
                "button_bg": "#3a3a3a",
                "button_fg": "white",
                "accent_bg": "#007acc",
                "accent_fg": "white",
                "placeholder_fg": "#666666",
                "warn_fg": "#ff6b6b",
                "swatch_border": "#555555",
            },
            "light": {
                "bg": "#f4f4f4",
                "fg": "#1a1a1a",
                "entry_bg": "white",
                "entry_fg": "#1a1a1a",
                "button_bg": "#e0e0e0",
                "button_fg": "#1a1a1a",
                "accent_bg": "#007acc",
                "accent_fg": "white",
                "placeholder_fg": "#999999",
                "warn_fg": "#c0392b",
                "swatch_border": "#aaaaaa",
            },
        }

        # Declare color attributes for static type checkers
        self._fg_rgb: RGB = (0, 0, 0)
        self._bg_qr_rgb: RGB = (255, 255, 255)

        self.qr_image: Image.Image | None = None
        self._qr_preview_tk: ImageTk.PhotoImage | None = None
        self.logo_path: str | None = None
        self.logo_preview_img: ImageTk.PhotoImage | None = None
        self.prefs: PrefsDict = load_prefs()

        # widget registries for theme updates
        self._labels: list[tk.Label] = []
        self._buttons: list[tk.Button] = []
        self._frames: list[tk.Frame] = []
        self._radios: list[tk.Radiobutton] = []

        self._build_layout()
        self._build_left_ui()
        self._build_right_ui()
        self._bind_shortcuts()
        self.apply_theme()

    # ------------------------------------------------------------------
    # Layout scaffolding
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Create the two-column outer layout with a scrollable left panel."""
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0, minsize=LEFT_PANEL_WIDTH)
        self.root.grid_columnconfigure(1, weight=1, minsize=420)

        # --- scrollable left column ---
        left_outer = tk.Frame(self.root)
        left_outer.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        self._frames.append(left_outer)

        self._canvas = tk.Canvas(left_outer, width=LEFT_PANEL_WIDTH, highlightthickness=0)
        self._scrollbar = tk.Scrollbar(left_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.left_frame = tk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window((0, 0), window=self.left_frame, anchor="nw")

        self.left_frame.bind("<Configure>", self._on_left_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        # Scope wheel handling to the left panel area only.
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.left_frame.bind("<MouseWheel>", self._on_mousewheel)

        # --- right column ---
        self.right_frame = tk.Frame(self.root)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        self._frames.append(self.right_frame)

    def _on_left_frame_configure(self, _event=None) -> None:
        """Update canvas scroll region when the left frame size changes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        """Keep the embedded left frame width synced to the canvas width."""
        self._canvas.itemconfig(self._canvas_window, width=max(event.width, LEFT_PANEL_WIDTH))

    def _on_mousewheel(self, event: tk.Event) -> None:
        """Scroll the left panel using the mouse wheel."""
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    # Left panel UI
    # ------------------------------------------------------------------

    def _build_left_ui(self) -> None:
        """Build controls for content, colors, shape, size, logo, and actions."""
        lf = self.left_frame
        PAD: PackPadding = PADDING

        # ---- URL / data input ----
        self._add_section_label(lf, "Content")

        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)

        self.url_combo = ttk.Combobox(
            lf,
            textvariable=self.url_var,
            values=self.prefs.get("recent_urls", []),
            font=(FONT_FAMILY, 11),
            width=40,
        )
        self.url_combo.pack(anchor="w", **PAD)
        self.url_combo.bind("<<ComboboxSelected>>", lambda _: self._validate_url())

        self.url_warn_label = tk.Label(lf, text="", font=(FONT_FAMILY, 9))
        self.url_warn_label.pack(anchor="w", padx=4)
        self._labels.append(self.url_warn_label)

        # ---- Colors ----
        self._add_section_label(lf, "Colors")

        fg_frame = tk.Frame(lf)
        fg_frame.pack(anchor="w", **PAD)
        self._frames.append(fg_frame)
        self._make_color_row(fg_frame, "Foreground", initial="#000000", attr="fg")

        bg_frame = tk.Frame(lf)
        bg_frame.pack(anchor="w", **PAD)
        self._frames.append(bg_frame)
        self._make_color_row(bg_frame, "Background", initial="#ffffff", attr="bg_qr")

        # ---- Shape ----
        self._add_section_label(lf, "Module Shape")

        self.shape_var = tk.StringVar(value="square")
        shape_frame = tk.Frame(lf)
        shape_frame.pack(anchor="w", fill="x", **PAD)
        self._frames.append(shape_frame)

        shape_frame.grid_columnconfigure(0, weight=1)
        shape_frame.grid_columnconfigure(1, weight=1)
        shape_frame.grid_columnconfigure(2, weight=1)

        for i, (shape, label) in enumerate(
            [("square", "■  Square"), ("rounded", "◉  Rounded"), ("dots", "•  Dots")]
        ):
            rb = tk.Radiobutton(
                shape_frame,
                text=label,
                variable=self.shape_var,
                value=shape,
                font=(FONT_FAMILY, 10),
                indicatoron=True,
                anchor="w",
                justify="left",
            )
            rb.grid(row=0, column=i, sticky="w", padx=(0, 8))
            self._radios.append(rb)

        # ---- Size ----
        self._add_section_label(lf, "Output Size (100 – 2000 px)")

        size_frame = tk.Frame(lf)
        size_frame.pack(anchor="w", **PAD)
        self._frames.append(size_frame)

        self.size_var = tk.IntVar(value=300)
        self.size_slider = tk.Scale(
            size_frame,
            from_=100,
            to=2000,
            orient="horizontal",
            variable=self.size_var,
            length=200,
            resolution=10,
            showvalue=False,
            command=self._on_size_slider,
        )
        self.size_slider.pack(side="left")

        self.size_display = tk.Label(size_frame, text="300 px", width=7, font=(FONT_FAMILY, 10))
        self.size_display.pack(side="left", padx=6)
        self._labels.append(self.size_display)

        # ---- Logo ----
        self._add_section_label(lf, "Logo (optional)")

        logo_btn_frame = tk.Frame(lf)
        logo_btn_frame.pack(anchor="w", **PAD)
        self._frames.append(logo_btn_frame)

        self.logo_btn = tk.Button(logo_btn_frame, text="Upload Logo", command=self._load_logo, width=14)
        self.logo_btn.pack(side="left")
        self._buttons.append(self.logo_btn)

        self.logo_clear_btn = tk.Button(
            logo_btn_frame, text="✕ Remove", command=self._clear_logo, width=10, state="disabled"
        )
        self.logo_clear_btn.pack(side="left", padx=6)
        self._buttons.append(self.logo_clear_btn)

        self.logo_preview = tk.Label(lf)
        self.logo_preview.pack(anchor="w", padx=4, pady=2)
        self._labels.append(self.logo_preview)

        # ---- Status bar ----
        self.status_label = tk.Label(lf, text="", font=(FONT_FAMILY, 9), anchor="w")
        self.status_label.pack(anchor="w", padx=4, pady=(4, 0))
        self._labels.append(self.status_label)

        # ---- Action buttons ----
        self._add_section_label(lf, "Actions")

        self.generate_btn = tk.Button(
            lf,
            text="⚡  Generate QR  (Ctrl+G)",
            command=self.generate_qr,
            font=(FONT_FAMILY, 11, "bold"),
            width=24,
        )
        self.generate_btn.pack(anchor="w", pady=(4, 8), padx=4)
        self._buttons.append(self.generate_btn)

        self.save_btn = tk.Button(
            lf, text="💾  Save PNG  (Ctrl+S)", command=self.save_qr, width=24, state="disabled"
        )
        self.save_btn.pack(anchor="w", **PAD)
        self._buttons.append(self.save_btn)

        self.copy_btn = tk.Button(
            lf, text="📋  Copy to Clipboard", command=self.copy_to_clipboard, width=24, state="disabled"
        )
        self.copy_btn.pack(anchor="w", **PAD)
        self._buttons.append(self.copy_btn)

        self.open_btn = tk.Button(
            lf, text="🔍  Open in Viewer", command=self.open_in_viewer, width=24, state="disabled"
        )
        self.open_btn.pack(anchor="w", **PAD)
        self._buttons.append(self.open_btn)

        self.clear_btn = tk.Button(lf, text="🗑  Clear All", command=self.clear_all, width=24)
        self.clear_btn.pack(anchor="w", pady=(8, 4), padx=4)
        self._buttons.append(self.clear_btn)

        # ---- Theme toggle (bottom of left panel) ----
        self.theme_toggle_btn = tk.Button(
            lf,
            text="🌙  Dark mode",
            command=self.toggle_theme,
            borderwidth=1,
            relief="groove",
            font=(FONT_FAMILY, 9),
            width=24,
        )
        self.theme_toggle_btn.pack(anchor="w", pady=(16, 4), padx=4)
        self._buttons.append(self.theme_toggle_btn)

    # ------------------------------------------------------------------
    # Right panel UI
    # ------------------------------------------------------------------

    def _build_right_ui(self) -> None:
        """Build the preview panel used to display generated QR images."""
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # Border container for the QR preview
        self.qr_container = tk.Frame(self.right_frame, bd=2, relief="groove")
        self.qr_container.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._frames.append(self.qr_container)

        self.qr_placeholder = tk.Label(
            self.qr_container,
            text="Your QR code will appear here",
            font=(FONT_FAMILY, 13),
            justify="center",
        )
        self.qr_placeholder.pack(expand=True)
        self._labels.append(self.qr_placeholder)

        self.qr_label = tk.Label(self.qr_container)
        # qr_label is packed when an image is ready

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_section_label(self, parent: tk.Frame, text: str) -> None:
        """Add a small section heading to the left panel."""
        lbl = tk.Label(parent, text=text.upper(), font=(FONT_FAMILY, 8, "bold"), anchor="w")
        lbl.pack(anchor="w", padx=4, pady=(12, 2))
        self._labels.append(lbl)

    def _make_color_row(self, parent: tk.Frame, label_text: str, initial: str, attr: str) -> None:
        """Create a color picker row and bind it to a dynamic color attribute."""
        lbl = tk.Label(parent, text=f"{label_text}:", font=(FONT_FAMILY, 10), width=12, anchor="w")
        lbl.pack(side="left")
        self._labels.append(lbl)

        swatch = tk.Label(parent, bg=initial, width=4, height=1, relief="solid", bd=1)
        swatch.pack(side="left", padx=4)

        hex_lbl = tk.Label(parent, text=initial, font=(FONT_FAMILY, 9), width=8)
        hex_lbl.pack(side="left", padx=2)
        self._labels.append(hex_lbl)

        btn = tk.Button(
            parent,
            text="Choose",
            command=lambda a=attr, s=swatch, h=hex_lbl: self._pick_color(a, s, h),
            font=(FONT_FAMILY, 9),
        )
        btn.pack(side="left", padx=4)
        self._buttons.append(btn)

        setattr(self, f"_{attr}_color", initial)
        setattr(self, f"_{attr}_rgb", _hex_to_rgb(initial))
        setattr(self, f"_{attr}_swatch", swatch)
        setattr(self, f"_{attr}_hex_lbl", hex_lbl)

    def _pick_color(self, attr: str, swatch: tk.Label, hex_lbl: tk.Label) -> None:
        """Open a color chooser and store both hex and RGB representations."""
        current = getattr(self, f"_{attr}_color")
        result = colorchooser.askcolor(color=current)
        if result and result[1] is not None:
            hex_color: str = result[1]
            rgb: RGB = _hex_to_rgb(hex_color)
            setattr(self, f"_{attr}_color", hex_color)
            setattr(self, f"_{attr}_rgb", rgb)
            swatch.config(bg=hex_color)
            hex_lbl.config(text=hex_color)

    def _on_size_slider(self, _val: str | None = None) -> None:
        """Reflect the current slider value beside the size control."""
        self.size_display.config(text=f"{self.size_var.get()} px")

    def _on_url_change(self, _var_name: str, _index: str, _mode: str) -> None:
        """Validate the URL/content field as the user types."""
        self._validate_url(silent=True)

    def _validate_url(self, silent: bool = False) -> bool:
        """Return True if the content field looks encodable; show a warning if not."""
        url = self.url_var.get().strip()
        t = self.themes[self.theme]

        if not url:
            self.url_warn_label.config(text="")
            return False

        # lightweight check – must look like a URI or non-empty text
        is_plausible = (
            url.startswith(("http://", "https://", "mailto:", "tel:", "sms:"))
            or "." in url
            or len(url) >= 3
        )

        if not is_plausible and not silent:
            self.url_warn_label.config(text="⚠ May not be a valid URL", fg=t["warn_fg"])
            return False

        self.url_warn_label.config(text="")
        return True

    def _set_output_buttons_state(self, state: ButtonState) -> None:
        """Enable or disable Save/Copy/Open output actions together."""
        for btn in (self.save_btn, self.copy_btn, self.open_btn):
            btn.config(state=state)

    def _set_status(self, msg: str) -> None:
        """Update the status line and flush pending UI redraws."""
        self.status_label.config(text=msg)
        self.root.update_idletasks()

    # ------------------------------------------------------------------
    # Logo handling
    # ------------------------------------------------------------------

    def _load_logo(self) -> None:
        """Select a logo file, create its preview, and enable logo removal."""
        path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if path:
            try:
                logo = Image.open(path)
                logo.thumbnail((64, 64))
                self.logo_preview_img = ImageTk.PhotoImage(logo)
                self.logo_preview.config(image=self.logo_preview_img)
                self.logo_path = path
                self.logo_clear_btn.config(state="normal")
            except (FileNotFoundError, OSError, UnidentifiedImageError):
                messagebox.showerror("Invalid Logo", "Could not open that image file.")

    def _clear_logo(self) -> None:
        """Remove the current logo and clear the preview thumbnail."""
        self.logo_path = None
        self.logo_preview.config(image="")
        self.logo_preview_img = None
        self.logo_clear_btn.config(state="disabled")

    # ------------------------------------------------------------------
    # QR generation
    # ------------------------------------------------------------------

    def _module_drawer_for_shape(self, shape: str):
        return {
            "square": SquareModuleDrawer(),
            "rounded": RoundedModuleDrawer(),
            "dots": CircleModuleDrawer(),
        }.get(shape, SquareModuleDrawer())

    def _build_qr_image(self, content: str, size: int, shape: str) -> Image.Image:
        """Build a styled QR image using current color and logo settings."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(content)
        qr.make(fit=True)

        # Render styled modules in a stable neutral palette, then map grayscale to user colors.
        # This avoids a StyledPilImage/SolidFillColorMask collapse observed with pure-black backgrounds.
        qr_base = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=self._module_drawer_for_shape(shape),
            color_mask=SolidFillColorMask(
                front_color=(0, 0, 0),
                back_color=(255, 255, 255),
            ),
        ).convert("RGB")
        qr_img = ImageOps.colorize(
            qr_base.convert("L"),
            black=self._fg_rgb,
            white=self._bg_qr_rgb,
        ).convert("RGB")
        qr_img = qr_img.resize((size, size), resample=Image.Resampling.LANCZOS)

        if self.logo_path:
            logo = Image.open(self.logo_path).convert("RGBA")
            logo_size = size // 5
            logo = logo.resize((logo_size, logo_size), resample=Image.Resampling.LANCZOS)
            pos = ((size - logo_size) // 2, (size - logo_size) // 2)
            qr_img.paste(logo, pos, mask=logo)

        return qr_img.convert("RGB")

    def generate_qr(self) -> None:
        """Generate a styled QR image from current inputs and update the preview."""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL or text to encode.")
            return

        size = self.size_var.get()
        shape = self.shape_var.get()

        self._set_status("Generating…")
        self.generate_btn.config(state="disabled")
        self.root.update_idletasks()

        try:
            self.qr_image = self._build_qr_image(url, size, shape)

            # scale preview to fit the right panel
            max_preview = min(self.right_frame.winfo_width(), self.right_frame.winfo_height(), 520)
            max_preview = max(max_preview, 240)
            preview = self.qr_image.copy()
            preview.thumbnail((max_preview, max_preview), resample=Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(preview)

            self.qr_placeholder.pack_forget()
            self._qr_preview_tk = img_tk
            self.qr_label.config(image=self._qr_preview_tk)
            self.qr_label.pack(expand=True)

            self._set_output_buttons_state("normal")
            self._set_status(f"✓ Generated {size}×{size} px QR code.")

            # update recent URLs
            recents: list[str] = self.prefs.get("recent_urls", [])
            if url in recents:
                recents.remove(url)
            recents.insert(0, url)
            self.prefs["recent_urls"] = recents[:MAX_RECENT]
            self.url_combo["values"] = self.prefs["recent_urls"]
            save_prefs(self.prefs)

        except Exception as exc:
            messagebox.showerror("Generation Failed", str(exc))
            self._set_status("Error during generation.")
        finally:
            self.generate_btn.config(state="normal")

    # ------------------------------------------------------------------
    # Output actions
    # ------------------------------------------------------------------

    def save_qr(self) -> None:
        """Save the generated QR image to a user-selected file."""
        if not self.qr_image:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg")],
        )
        if path:
            self.qr_image.save(path)
            self._set_status(f"✓ Saved to {os.path.basename(path)}")

    def copy_to_clipboard(self) -> None:
        """Copy the generated QR image to the system clipboard."""
        if not self.qr_image:
            return
        self._set_status("Copying…")
        self.root.update_idletasks()
        ok = copy_image_to_clipboard(self.qr_image)
        if ok:
            self._set_status("✓ Image copied to clipboard.")
        else:
            self._set_status("⚠ Clipboard copy failed on this platform.")
            messagebox.showwarning(
                "Clipboard",
                "Could not copy as an image on this platform.\n"
                "Try saving the file instead.",
            )

    def open_in_viewer(self) -> None:
        """Open the generated QR image in the default system image viewer."""
        if not self.qr_image:
            return
        self.qr_image.show()
        self._set_status("Opened in system viewer.")

    def clear_all(self) -> None:
        """Reset content, output preview, and logo while keeping theme/settings."""
        self.url_var.set("")
        self.url_warn_label.config(text="")
        self.qr_label.pack_forget()
        self.qr_label.config(image="")
        self._qr_preview_tk = None
        self.qr_image = None
        self._clear_logo()
        self.qr_placeholder.pack(expand=True)
        self._set_output_buttons_state("disabled")
        self._set_status("")

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        """Register keyboard shortcuts for generate and save actions."""
        self.root.bind("<Control-g>", lambda _: self.generate_qr())
        self.root.bind("<Control-G>", lambda _: self.generate_qr())
        self.root.bind("<Control-s>", lambda _: self.save_qr())
        self.root.bind("<Control-S>", lambda _: self.save_qr())

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def apply_theme(self) -> None:
        """Apply the active theme colors to all tracked widgets."""
        t = self.themes[self.theme]

        self.root.configure(bg=t["bg"])
        self._canvas.configure(bg=t["bg"])
        self._scrollbar.configure(bg=t["bg"])

        for f in self._frames:
            f.configure(bg=t["bg"])

        self.left_frame.configure(bg=t["bg"])
        self.qr_container.configure(bg=t["bg"])

        for lbl in self._labels:
            lbl.configure(bg=t["bg"], fg=t["fg"])

        # warn label keeps its own color logic
        self.url_warn_label.configure(bg=t["bg"])
        self.qr_placeholder.configure(bg=t["bg"], fg=t["placeholder_fg"])

        for btn in self._buttons:
            if btn is self.generate_btn:
                btn.configure(bg=t["accent_bg"], fg=t["accent_fg"],
                               activebackground=t["accent_bg"], activeforeground=t["accent_fg"])
            else:
                btn.configure(bg=t["button_bg"], fg=t["button_fg"],
                               activebackground=t["bg"], activeforeground=t["fg"])

        self.theme_toggle_btn.configure(
            text="🌙  Dark mode" if self.theme == "dark" else "☀️  Light mode"
        )

        for rb in self._radios:
            rb.configure(
                bg=t["bg"],
                fg=t["fg"],
                selectcolor=t["bg"],
                activebackground=t["bg"],
                activeforeground=t["fg"],
            )

        # Combobox via ttk style
        style = ttk.Style()
        style.configure(
            "TCombobox",
            fieldbackground=t["entry_bg"],
            background=t["button_bg"],
            foreground=t["entry_fg"],
            selectbackground=t["accent_bg"],
            selectforeground=t["accent_fg"],
        )

        self.size_slider.configure(
            bg=t["bg"],
            fg=t["fg"],
            troughcolor=t["entry_bg"],
            activebackground=t["accent_bg"],
            highlightbackground=t["bg"],
        )
        self.size_display.configure(bg=t["bg"], fg=t["fg"])

        # Refresh color swatches with border
        for attr in ("fg", "bg_qr"):
            swatch = getattr(self, f"_{attr}_swatch", None)
            if isinstance(swatch, tk.Label):
                swatch.configure(highlightbackground=t["swatch_border"], highlightthickness=1)

        self.qr_label.configure(bg=t["bg"])

    def toggle_theme(self) -> None:
        """Switch between dark and light themes."""
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()


# ---------------------------------------------------------------------------
TaskbarIconImage: TypeAlias = tk.PhotoImage | ImageTk.PhotoImage
_TASKBAR_ICONS: list[TaskbarIconImage] = []


def _icon_search_dirs() -> list[str]:
    """Return candidate directories where icon assets may exist."""
    if getattr(sys, "frozen", False):
        dirs: list[str] = []
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if isinstance(bundle_dir, str):
            dirs.append(bundle_dir)
        dirs.append(os.path.dirname(sys.executable))
        return dirs
    return [os.path.dirname(os.path.abspath(__file__))]


def _find_icon_file(filename: str) -> str | None:
    """Find the first existing icon file in known runtime locations."""
    for directory in _icon_search_dirs():
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    return None


if __name__ == "__main__":
    root = tk.Tk()

    ico_icon_path = _find_icon_file("icon_neon.ico")
    png_icon_path = _find_icon_file("icon_neon.png")

    if ico_icon_path:
        try:
            root.iconbitmap(ico_icon_path)
        except tk.TclError:
            pass

    # Prefer PNG for wm_iconphoto since tk.PhotoImage handles PNG reliably on Windows.
    if png_icon_path:
        try:
            photo = tk.PhotoImage(file=png_icon_path)
            root.wm_iconphoto(True, photo)
            _TASKBAR_ICONS[:] = [photo]  # prevent garbage collection
        except tk.TclError:
            pass
    elif ico_icon_path:
        # Fallback: convert ICO frames through PIL when PNG is unavailable.
        try:
            icon_img = Image.open(ico_icon_path).convert("RGBA")
            photos: list[ImageTk.PhotoImage] = [
                ImageTk.PhotoImage(icon_img.copy().resize((s, s), Image.Resampling.LANCZOS))
                for s in (16, 32, 48, 64)
            ]
            root.wm_iconphoto(True, *photos)  # type: ignore[arg-type]
            _TASKBAR_ICONS[:] = photos  # prevent garbage collection
        except Exception:
            # Do not block app startup if icon conversion fails in a bundled build.
            pass

    app = QRApp(root)
    root.mainloop()