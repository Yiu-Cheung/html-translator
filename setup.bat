@echo off
REM Setup script for HTML Translation POC
echo ================================
echo HTML Translation POC Setup
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo Found Python:
python --version
echo.

REM Check if venv already exists
if exist "venv\" (
    echo Virtual environment already exists at: venv\
    choice /C YN /M "Do you want to recreate it"
    if errorlevel 2 goto :install_deps
    echo.
    echo Removing existing venv...
    rmdir /S /Q venv
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment created
echo.

:install_deps
REM Activate venv and install dependencies
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

echo ================================
echo Setup Complete!
echo ================================
echo.
echo Next steps:
echo 1. Make sure Ollama is running with gemma3:4b model
echo 2. Place HTML files in poc\input\ folder
echo 3. Run: cd poc
echo 4. Run: run_demo.bat
echo.
echo Press any key to exit...
pause >nul
