@echo off
REM Build a standalone PlateSense distributable on Windows.
REM Usage: scripts\build.bat [--onefile]
setlocal
pushd "%~dp0.."

if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

set ONEFILE=
if "%~1"=="--onefile" set ONEFILE=--onefile

pyinstaller PlateSense.spec --clean --noconfirm %ONEFILE%

echo.
echo Build finished. Output:
echo   %CD%\dist\PlateSense\PlateSense.exe
popd
endlocal
