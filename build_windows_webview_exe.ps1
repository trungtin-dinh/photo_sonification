$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSCommandPath
Set-Location $Root

$env:PYTHONUTF8 = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

Write-Host "=== Photo Sonification Windows WebView build ==="
Write-Host "Root: $Root"

if (-not (Test-Path "desktop_launcher.py")) {
    throw "desktop_launcher.py not found. Run this script from the repository root."
}
if (-not (Test-Path "app_local.py")) {
    throw "app_local.py not found. The local desktop version is missing."
}
if (-not (Test-Path "requirements_desktop.txt")) {
    throw "requirements_desktop.txt not found."
}

Write-Host "=== Installing Python dependencies ==="
python -m pip install --upgrade pip wheel setuptools

# Windows must not install the GTK extra used on Linux.
$requirementsWindows = "requirements_windows.txt"
(Get-Content "requirements_desktop.txt") `
    -replace "pywebview\[gtk\]", "pywebview" `
    | Set-Content $requirementsWindows -Encoding UTF8

python -m pip install -r $requirementsWindows
python -m pip install pyinstaller pywebview

Write-Host "=== Cleaning previous Windows build ==="
Remove-Item -Recurse -Force "build_windows" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist\PhotoSonification" -ErrorAction SilentlyContinue
Remove-Item -Force "dist\PhotoSonification-Windows-WebView-x86_64.zip" -ErrorAction SilentlyContinue

Write-Host "=== Collecting data files ==="

$addData = New-Object System.Collections.Generic.List[string]

# Core local app files executed by Streamlit at runtime.
$coreFiles = @(
    "app_local.py",
    "ui_local.py",
    "photo_batch.py",
    "ui.py",
    "image_analysis.py",
    "composition.py",
    "audio.py",
    "config.py",
    "utils.py"
)

foreach ($file in $coreFiles) {
    if (Test-Path $file) {
        $addData.Add("$file;.")
    }
}

# Include Markdown documentation if present.
Get-ChildItem -Path . -Filter "*.md" -File -ErrorAction SilentlyContinue | ForEach-Object {
    $addData.Add("$($_.Name);.")
}

# Include optional resource folders if present.
$resourceDirs = @(
    "assets",
    "docs",
    "examples",
    "default_images",
    "soundfonts"
)

foreach ($dir in $resourceDirs) {
    if (Test-Path $dir) {
        $addData.Add("$dir;$dir")
    }
}

Write-Host "=== Building with PyInstaller ==="

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "PhotoSonification",
    "--distpath", "dist",
    "--workpath", "build_windows"
)

foreach ($entry in $addData) {
    $pyiArgs += @("--add-data", $entry)
}

# Streamlit and PyWebView use dynamic imports; these hints avoid common missing-module errors.
$hiddenImports = @(
    "streamlit.web.cli",
    "streamlit.web.bootstrap",
    "streamlit.runtime",
    "streamlit.runtime.scriptrunner",
    "webview",
    "PIL._tkinter_finder",
    "pillow_heif",
    "lameenc"
)

foreach ($importName in $hiddenImports) {
    $pyiArgs += @("--hidden-import", $importName)
}

$collectSubmodules = @(
    "streamlit",
    "altair",
    "pydeck"
)

foreach ($moduleName in $collectSubmodules) {
    $pyiArgs += @("--collect-submodules", $moduleName)
}

$pyiArgs += "desktop_launcher.py"

python -m PyInstaller @pyiArgs

$exePath = "dist\PhotoSonification\PhotoSonification.exe"
if (-not (Test-Path $exePath)) {
    throw "Windows executable was not created: $exePath"
}

Write-Host "=== Adding Windows README ==="

$readmePath = "dist\PhotoSonification\README_WINDOWS.txt"
@"
Photo Sonification - Windows WebView build

Run:
  PhotoSonification.exe

This version launches Photo Sonification in its own desktop window.
It runs a local Streamlit server on 127.0.0.1 and displays it through PyWebView.

Notes:
- The Microsoft Edge WebView2 Runtime is required.
- On most recent Windows 10/11 systems, WebView2 is already installed.
- If the window does not open, install the Microsoft Edge WebView2 Runtime and run PhotoSonification.exe again.
"@ | Set-Content $readmePath -Encoding UTF8

Write-Host "=== Creating ZIP ==="

$zipPath = "dist\PhotoSonification-Windows-WebView-x86_64.zip"
Compress-Archive -Path "dist\PhotoSonification\*" -DestinationPath $zipPath -Force

if (-not (Test-Path $zipPath)) {
    throw "ZIP was not created: $zipPath"
}

Write-Host "=== Build completed ==="
Write-Host "Executable:"
Write-Host "  $exePath"
Write-Host "ZIP:"
Write-Host "  $zipPath"
