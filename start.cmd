@echo off
rem Double-click to start SkillSprint AI. Options: start.cmd -NoLLM -NoBrowser
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
