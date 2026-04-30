@echo off
setlocal enabledelayedexpansion
title Aiedu HWP Editor - Launcher

echo ===================================================
echo   Aiedu HWP Editor: Launcher and Updater
echo ===================================================

:: 1. Python Check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found. Installing via winget...
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [!] Python installation failed.
        pause
        exit /b
    )
    echo [!] Please restart this script.
    pause
    exit /b
)

:: 2. Git Check
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Git not found. Installing via winget...
    winget install --id Git.Git --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo [!] Git installation failed.
    ) else (
        echo [!] Git installed. Please restart this script for updates.
        pause
        exit /b
    )
)

:: 3. Virtual Env
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

:: 4. Update Check
if exist "version.txt" (
    echo [*] Checking for updates...
    set /p LOCAL_VERSION=<version.txt
    
    :: Use a safer way to get remote version
    powershell -Command "$v = (Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/y5496694/aiedue_korean_maker/main/version.txt').Trim(); $v | Out-File -FilePath 'remote.tmp' -Encoding ascii"
    
    if exist "remote.tmp" (
        set /p REMOTE_VERSION=<remote.tmp
        del "remote.tmp"
        
        if not "!LOCAL_VERSION!"=="!REMOTE_VERSION!" (
            echo.
            echo [!] New version available: !REMOTE_VERSION! (Current: !LOCAL_VERSION!)
            set /p "DO_UPDATE=Update now? (Y/N): "
            if /i "!DO_UPDATE!"=="Y" (
                if exist ".git" (
                    echo [*] Updating via Git...
                    git pull
                    echo [*] Done. Restarting...
                    pause
                    exit /b
                ) else (
                    echo [!] No .git folder. Please download manually.
                    pause
                )
            )
        ) else (
            echo [*] Version is up to date: !LOCAL_VERSION!
        )
    )
)

:: 5. Run App
echo [*] Activating environment and installing dependencies...
call venv\Scripts\activate
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

echo [*] Launching App...
python app.py

if %errorlevel% neq 0 (
    echo [!] App closed with an error.
    pause
)
deactivate
