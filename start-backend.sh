#!/bin/bash
# QSOP Backend Startup Script for Linux/Mac
# =============================================

echo "Starting QSOP Backend..."
echo ""

# Set Python path
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"

# Check dependencies
echo "Checking dependencies..."
pip list | grep -E "fastapi|uvicorn" > /dev/null
if [ $? -ne 0 ]; then
    echo "Installing required dependencies..."
    pip install fastapi uvicorn[standard] python-multipart python-jose[cryptography] passlib[bcrypt] aiofiles qiskit qiskit-aer
fi

# Start backend
echo "Starting FastAPI backend on http://127.0.0.1:8000"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
