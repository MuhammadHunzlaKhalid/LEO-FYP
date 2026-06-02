@echo off
echo Searching for mongod.exe...
echo.
for /d %%v in ("C:\Program Files\MongoDB\Server\*") do (
    if exist "%%v\bin\mongod.exe" (
        echo FOUND: %%v\bin\mongod.exe
    )
)
for /d %%v in ("C:\MongoDB\*") do (
    if exist "%%v\bin\mongod.exe" (
        echo FOUND: %%v\bin\mongod.exe
    )
)
where mongod 2>nul && echo FOUND IN PATH: mongod
echo.
echo Done. Copy the path shown above.
pause
