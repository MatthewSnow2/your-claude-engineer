#!/bin/bash
set -e

# Get absolute path of script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Starting AI Agent Analytics Platform..."

# Install backend dependencies
echo "Setting up backend..."
cd "$SCRIPT_DIR/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
venv/bin/python3 -m pip install -r requirements.txt

# Start backend server in background
echo "Starting backend server on port 8000..."
venv/bin/python3 main.py &
BACKEND_PID=$!

# Install frontend dependencies
echo "Setting up frontend..."
cd "$SCRIPT_DIR/frontend"
npm install --include=dev

# Start frontend dev server
echo "Starting frontend on port 3000..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Application is running!"
echo "   Frontend: http://localhost:3001"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
