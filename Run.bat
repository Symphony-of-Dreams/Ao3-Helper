@echo off



TITLE AO3 Helper - Development Console


IF NOT EXIST ".\venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please ensure the 'venv' folder exists in the project root.
    pause
    exit /b 1
)


echo [INFO] Activating virtual environment...
call ".\venv\Scripts\activate.bat"


IF NOT EXIST ".\src\main.py" (
    echo [ERROR] Entry point script 'src/main.py' not found.
    echo Please ensure the project structure is correct.
    pause
    exit /b 1
)


echo [INFO] Starting AO3 Helper...
python .\src\main.py

echo [INFO] Application has exited. Press any key to close this console.
pause