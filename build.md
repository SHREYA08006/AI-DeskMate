# AI DeskMate — Build & Packaging Guide

This guide provides step-by-step instructions to compile, bundle, and package **AI DeskMate** into standalone executables and native installers across supported platforms.

---

## 📋 Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Windows Build Instructions](#2-windows-build-instructions)
3. [Streamlit Packaging Strategy](#3-streamlit-packaging-strategy)
4. [macOS Build Instructions (Best Effort)](#4-macos-build-instructions-best-effort)
5. [Linux Build Instructions](#5-linux-build-instructions)
6. [Testing the Build on Clean Machines](#6-testing-the-build-on-clean-machines)

---

## 1. Prerequisites

### Windows
- **Python**: 3.10+ (64-bit recommended).
- **Virtual Environment**: All dependencies from `requirements.txt` installed.
- **PyInstaller**: `pip install pyinstaller`.
- **Inno Setup 6** (Optional, for building the `.exe` installer):
  - Download and install from [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php).
  - Ensure `ISCC.exe` is added to your system `PATH` or installed at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`.

### macOS (Best Effort)
- macOS 12 (Monterey) or later.
- Python 3.10+ with Xcode Command Line Tools (`xcode-select --install`).

---

## 2. Windows Build Instructions

### Option A: Automated Build Script (Recommended)
Run the PowerShell build pipeline from the repository root:

```powershell
.\build\build_windows.ps1
```

To skip the automated test suite during rapid packaging iteration:
```powershell
.\build\build_windows.ps1 -SkipTests
```

### Option B: Manual Step-by-Step Build

1. **Verify All Tests Pass**:
   ```powershell
   .venv\Scripts\python -m unittest discover tests
   ```

2. **Compile Standalone Executable with PyInstaller**:
   ```powershell
   .venv\Scripts\pyinstaller build\deskmate.spec --noconfirm --distpath dist --workpath build\temp
   ```
   This generates the portable application folder at:
   `dist\AIDeskMate\AIDeskMate.exe`

3. **Compile the Single-File Installer (Inno Setup)**:
   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
   ```
   This produces the single setup executable:
   `dist\AI-DeskMate-Setup-1.0.0.exe`

---

## 3. Streamlit Packaging Strategy

### Chosen Approach: Single-Executable Subprocess via `launcher.py`
- **Mechanism**: The PyInstaller spec utilizes `collect_all('streamlit')` to embed Streamlit's static assets, tornado web server, jinja templates, and cli modules inside the main application bundle.
- **Process Model**: When the user clicks **"📊 Open Dashboard"** from the system tray, the application invokes a background subprocess of its own executable with the dedicated flag:
  ```bash
  AIDeskMate.exe --dashboard --port <free_port>
  ```
- **Port Allocation**: Instead of colliding on hardcoded port 8501, [`app/dashboard/launcher.py`](file:///C:/Users/HIND/.gemini/antigravity/scratch/ai-deskmate/app/dashboard/launcher.py) queries the operating system kernel for an available ephemeral port on `127.0.0.1` and binds exclusively to localhost.
- **Why this was chosen over an embedded Python environment**:
  1. **Binary footprint**: Bundling an external embedded Python folder duplicates the entire standard library and C-runtime, bloating the distribution by 80–120MB.
  2. **Clean updates**: Having one runtime ensures that packages like `scikit-learn`, `pandas`, and `customtkinter` share binary versions with no path desynchronization.

### Documented Fallback: Bundled Embedded Python
If a locked-down enterprise Windows environment or security software restricts PyInstaller subprocess bootstrapping:
1. Download `python-3.10.x-embed-amd64.zip` from python.org.
2. Unpack into `python_runtime/` inside the application folder.
3. Install wheels for `streamlit`, `pandas`, `plotly` directly into `python_runtime/Lib/site-packages`.
4. In [`app/ui/tray.py`](file:///C:/Users/HIND/.gemini/antigravity/scratch/ai-deskmate/app/ui/tray.py), launch `python_runtime\python.exe -m streamlit run app/dashboard/dashboard.py`.

---

## 4. macOS Build Instructions (Best Effort)

> ⚠️ **Note**: macOS packaging is provided as best-effort scripts. Primary QA was performed on Windows. Verification on an actual macOS machine is required before release.

1. Ensure permissions and virtual environment:
   ```bash
   chmod +x build/build_macos.sh
   ./build/build_macos.sh
   ```
2. **Required macOS System Permissions**:
   - **Accessibility** (`System Settings > Privacy & Security > Accessibility`): Required by `pynput` for keyboard and mouse activity counting.
   - **Input Monitoring** (`System Settings > Privacy & Security > Input Monitoring`): Required on macOS Catalina+ to monitor background keystrokes.
   - **Screen Recording** (`System Settings > Privacy & Security > Screen Recording`): Required to retrieve active frontmost window titles.

---

## 5. Linux Build Instructions

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt update && sudo apt install -y python3-tk libx11-dev libxtst-dev

# Build via PyInstaller
python3 -m pyinstaller build/deskmate.spec --noconfirm --distpath dist
```

---

## 6. Testing the Build on Clean Machines

1. Copy `dist\AI-DeskMate-Setup-1.0.0.exe` to a fresh Windows 10/11 machine or VM that does **not** have Python installed.
2. Run the installer:
   - Verify installation into `%ProgramFiles%\AI DeskMate` (or per-user directory).
   - Verify Start Menu shortcut and Desktop icon creation.
3. Launch AI DeskMate:
   - Confirm first-run onboarding wizard appears.
   - Select avatar and save.
   - Confirm floating corner overlay and system tray icon appear.
4. Test Demo Mode:
   - Run `AIDeskMate.exe --demo` or open tray menu in demo mode.
   - Click "Open Dashboard" to confirm Streamlit opens on a dynamic port with the synthetic badge.
5. Uninstall:
   - Run uninstaller from Windows "Installed Apps".
   - Confirm dialog prompts whether to keep or delete user wellness history in `%APPDATA%\AI DeskMate`.
