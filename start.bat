@echo off
chcp 65001 >nul
echo.
echo ===================================================
echo   LottoAI Pro — Backend Node API Server
echo ===================================================
echo.

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ไม่พบ Node.js! กรุณาติดตั้ง Node.js ก่อน
    pause
    exit /b 1
)

echo [1/2] กำลังตรวจสอบ Dependencies...
if not exist "node_modules" (
    echo [INFO] กำลังติดตั้ง Dependencies...
    npm install express cors axios cheerio
)

echo [2/2] เริ่มต้น API Server ที่ http://127.0.0.1:8765
echo.
echo กด Ctrl+C เพื่อหยุด Server
echo.

node server.js

pause
