#!/bin/bash
# Launch pkiler with backend server
cd ~/Desktop/pkiler

# Kill any existing server on port 8899
lsof -ti:8899 | xargs kill 2>/dev/null

# Start backend server
python3 pkiler.app/Contents/Resources/pkiler_server.py &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Open the reader
open pkiler.app

echo "Server PID: $SERVER_PID"
echo "Press Ctrl+C to stop"
wait $SERVER_PID
