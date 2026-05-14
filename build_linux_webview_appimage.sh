#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PhotoSonification"
APP_ID="photo-sonification"
APPIMAGE_NAME="PhotoSonification-Linux-WebView-x86_64.AppImage"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." >/dev/null 2>&1 && pwd)"

# If this script is copied directly to the repo root, fix ROOT.
if [[ ! -f "$ROOT/app_local.py" && -f "$(pwd)/app_local.py" ]]; then
  ROOT="$(pwd)"
fi

cd "$ROOT"

if [[ ! -f "app_local.py" ]]; then
  echo "ERROR: app_local.py not found. Run this script from the photo_sonification repo root or from build/." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required." >&2
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import gi
PY
then
  cat >&2 <<'EOF'
ERROR: Python GTK bindings are missing.
Install them first on Ubuntu 24.04 with:

sudo apt update
sudo apt install -y \
  python3-venv python3-gi python3-gi-cairo \
  gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
  libwebkit2gtk-4.1-0
EOF
  exit 1
fi

mkdir -p dist build
rm -rf "build/${APP_NAME}.AppDir" "dist/${APPIMAGE_NAME}"
APPDIR="build/${APP_NAME}.AppDir"
mkdir -p "$APPDIR/usr/app" "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Create a relocatable-enough venv for this AppDir. We use system-site-packages
# intentionally so GTK/WebKitGTK bindings from apt remain available.
python3 -m venv --system-site-packages --copies "$APPDIR/usr/venv"
"$APPDIR/usr/venv/bin/python" -m pip install --upgrade pip wheel setuptools

REQ_TMP="build/requirements_appimage_webview.txt"
python3 - <<'PY'
from pathlib import Path
src = Path('requirements_desktop.txt') if Path('requirements_desktop.txt').exists() else Path('requirements.txt')
lines = []
if src.exists():
    for raw in src.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # Gradio is not needed for the local desktop Streamlit app.
        if line.lower().startswith('gradio'):
            continue
        if line.lower().startswith('pyinstaller'):
            continue
        if line.lower().startswith('pywebview'):
            continue
        lines.append(line)
# Minimum dependencies for the local desktop version.
needed = [
    'streamlit',
    'numpy',
    'pillow',
    'pillow-heif',
    'matplotlib',
    'lameenc',
    'pywebview',
]
existing = '\n'.join(lines).lower()
for dep in needed:
    name = dep.split('[')[0].split('=')[0].split('<')[0].split('>')[0].lower()
    if name not in existing:
        lines.append(dep)
Path('build/requirements_appimage_webview.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
PY

"$APPDIR/usr/venv/bin/python" -m pip install -r "$REQ_TMP"

# Copy project files. Exclude build artifacts and environments.
if command -v rsync >/dev/null 2>&1; then
  rsync -a ./ "$APPDIR/usr/app/" \
    --exclude '.git' \
    --exclude '.venv*' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'build' \
    --exclude 'dist'
else
  cp -a . "$APPDIR/usr/app"
  rm -rf "$APPDIR/usr/app/.git" "$APPDIR/usr/app/build" "$APPDIR/usr/app/dist" "$APPDIR/usr/app/.venv"* || true
fi

cat > "$APPDIR/usr/app/desktop_launcher_webview.py" <<'PY'
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def _find_free_port(start: int = 8501, end: int = 8599) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free local port found between 8501 and 8599.")


def _wait_until_ready(port: int, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError("Streamlit did not start in time.")


def main() -> int:
    app_dir = Path(__file__).resolve().parent
    app_path = app_dir / "app_local.py"
    if not app_path.exists():
        raise FileNotFoundError(f"Cannot find app_local.py at: {app_path}")

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    env["PYTHONNOUSERSITE"] = "0"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(app_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        _wait_until_ready(port)

        import webview

        webview.create_window(
            title="Photo Sonification",
            url=url,
            width=1280,
            height=850,
            min_size=(1000, 700),
            text_select=True,
        )
        webview.start(gui="gtk", debug=False)
        return 0
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
PY

cat > "$APPDIR/AppRun" <<'SH2'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
export PYTHONNOUSERSITE=0
export STREAMLIT_GLOBAL_DEVELOPMENT_MODE=false
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_FILE_WATCHER_TYPE=none
cd "$HERE/usr/app"
exec "$HERE/usr/venv/bin/python" "$HERE/usr/app/desktop_launcher_webview.py"
SH2
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/${APP_ID}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Photo Sonification
Comment=Local desktop version of Photo Sonification
Exec=PhotoSonification
Icon=${APP_ID}
Categories=AudioVideo;Audio;Education;
Terminal=false
EOF
cp "$APPDIR/${APP_ID}.desktop" "$APPDIR/usr/share/applications/${APP_ID}.desktop"

# Simple generated icon.
python3 - <<'PY'
from pathlib import Path
try:
    from PIL import Image, ImageDraw
except Exception:
    raise SystemExit(0)
out = Path('build/PhotoSonification.AppDir/usr/share/icons/hicolor/256x256/apps/photo-sonification.png')
out.parent.mkdir(parents=True, exist_ok=True)
img = Image.new('RGB', (256, 256), (28, 35, 49))
d = ImageDraw.Draw(img)
d.ellipse((38, 38, 218, 218), outline=(98, 180, 255), width=10)
d.rectangle((72, 88, 184, 166), outline=(255, 212, 98), width=8)
for x, h in [(86, 22), (110, 48), (134, 72), (158, 40)]:
    d.line((x, 182, x, 182-h), fill=(172, 255, 170), width=8)
img.save(out)
PY
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP_ID}.png" "$APPDIR/${APP_ID}.png"

# Quick sanity test before AppImage packaging.
"$APPDIR/AppRun" --help >/dev/null 2>&1 || true

APPIMAGETOOL=""
if command -v appimagetool >/dev/null 2>&1; then
  APPIMAGETOOL="$(command -v appimagetool)"
elif [[ -x "build/appimagetool-x86_64.AppImage" ]]; then
  APPIMAGETOOL="build/appimagetool-x86_64.AppImage"
elif [[ -x "build/appimagetool" ]]; then
  APPIMAGETOOL="build/appimagetool"
else
  echo "appimagetool not found. Downloading it to build/appimagetool-x86_64.AppImage ..."
  if command -v wget >/dev/null 2>&1; then
    wget -O build/appimagetool-x86_64.AppImage "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  elif command -v curl >/dev/null 2>&1; then
    curl -L -o build/appimagetool-x86_64.AppImage "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  else
    echo "ERROR: install appimagetool, wget, or curl." >&2
    exit 1
  fi
  chmod +x build/appimagetool-x86_64.AppImage
  APPIMAGETOOL="build/appimagetool-x86_64.AppImage"
fi

ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "dist/${APPIMAGE_NAME}"
chmod +x "dist/${APPIMAGE_NAME}"

echo ""
echo "Built: dist/${APPIMAGE_NAME}"
echo "Run it with:"
echo "  ./dist/${APPIMAGE_NAME}"
echo ""
echo "This version opens a dedicated PyWebView/WebKitGTK window, not your default browser."
