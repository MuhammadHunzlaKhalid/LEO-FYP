@echo off
title Stopping LEO...
taskkill /F /IM mongod.exe     >nul 2>&1
taskkill /F /IM uvicorn.exe    >nul 2>&1
taskkill /F /IM dart.exe       >nul 2>&1
wmic process where "commandline like '%%dashboard.py%%'" delete >nul 2>&1
wmic process where "commandline like '%%leo_app.py%%'"   delete >nul 2>&1
echo All LEO services stopped.
pause
