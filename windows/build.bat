@echo off
setlocal EnableDelayedExpansion

rem Build a portable FFIV3DSaveEditor.exe. Run this from Windows.
cd /d "%~dp0"
set LOGFILE=%~dp0build.log
echo Build started %date% %time% > "%LOGFILE%"

call :main
set RESULT=%ERRORLEVEL%
echo.
if %RESULT% neq 0 (
    echo ============================================================
    echo BUILD FAILED. Full log: %LOGFILE%
    echo ============================================================
) else (
    echo ============================================================
    echo BUILD SUCCEEDED.
    echo Portable exe: %~dp0dist\FFIV3DSaveEditor.exe
    echo ============================================================
)
echo.
pause
exit /b %RESULT%

:main
if not exist "..\ffiv3d_save_gui.py" (
    echo The windows folder must remain inside the complete project directory.
    exit /b 1
)

set PYCMD=
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 --version >>"%LOGFILE%" 2>&1
    if !ERRORLEVEL! equ 0 set PYCMD=py -3
)
if "!PYCMD!"=="" (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        python --version >>"%LOGFILE%" 2>&1
        if !ERRORLEVEL! equ 0 set PYCMD=python
    )
)
if "!PYCMD!"=="" (
    echo Python 3.10 or newer was not found on PATH.
    exit /b 1
)

if not exist .buildenv (
    !PYCMD! -m venv .buildenv >>"%LOGFILE%" 2>&1
    if !ERRORLEVEL! neq 0 exit /b 1
)
call .buildenv\Scripts\activate.bat

python -m pip install --upgrade pip >>"%LOGFILE%" 2>&1
python -m pip install pyinstaller pyside6-essentials >>"%LOGFILE%" 2>&1
if !ERRORLEVEL! neq 0 (
    echo Dependency installation failed; see %LOGFILE%.
    exit /b 1
)

python -m PyInstaller --noconfirm --clean FFIV3DSaveEditor.spec >>"%LOGFILE%" 2>&1
if !ERRORLEVEL! neq 0 (
    echo PyInstaller failed; see %LOGFILE%.
    exit /b 1
)
if not exist dist\FFIV3DSaveEditor.exe (
    echo PyInstaller reported success but the executable is missing.
    exit /b 1
)
exit /b 0
