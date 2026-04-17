#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== CampingV2 ===${NC}"

# Kill existing processes on our ports
for PORT in 8000 5173; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "Killing process on port $PORT (PID: $PID)"
        kill $PID 2>/dev/null || true
        sleep 1
    fi
done

# Backend
echo -e "${BLUE}Starting backend...${NC}"
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
python3 -m uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend
echo -e "${BLUE}Starting frontend...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    npm install --silent
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}Swagger:  http://localhost:8000/docs${NC}"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" SIGINT SIGTERM
wait
