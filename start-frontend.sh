#!/bin/bash
# QSOP Frontend Startup Script for Linux/Mac
# =============================================

echo "Starting QSOP Frontend..."
echo ""

cd "$(dirname "$0")/frontend"

echo "Starting HTTP server on http://127.0.0.1:8080"
python -m http.server 8080
