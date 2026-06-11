@echo off

echo Deploying firmware to OpenMV...

if exist D:\src rmdir /S /Q D:\src

xcopy firmware\main.py D:\ /Y
xcopy firmware\src D:\src\ /E /I /Y

echo Done.
pause