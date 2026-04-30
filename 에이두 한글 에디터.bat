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

REM 1.5 Check Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [*] Git is not detected. Installing Git for automatic updates...
    winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [!] Git installation failed. Automatic updates might be limited.
    ) else (
        echo [*] Git installed successfully. Please restart this script to enable update features.
        pause
        exit /b
    )
)

REM 2. Virtual Env
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

setlocal enabledelayedexpansion
REM 2.5 Update Check
echo.
echo [*] Checking for updates...
if exist "version.txt" (
    set /p LOCAL_VERSION=<version.txt
    for /f "delims=" %%v in ('powershell -Command "(Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/y5496694/aiedue_korean_maker/main/version.txt' -UseBasicParsing).Content.Trim()"') do set "REMOTE_VERSION=%%v"
    
    if not "!LOCAL_VERSION!"=="!REMOTE_VERSION!" (
        echo.
        echo ======================================================
        echo  [!] New update available: !REMOTE_VERSION! (Current: !LOCAL_VERSION!)
        echo ======================================================
        echo.
        set /p "UPDATE_CHOICE=Do you want to update now? (Y/N): "
        if /i "!UPDATE_CHOICE!"=="Y" (
            if exist ".git" (
                echo [*] Updating via Git...
                git pull
                echo [*] Update complete. Please restart the program.
                pause
                exit
            ) else (
                echo [!] No Git detected. Please run '에이두_한글_에디터_설치기.bat' to update.
                pause
            )
        )
    ) else (
        echo [*] Running the latest version (!LOCAL_VERSION!).
    )
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
