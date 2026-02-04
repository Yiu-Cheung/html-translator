@echo off
REM HTML Translation App Launcher
REM Activates virtual environment and launches the PySide6 application

echo Starting HTML Translator...

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first to create the virtual environment.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if PySide6 is installed
python -c "import PySide6" 2>nul
if errorlevel 1 (
    echo Installing PySide6...
    pip install PySide6>=6.6.0 Pygments>=2.17.0
)

REM Launch the application
python -m app.main

REM Deactivate on exit
deactivate
