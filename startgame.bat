@echo off
rem ---------------------------------------------------------------------------
rem  The Long Post - start the game.
rem
rem  Double-click this, or run it from a prompt with a seed:
rem      startgame.bat              the default seed
rem      startgame.bat 7            seed 7
rem      startgame.bat 7 --resume   seed 7, taking up the written run
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem The py launcher first: it is what a Windows python install provides.
set "PYTHON="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"

if not defined PYTHON (
    python --version >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo Python 3.11 or newer was not found on this machine.
    echo Install it from https://www.python.org/downloads/ and run this again.
    echo Tick "Add python.exe to PATH" in the installer.
    goto :wait
)

rem pygame and numpy, and nothing else. If either is missing, offer to fetch them.
%PYTHON% -c "import pygame, numpy" >nul 2>&1
if errorlevel 1 (
    echo The game needs pygame and numpy, and they are not installed.
    set /p "FETCH=Install them now? [y/N] "
    if /i not "!FETCH!"=="y" goto :wait
    %PYTHON% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo The install did not finish. Try it by hand:
        echo     %PYTHON% -m pip install -r requirements.txt
        goto :wait
    )
)

%PYTHON% -m longpost %*
if errorlevel 1 (
    echo.
    echo The game stopped with an error. The lines above say why.
    goto :wait
)

endlocal
exit /b 0

:wait
echo.
pause
endlocal
exit /b 1
