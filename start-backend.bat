@echo off
REM QSOP Backend Startup Script for Windows
REM =============================================

echo Starting QSOP Backend...
echo.

cd /d D:\Quantum

REM Use virtual environment Python directly
if exist .venv\Scripts\python.exe (
    set PYTHON_EXEC=.venv\Scripts\python.exe
    echo Using virtual environment: .venv\Scripts\python.exe
) else (
    set PYTHON_EXEC=python
    echo Using system Python
)

echo.
echo Starting FastAPI backend on http://127.0.0.1:8000
echo.
echo Press CTRL+C to stop
echo.

REM Try to start the full backend first, fallback to minimal
%PYTHON_EXEC% -c "import sys; sys.path.insert(0, ''); sys.path.insert(0, 'src'); from qsop.main import app" 2>nul
if errorlevel 1 (
    echo.
    echo Full backend not available, starting minimal backend...
    echo.
    %PYTHON_EXEC% -m uvicorn minimal_backend:app --host 127.0.0.1 --port 8000 --reload
) else (
    echo Starting full backend with hexagonal architecture...
    echo.
    %PYTHON_EXEC% -m uvicorn qsop.main:app --host 127.0.0.1 --port 8000 --reload
)

pause
