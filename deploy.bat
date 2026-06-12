@echo off

echo Deploying firmware to OpenMV...

if exist D:\src rmdir /S /Q D:\src
REM if exist D:\main.py del D:\main.py

REM xcopy firmware\main.py D:\test_main.py /Y
xcopy firmware\src D:\src\ /E /I /Y

echo Done.
pause