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
    :: Use PowerShell to compare versions reliably (handles line endings/BOM)
    powershell -Command "$local = (Get-Content version.txt -Raw).Trim(); $remote = (Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/y5496694/aiedue_korean_maker/main/version.txt').Trim(); if ($local -ne $remote) { exit 1 } else { exit 0 }"
    
    if %errorlevel% equ 1 (
        for /f "usebackq delims=" %%v in (`powershell -Command "(Invoke-RestMethod -Uri 'https://raw.githubusercontent.com/y5496694/aiedue_korean_maker/main/version.txt').Trim()"`) do set "REMOTE_VERSION=%%v"
        set /p LOCAL_VERSION=<version.txt
        echo.
        echo ======================================================
        echo  [!] New version available: !REMOTE_VERSION! (Current: !LOCAL_VERSION!)
        echo ======================================================
        echo.
        set /p "DO_UPDATE=Update now? (Y/N): "
        if /i "!DO_UPDATE!"=="Y" (
            if exist ".git" (
                echo [*] Updating via Git...
                git pull
                echo [*] Done. Please restart.
                pause
                exit /b
            ) else (
                echo [!] No .git folder. Please download manually.
                pause
            )
        )
    ) else (
        echo [*] Version is up to date.
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
