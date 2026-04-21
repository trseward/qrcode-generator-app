# QR Code Generator (Desktop, No Login, No Subscription)

A fast, local QR code app built for one simple reason: **generate great-looking QR codes without signups, ads, or monthly fees**.

Designed as a fun personal project, this tool runs on your machine and gives you full control over style, colors, logos, and output.

---

## Why this exists

Most online QR tools are paywalled, require accounts, or limit customization. This project keeps everything local and straightforward:

- No account required
- No data sent to third-party services
- No usage limits
- No recurring cost

---

## What the app can do

- Generate QR codes from URLs or plain text
- Choose shape/style and tune QR size
- Customize foreground/background colors
- Upload a logo overlay for branded QR codes
- Save as PNG
- Copy QR image directly to clipboard
- Toggle dark/light theme

---

## Tech stack

- Python `3.10+` (project currently tested with newer versions too)
- Tkinter UI
- `qrcode[pil]` + `Pillow`
- Optional `pywin32` for Windows clipboard image support
- PyInstaller for Windows `.exe` builds

---

## Project structure

```text
qr-code-app/
├─ main_app.py
├─ make_icon.py
├─ icon_neon.ico
├─ icon_neon.png
├─ requirements.txt
└─ scripts/
   ├─ build_exe.ps1
   └─ build_exe_with_icon.ps1
```

---

## Quick start (run Python app)

### 1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Run the app

```powershell
python .\main_app.py
```

---

## PowerShell build scripts (what they do)

### `scripts/build_exe.ps1`

Builds a **single-file, windowed** executable with embedded icon and bundled icon assets via PyInstaller.

- Input app entry: `main_app.py`
- Output executable: `dist\QR Code Generator.exe`
- Keeps build behavior focused and repeatable

Run it from repo root:

```powershell
.\scripts\build_exe.ps1
```

### `scripts/build_exe_with_icon.ps1`

Runs the full icon+build pipeline:

1. Generates/refreshes icon files by running `make_icon.py`
2. Calls `scripts/build_exe.ps1` to produce the executable

Run it from repo root:

```powershell
.\scripts\build_exe_with_icon.ps1
```

---

## Run the generated `.exe`

After a successful build:

```powershell
.\dist\"QR Code Generator.exe"
```

Or double-click `dist\QR Code Generator.exe` in File Explorer.

---

## Notes for Windows PowerShell users

If script execution is blocked on your machine, run with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_exe_with_icon.ps1
```

---

## Contributing / tweaking

This is a personal fun project, but improvements are welcome:

- UI polish
- New QR styling presets
- Additional export formats
- Better cross-platform packaging

If you fork it, make it yours and have fun.

