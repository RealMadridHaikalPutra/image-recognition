@echo off
REM Database Management Script for Windows
REM PostgreSQL utilities for image_search database

setlocal enabledelayedexpansion

set DB_NAME=image_search
set DB_USER=postgres
set DB_HOST=localhost
set DB_PORT=5432

echo.
echo ^|==================================================^|
echo ^|  Database Management - image_search Database    ^|
echo ^|==================================================^|
echo.

if "%1"=="" (
    call :show_menu
    exit /b
)

if /i "%1"=="create" (
    call :create_db
) else if /i "%1"=="drop" (
    call :drop_db
) else if /i "%1"=="backup" (
    call :backup_db
) else if /i "%1"=="restore" (
    call :restore_db %2
) else if /i "%1"=="size" (
    call :show_size
) else if /i "%1"=="tables" (
    call :show_tables
) else if /i "%1"=="vacuum" (
    call :vacuum_db
) else (
    call :show_menu
)

exit /b

REM ==================================================
REM Function: Create database
REM ==================================================
:create_db
echo [*] Creating database: %DB_NAME%
echo.
createdb -h %DB_HOST% -U %DB_USER% %DB_NAME% 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Database created successfully
) else (
    echo [ERROR] Database already exists or error occurred
)
exit /b


REM ==================================================
REM Function: Drop database
REM ==================================================
:drop_db
echo [*] Dropping database: %DB_NAME%
set /p confirm="Are you sure? This will delete all data! (yes/no): "
if /i "%confirm%"=="yes" (
    dropdb -h %DB_HOST% -U %DB_USER% %DB_NAME% 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [OK] Database dropped successfully
    ) else (
        echo [ERROR] Error dropping database
    )
) else (
    echo [CANCEL] Operation cancelled
)
exit /b


REM ==================================================
REM Function: Backup database
REM ==================================================
:backup_db
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set BACKUP_FILE=backup_%DB_NAME%_%mydate%_%mytime%.sql

echo [*] Creating backup: %BACKUP_FILE%
echo.
pg_dump -h %DB_HOST% -U %DB_USER% %DB_NAME% > %BACKUP_FILE%
if %ERRORLEVEL% equ 0 (
    echo [OK] Backup created: %BACKUP_FILE%
) else (
    echo [ERROR] Backup failed
)
exit /b


REM ==================================================
REM Function: Restore database
REM ==================================================
:restore_db
if "%1"=="" (
    echo [ERROR] Please provide backup file
    echo Usage: %0 restore backup_file.sql
    exit /b 1
)

if not exist "%1" (
    echo [ERROR] File not found: %1
    exit /b 1
)

echo [*] Restoring from: %1
set /p confirm="This will overwrite existing data! Continue? (yes/no): "
if /i "%confirm%"=="yes" (
    psql -h %DB_HOST% -U %DB_USER% -d %DB_NAME% < %1
    if %ERRORLEVEL% equ 0 (
        echo [OK] Database restored successfully
    ) else (
        echo [ERROR] Restore failed
    )
) else (
    echo [CANCEL] Operation cancelled
)
exit /b


REM ==================================================
REM Function: Show database size
REM ==================================================
:show_size
echo [*] Database size:
echo.
psql -h %DB_HOST% -U %DB_USER% -d %DB_NAME% -c "SELECT pg_size_pretty(pg_database_size('%DB_NAME%')) as size;"
exit /b


REM ==================================================
REM Function: Show table info
REM ==================================================
:show_tables
echo [*] Tables and row counts:
echo.
psql -h %DB_HOST% -U %DB_USER% -d %DB_NAME% -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';"
exit /b


REM ==================================================
REM Function: Vacuum database
REM ==================================================
:vacuum_db
echo [*] Vacuuming and analyzing database...
psql -h %DB_HOST% -U %DB_USER% -d %DB_NAME% -c "VACUUM ANALYZE;"
if %ERRORLEVEL% equ 0 (
    echo [OK] Vacuum and analyze complete
) else (
    echo [ERROR] Vacuum failed
)
exit /b


REM ==================================================
REM Function: Show menu
REM ==================================================
:show_menu
echo.
echo PostgreSQL Database Management Utility
echo.
echo Usage: %0 {command} [options]
echo.
echo Commands:
echo   create              Create new database
echo   drop                Drop existing database
echo   backup              Backup database to SQL file
echo   restore XXXX.sql    Restore database from SQL file
echo   size                Show database size
echo   tables              Show table info
echo   vacuum              Vacuum and analyze database
echo.
echo Examples:
echo   %0 create
echo   %0 backup
echo   %0 restore backup_image_search.sql
echo.
exit /b
