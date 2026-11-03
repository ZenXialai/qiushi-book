@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY (
  for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.10+ and add it to PATH.
  pause
  exit /b 1
)

echo Starting Qiushi PDF maker ...
echo Browser opens automatically. Close this window to stop the service.
echo.

"%PY%" -u app.py
set RC=%ERRORLEVEL%
if "%RC%"=="0" goto end
if "%RC%"=="3" goto end
echo.
echo [!] Service exited with code %RC%. See messages above.
pause
:end
endlocal
