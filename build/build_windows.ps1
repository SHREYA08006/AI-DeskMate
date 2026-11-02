# build/build_windows.ps1 - Automated Windows Build & Installer Script for AI DeskMate
param(
    [switch]$SkipTests = $false,
    [switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   AI DESKMATE -- WINDOWS PACKAGING & BUILD PIPELINE      " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Read Version
$VersionFile = Join-Path $ProjectDir "VERSION"
$AppVersion = if (Test-Path $VersionFile) { (Get-Content $VersionFile).Trim() } else { "1.0.0" }
Write-Host "[1/4] App Version: $AppVersion" -ForegroundColor Green

# Detect Python and PyInstaller executables
$PythonExe = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
$PyinstallerExe = if (Test-Path ".\.venv\Scripts\pyinstaller.exe") { ".\.venv\Scripts\pyinstaller.exe" } elseif (Get-Command pyinstaller -ErrorAction SilentlyContinue) { "pyinstaller" } else { "$PythonExe -m PyInstaller" }

# 2. Run Test Suite
if (-not $SkipTests) {
    Write-Host "[2/4] Running automated test suite before building using $PythonExe..." -ForegroundColor Yellow
    & $PythonExe -m unittest tests.test_phase9
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Phase 9 tests failed. Aborting build."
        exit 1
    }
    Write-Host "Tests passed successfully." -ForegroundColor Green
} else {
    Write-Host "[2/4] Skipping tests (-SkipTests specified)." -ForegroundColor Gray
}

# 3. Build Standalone PyInstaller Package
Write-Host "[3/4] Building standalone executable via PyInstaller using $PyinstallerExe..." -ForegroundColor Yellow
& $PyinstallerExe build/deskmate.spec --noconfirm --distpath dist --workpath build/temp

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
    exit 1
}

$DistApp = Join-Path $ProjectDir "dist\AIDeskMate\AIDeskMate.exe"
if (Test-Path $DistApp) {
    Write-Host "Executable build succeeded: $DistApp" -ForegroundColor Green
} else {
    Write-Error "Could not locate built executable at $DistApp"
    exit 1
}

# 4. Build Inno Setup Installer
if (-not $SkipInstaller) {
    Write-Host "[4/4] Locating Inno Setup Compiler (ISCC.exe)..." -ForegroundColor Yellow
    $IsccCandidates = @(
        "ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )

    $IsccPath = $null
    foreach ($cand in $IsccCandidates) {
        if (Get-Command $cand -ErrorAction SilentlyContinue) {
            $IsccPath = $cand
            break
        } elseif (Test-Path $cand) {
            $IsccPath = $cand
            break
        }
    }

    if ($IsccPath) {
        Write-Host "Found Inno Setup at: $IsccPath" -ForegroundColor Green
        & $IsccPath "build/installer.iss"
        if ($LASTEXITCODE -eq 0) {
            $InstallerExe = Join-Path $ProjectDir "dist\AI-DeskMate-Setup-$AppVersion.exe"
            Write-Host "Installer created successfully: $InstallerExe" -ForegroundColor Green
        } else {
            Write-Warning "Inno Setup compilation finished with non-zero exit code: $LASTEXITCODE"
        }
    } else {
        Write-Host "Inno Setup (ISCC.exe) not found on system PATH or standard folders." -ForegroundColor Yellow
        Write-Host "The standalone distribution is ready at: dist\AIDeskMate\" -ForegroundColor Green
        Write-Host "To create the single setup .exe, install Inno Setup 6 from https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
        Write-Host "and run: ISCC.exe build/installer.iss" -ForegroundColor Cyan
    }
} else {
    Write-Host "[4/4] Skipping installer generation (-SkipInstaller specified)." -ForegroundColor Gray
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Build pipeline completed." -ForegroundColor Cyan
