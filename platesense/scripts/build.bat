@echo off
REM Build a standalone PlateSense distributable on Windows.
REM Usage: scripts\build.bat [--onefile]
setlocal enabledelayedexpansion
pushd "%~dp0.."

REM --- Guard: Python version check -------------------------------------------
python -c "import sys; assert (3,11) <= sys.version_info[:2] <= (3,13), 'Python 3.11, 3.12 or 3.13 is required (you have %s).' % sys.version.split()[0]"
if errorlevel 1 (
    echo.
    echo [ERROR] Unsupported Python version. Please install Python 3.11 or 3.12 from https://www.python.org/downloads/ and try again.
    echo Make sure to tick "Add Python to PATH" during install, then delete the
    echo existing .venv folder and re-run scripts\build.bat.
    popd
    exit /b 1
)

if not exist .venv (
    echo [setup] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail

python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [setup] Installing runtime + build dependencies...
python -m pip install -r requirements-dev.txt
if errorlevel 1 goto :fail

set ONEFILE=
if "%~1"=="--onefile" set ONEFILE=--onefile

echo [build] Running PyInstaller...
pyinstaller PlateSense.spec --clean --noconfirm %ONEFILE%
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  Build finished successfully.
echo  Output: %CD%\dist\PlateSense\PlateSense.exe
echo ============================================================
popd
exit /b 0

:fail
echo.
echo [ERROR] Build failed. See output above for details.
popd
exit /b 1
