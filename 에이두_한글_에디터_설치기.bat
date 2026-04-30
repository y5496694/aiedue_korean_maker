@echo off
setlocal enabledelayedexpansion

set "REPO_URL=https://github.com/y5496694/aiedue_korean_maker/archive/refs/heads/main.zip"
set "FOLDER_NAME=에이두 한글 에디터"
set "ZIP_FILE=aiedu_setup.zip"

echo ======================================================
echo           에이두 한글 에디터 자동 설치기
echo ======================================================
echo.
echo [*] 다운로드를 시작합니다... 잠시만 기다려 주세요.
echo.

:: Download using PowerShell
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%REPO_URL%' -OutFile '%ZIP_FILE%'"

if %ERRORLEVEL% neq 0 (
    echo [!] 다운로드에 실패했습니다. 인터넷 연결을 확인해 주세요.
    pause
    exit /b
)

echo [*] 압축을 해제하는 중입니다...
echo.

:: Extract using PowerShell
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '.' -Force"

if %ERRORLEVEL% neq 0 (
    echo [!] 압축 해제에 실패했습니다.
    pause
    exit /b
)

:: Rename the extracted folder (GitHub ZIPs have branch names in the folder name)
echo [*] 폴더 정리 중...
if exist "aiedue_korean_maker-main" (
    if exist "%FOLDER_NAME%" (
        echo [*] 기존 폴더가 발견되어 백업합니다...
        move "%FOLDER_NAME%" "%FOLDER_NAME%_backup_%date%"
    )
    ren "aiedue_korean_maker-main" "%FOLDER_NAME%"
)

:: Cleanup
del "%ZIP_FILE%"

echo.
echo ======================================================
echo           설치가 완료되었습니다!
echo ======================================================
echo.
echo [!] '%FOLDER_NAME%' 폴더가 생성되었습니다.
echo [!] 해당 폴더 안의 '에이두 한글 에디터.bat'을 실행해 주세요.
echo.
pause
