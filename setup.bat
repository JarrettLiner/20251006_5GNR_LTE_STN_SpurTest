@echo off
echo Setting up virtual environment...

:: Check if Python is installed and version is 3.8 or higher
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version') do set PY_VERSION=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)
if %MAJOR% lss 3 (
    echo Python 3.8 or higher is required. Found version %PY_VERSION%.
    pause
    exit /b 1
)
if %MAJOR% equ 3 if %MINOR% lss 8 (
    echo Python 3.8 or higher is required. Found version %PY_VERSION%.
    pause
    exit /b 1
)

:: Create virtual environment
python -m venv .venv
if %ERRORLEVEL% neq 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Upgrade pip
echo Upgrading pip...
pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

:: Check if requirements.txt exists
if not exist requirements.txt (
    echo requirements.txt not found in the current directory.
    pause
    exit /b 1
)

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo Setup complete. Run 'python src/main.py' to start measurements.
echo For Linux/macOS, use: source .venv/bin/activate