@echo off
rem ============================================
rem  PyCharm Run-End Notifier launcher
rem ============================================
set "PYCMD="
python --version >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto :found
py --version >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if defined PYCMD goto :found

echo [ERROR] Python 3 was not found or is not working.
echo.
echo Please install Python 3 from:  https://www.python.org/downloads/
echo IMPORTANT: during installation, check "Add python.exe to PATH".
echo.
echo If a Microsoft Store window opened instead of this error, the App
echo execution alias for python is enabled but Python is not installed.
echo Fix: Settings ^> Apps ^> Advanced app settings ^> App execution
echo aliases, disable the python.exe / python3.exe aliases, then
echo install Python from python.org.
echo.
pause
exit /b 1

:found
echo Using: %PYCMD%
%PYCMD% --version
%PYCMD% "%~dp0pycharm_run_timer.py"
goto :end

:end
pause
