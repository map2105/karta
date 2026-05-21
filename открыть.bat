@echo off
chcp 65001 > nul
title Карта России

:: Переходим в папку где лежит этот bat-файл (всегда E:\karta)
cd /d "%~dp0"

echo.
echo  ====================================
echo   Запуск карты России...
echo  ====================================
echo.

:: Убиваем предыдущий сервер на порту 8080 (если был)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8080 "') do (
    taskkill /f /pid %%a > nul 2>&1
)

echo  Сервер: http://localhost:8080
echo  Закройте это окно чтобы остановить сервер.
echo.

:: Открываем браузер через 1.5 секунды
start "" /b cmd /c "timeout /t 2 /nobreak > nul && start http://localhost:8080"

:: Запускаем Python HTTP сервер (окно остаётся открытым)
python -m http.server 8080

pause
