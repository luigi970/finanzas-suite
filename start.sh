#!/bin/bash

# Stock Screener — arranque para Linux y macOS

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "Iniciando Stock Screener..."

# Backend
cd "$ROOT/backend"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Frontend
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Presioná Ctrl+C para detener."

# Al hacer Ctrl+C mata ambos procesos
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
