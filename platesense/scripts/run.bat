@echo off
REM Run PlateSense from a source checkout on Windows.
REM Creates a venv and installs deps on first run.
setlocal enabledelayedexpansion
pushd "%~dp0.."

python -c "import sys; assert (3,11) <= sys.version_info[:2] <= (3,13), 'Python 3.11/3.12/3.13 required (you have %s).' % sys.version.split()[0]"
if errorlevel 1 (
    echo [ERROR] Unsupported Python version. Install Python 3.12 from https://www.python.org/downloads/ and tick "Add Python to PATH".
    popd
    exit /b 1
)

if not exist .venv (
    echo [setup] Creating virtual environment...
    python -m venv .venv || goto :fail
)

call .venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || goto :fail

python app.py
popd
exit /b %errorlevel%

:fail
echo [ERROR] Setup failed. See output above.
popd
exit /b 1
