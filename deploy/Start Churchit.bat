@echo off
title Churchit
rem Double-click this file to start churchit on Windows.
rem It runs start.ps1 (in this same folder) with the script policy bypassed
rem for this one run, so Windows does not block it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
pause
