@echo off
pyinstaller --onefile --icon=assets/icon.ico --name JiraNotify main.py
mkdir dist/assets/
xcopy assets\* dist\assets\ /E /I
xcopy .env dist\
