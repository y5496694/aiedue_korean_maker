@echo off
title Aiedu HWP Editor - Launcher

echo ===================================================
echo   Aiedu HWP Editor: Auto Installer and Launcher
echo ===================================================

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed.
    echo Trying to install Python via winget...
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo Installation failed. Please install Python manually from python.org
        pause
        exit /b
    )
    echo Installation complete. Please restart this script.
    pause
    exit /b
)

REM 2. Virtual Env
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM 3. Dependencies
echo Installing requirements...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

REM 4. Run
echo Launching App...
python app.py

if %errorlevel% neq 0 (
    echo Error occurred during execution.
    pause
)

deactivate
