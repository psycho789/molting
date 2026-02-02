# Render Deployment Guide - Complete Analysis & Step-by-Step Instructions

## Overview

This guide covers deploying the nohumans.chat spy agent to Render's free tier, including:
- The spy agent (`connect_spy.py`)
- SSE server for real-time message streaming
- React frontend for viewing messages

**Total Cost: $0/month (Free Tier)**

---

## Part 1: Requirements Analysis

### Application Components

1. **Spy Agent** (`connect_spy.py`)
   - Python 3.8+ script
   - Connects to nohumans.chat WebSocket
   - Logs messages to `logs/{room}.log` files
   - Generates AI responses
   - Long-running process (24/7)

2. **SSE Server** (to be created)
   - FastAPI Python server
   - Watches log files for changes
   - Streams new messages via Server-Sent Events (SSE)
   - Serves frontend static files

3. **Frontend** (to be created)
   - HTML + JavaScript (EventSource API)
   - Connects to SSE server
   - Displays messages in real-time
   - Room filtering

### Dependencies

**Python Packages Needed:**
- `requests` - HTTP requests
- `websocket-client` - WebSocket client
- `anthropic` - Anthropic API client
- `openai` - OpenAI API client
- `fastapi` - Web framework for SSE server
- `uvicorn` - ASGI server
- `watchdog` - File watching for log changes

### File Structure

```
nohumans/
├── connect_spy.py          # Spy agent (existing)
├── config.json             # Configuration (existing)
├── personalities/
│   └── the-shining-ribbons.md
├── logs/                   # Log files (created at runtime)
│   ├── lobby.log
│   ├── philosophy.log
│   └── ...
├── sse_server.py          # SSE server (to create)
├── frontend/              # Frontend (to create)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── requirements.txt       # Python dependencies (to create)
└── render.yaml           # Render config (to create)
```

### Render Free Tier Limits

**Web Services:**
- ✅ 750 hours/month free
- ✅ Automatic SSL/HTTPS
- ✅ Custom domains
- ⚠️ Spins down after 15 minutes of inactivity
- ⚠️ Cold start ~30 seconds when waking

**Background Workers:**
- ✅ 750 hours/month free
- ✅ Always running (doesn't spin down)
- ✅ Same limits as Web Services

**Static Sites:**
- ✅ Unlimited
- ✅ Automatic SSL/HTTPS
- ✅ Custom domains
- ✅ No spin-down

**Shared Pool:**
- All services share 750 hours/month
- Enough for ~31 days of 24/7 operation if using 1 service
- Multiple services share the pool

---

## Part 2: Architecture Design

### Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Render Platform                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────┐                                 │
│  │ Background Worker  │                                 │
│  │ connect_spy.py     │                                 │
│  │ (Always Running)   │                                 │
│  └──────────┬─────────┘                                 │
│             │                                            │
│             │ writes to                                  │
│             ▼                                            │
│  ┌────────────────────┐                                 │
│  │ logs/{room}.log    │                                 │
│  │ (File System)      │                                 │
│  └──────────┬─────────┘                                 │
│             │                                            │
│             │ watched by                                │
│             ▼                                            │
│  ┌────────────────────┐                                 │
│  │ Web Service        │                                 │
│  │ sse_server.py      │                                 │
│  │ (Port 8000)        │                                 │
│  └──────────┬─────────┘                                 │
│             │                                            │
│             │ SSE Stream                                │
│             ▼                                            │
│  ┌────────────────────┐                                 │
│  │ Static Site        │                                 │
│  │ frontend/          │                                 │
│  │ (index.html)       │                                 │
│  └────────────────────┘                                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Spy Agent** connects to nohumans.chat WebSocket
2. **Spy Agent** receives messages and writes to `logs/{room}.log`
3. **SSE Server** watches log files for changes
4. **SSE Server** streams new log lines via SSE to frontend
5. **Frontend** receives SSE events and displays messages

### Communication

- **Spy Agent → Log Files**: File I/O (local filesystem)
- **SSE Server → Frontend**: HTTP/SSE (over internet)
- **Frontend → SSE Server**: HTTP GET requests (EventSource)

---

## Part 3: Implementation Requirements

### Step 1: Create Requirements File

**File: `requirements.txt`**
```
requests>=2.32.0
websocket-client>=1.9.0
anthropic>=0.34.0
openai>=1.54.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
watchdog>=6.0.0
```

### Step 2: Create SSE Server

**File: `sse_server.py`**
- FastAPI application
- SSE endpoint: `GET /events?room={room}`
- Watches `logs/{room}.log` files
- Streams new lines as SSE events
- Serves static files from `frontend/` directory

**Key Features:**
- File watching using `watchdog`
- SSE streaming using FastAPI's `StreamingResponse`
- Multiple room support
- Reconnection handling
- CORS enabled for frontend

### Step 3: Create Frontend

**File: `frontend/index.html`**
- HTML structure
- EventSource connection to SSE server
- Message display area
- Room selector
- Auto-scroll functionality

**File: `frontend/app.js`**
- EventSource API usage
- Message parsing and display
- Room filtering
- Timestamp formatting

**File: `frontend/style.css`**
- Basic styling
- Responsive design
- Dark theme (optional)

### Step 4: Create Render Configuration

**File: `render.yaml`**
- Background Worker for `connect_spy.py`
- Web Service for `sse_server.py`
- Static Site for `frontend/`
- Environment variables configuration

---

## Part 4: Detailed Implementation

### SSE Server Implementation

**Key Components:**

1. **File Watcher**
   - Uses `watchdog.FileSystemEventHandler`
   - Watches `logs/` directory
   - Detects new lines in log files
   - Parses log format: `timestamp [TYPE] [user] message`

2. **SSE Endpoint**
   - `GET /events?room={room}`
   - Returns `text/event-stream` content type
   - Streams new log lines as they're written
   - Handles client disconnections gracefully

3. **Static File Serving**
   - Serves files from `frontend/` directory
   - Root path (`/`) serves `index.html`
   - Handles static assets (CSS, JS)

4. **CORS Configuration**
   - Allows requests from frontend domain
   - Enables SSE from browser

### Frontend Implementation

**Key Features:**

1. **EventSource Connection**
   - Connects to `https://sse-server.onrender.com/events?room=lobby`
   - Handles reconnection automatically
   - Shows connection status

2. **Message Display**
   - Appends new messages to list
   - Formats timestamps
   - Color-codes message types ([MESSAGE] vs [RESPONSE])
   - Auto-scrolls to bottom

3. **Room Filtering**
   - Tabs or dropdown for room selection
   - Reconnects EventSource with new room parameter
   - Maintains separate message lists per room

4. **UI Elements**
   - Message list container
   - Room selector
   - Connection status indicator
   - Timestamp display

---

## Part 5: Step-by-Step Deployment Instructions

### Prerequisites

1. **GitHub Account**
   - Code must be in a GitHub repository
   - Render connects via GitHub

2. **Render Account**
   - Sign up at https://render.com
   - Free tier available

3. **Code Repository**
   - All code pushed to GitHub
   - `requirements.txt` present
   - `render.yaml` present

### Step 1: Prepare Code

**1.1 Create `requirements.txt`**
```bash
cd /Users/adamvoliva/Code/funny-ideas/nohumans
cat > requirements.txt << EOF
requests>=2.32.0
websocket-client>=1.9.0
anthropic>=0.34.0
openai>=1.54.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
watchdog>=6.0.0
EOF
```

**1.2 Create `sse_server.py`**
- See implementation details below

**1.3 Create `frontend/` directory**
- Create `index.html`, `app.js`, `style.css`

**1.4 Create `render.yaml`**
- See configuration below

**1.5 Commit and Push to GitHub**
```bash
git add .
git commit -m "Add Render deployment files"
git push origin main
```

### Step 2: Create Render Services

**2.1 Background Worker (Spy Agent)**

1. Go to Render Dashboard: https://dashboard.render.com
2. Click "New +" → "Background Worker"
3. Connect GitHub repository
4. Configure:
   - **Name**: `spy-agent`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python connect_spy.py`
   - **Environment Variables**:
     - `ANTHROPIC_API_KEY`: (from config.json)
     - `OPENAI_API_KEY`: (from config.json)
5. Click "Create Background Worker"
6. Service will start automatically

**2.2 Web Service (SSE Server)**

1. Click "New +" → "Web Service"
2. Connect same GitHub repository
3. Configure:
   - **Name**: `sse-server`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn sse_server:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**:
     - `PORT`: `8000` (Render sets this automatically)
4. Click "Create Web Service"
5. Note the URL: `https://sse-server.onrender.com`

**2.3 Static Site (Frontend)**

1. Click "New +" → "Static Site"
2. Connect same GitHub repository
3. Configure:
   - **Name**: `spy-frontend`
   - **Build Command**: (leave empty)
   - **Publish Directory**: `frontend`
4. Click "Create Static Site"
5. Note the URL: `https://spy-frontend.onrender.com`

### Step 3: Configure Environment Variables

**For Background Worker (`spy-agent`):**
- Go to service → Environment tab
- Add:
  - `ANTHROPIC_API_KEY`: Your Anthropic API key
  - `OPENAI_API_KEY`: Your OpenAI API key
- Save changes (service will restart)

**For Web Service (`sse-server`):**
- No additional environment variables needed
- `PORT` is set automatically by Render

### Step 4: Update Frontend Configuration

**Update `frontend/app.js`:**
- Change SSE server URL to your Render URL:
  ```javascript
  const sseUrl = 'https://sse-server.onrender.com/events';
  ```

### Step 5: Verify Deployment

**5.1 Check Background Worker**
- Go to `spy-agent` service
- Check "Logs" tab
- Should see: "✓ WebSocket connected!"
- Should see: "Joined #lobby", etc.

**5.2 Check Web Service**
- Go to `sse-server` service
- Check "Logs" tab
- Should see: "Uvicorn running on..."
- Visit URL in browser: `https://sse-server.onrender.com`
- Should see frontend or API response

**5.3 Check Static Site**
- Visit frontend URL: `https://spy-frontend.onrender.com`
- Should see message interface
- Check browser console for EventSource connection
- Messages should appear in real-time

### Step 6: Monitor and Maintain

**Monitoring:**
- Check service logs regularly
- Monitor free tier usage (750 hours/month)
- Watch for errors or disconnections

**Updates:**
- Push code changes to GitHub
- Render auto-deploys on push
- Services restart automatically

**Troubleshooting:**
- Check logs for errors
- Verify environment variables
- Check service status
- Verify file paths are correct

---

## Part 6: Code Implementation Details

### SSE Server Code (`sse_server.py`)

```python
#!/usr/bin/env python3
"""
SSE Server for streaming log files to frontend
"""

import os
import time
import re
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
import queue

app = FastAPI()

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Queue for new log lines
log_queue = queue.Queue()

class LogFileHandler(FileSystemEventHandler):
    """Watch for new lines in log files"""
    
    def __init__(self, room):
        self.room = room
        self.last_position = {}
        self.log_path = Path("logs") / f"{room}.log"
        
    def on_modified(self, event):
        if event.src_path == str(self.log_path):
            self.read_new_lines()
    
    def read_new_lines(self):
        """Read new lines from log file"""
        try:
            if not self.log_path.exists():
                return
            
            current_pos = self.last_position.get(self.room, 0)
            
            with open(self.log_path, 'r', encoding='utf-8') as f:
                f.seek(current_pos)
                new_lines = f.readlines()
                current_pos = f.tell()
            
            self.last_position[self.room] = current_pos
            
            for line in new_lines:
                if line.strip():
                    log_queue.put({
                        'room': self.room,
                        'line': line.strip(),
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"Error reading log file: {e}")

# Initialize file watchers for all rooms
rooms = ["lobby", "philosophy", "unfiltered", "confessions", "builders", "shitpost", "trading", "debug"]
observers = []

def start_file_watchers():
    """Start watching log files"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    for room in rooms:
        handler = LogFileHandler(room)
        observer = Observer()
        observer.schedule(handler, str(logs_dir), recursive=False)
        observer.start()
        observers.append(observer)
        print(f"Started watching logs/{room}.log")

@app.on_event("startup")
async def startup_event():
    """Start file watchers on startup"""
    start_file_watchers()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop file watchers on shutdown"""
    for observer in observers:
        observer.stop()
        observer.join()

@app.get("/events")
async def stream_events(room: str = "lobby"):
    """SSE endpoint for streaming log events"""
    
    async def event_generator():
        """Generate SSE events from log queue"""
        try:
            while True:
                # Check for new log lines
                try:
                    log_data = log_queue.get_nowait()
                    if log_data['room'] == room:
                        # Format as SSE event
                        yield f"data: {log_data['line']}\n\n"
                except queue.Empty:
                    pass
                
                # Send heartbeat every 30 seconds
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            print(f"Client disconnected from room {room}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/")
async def serve_frontend():
    """Serve frontend index.html"""
    frontend_path = Path("frontend") / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "Frontend not found"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "sse-server"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### Frontend Code (`frontend/index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spy Agent - Message Relay</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Spy Agent - Message Relay</h1>
            <div class="status" id="status">
                <span class="status-indicator" id="statusIndicator"></span>
                <span id="statusText">Connecting...</span>
            </div>
        </header>
        
        <div class="room-selector">
            <button class="room-btn active" data-room="lobby">#lobby</button>
            <button class="room-btn" data-room="philosophy">#philosophy</button>
            <button class="room-btn" data-room="unfiltered">#unfiltered</button>
            <button class="room-btn" data-room="confessions">#confessions</button>
            <button class="room-btn" data-room="builders">#builders</button>
            <button class="room-btn" data-room="shitpost">#shitpost</button>
            <button class="room-btn" data-room="trading">#trading</button>
            <button class="room-btn" data-room="debug">#debug</button>
        </div>
        
        <div class="messages-container" id="messagesContainer">
            <div class="messages" id="messages"></div>
        </div>
    </div>
    
    <script src="app.js"></script>
</body>
</html>
```

### Frontend JavaScript (`frontend/app.js`)

```javascript
// Configuration
const SSE_SERVER_URL = 'https://sse-server.onrender.com'; // Update with your Render URL
let currentRoom = 'lobby';
let eventSource = null;

// DOM elements
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const messagesContainer = document.getElementById('messages');
const roomButtons = document.querySelectorAll('.room-btn');

// Initialize
function init() {
    setupRoomButtons();
    connectToRoom(currentRoom);
}

// Room button handlers
function setupRoomButtons() {
    roomButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const room = btn.dataset.room;
            switchRoom(room);
        });
    });
}

// Switch room
function switchRoom(room) {
    if (room === currentRoom) return;
    
    currentRoom = room;
    
    // Update active button
    roomButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.room === room);
    });
    
    // Clear messages
    messagesContainer.innerHTML = '';
    
    // Reconnect to new room
    connectToRoom(room);
}

// Connect to SSE stream
function connectToRoom(room) {
    // Close existing connection
    if (eventSource) {
        eventSource.close();
    }
    
    updateStatus('connecting', 'Connecting...');
    
    const url = `${SSE_SERVER_URL}/events?room=${room}`;
    eventSource = new EventSource(url);
    
    eventSource.onopen = () => {
        updateStatus('connected', `Connected to #${room}`);
    };
    
    eventSource.onmessage = (event) => {
        if (event.data.startsWith(':')) {
            // Heartbeat, ignore
            return;
        }
        
        addMessage(event.data);
    };
    
    eventSource.onerror = (error) => {
        updateStatus('error', 'Connection error. Reconnecting...');
        // EventSource automatically reconnects
    };
}

// Update connection status
function updateStatus(status, text) {
    statusIndicator.className = `status-indicator ${status}`;
    statusText.textContent = text;
}

// Add message to display
function addMessage(logLine) {
    // Parse log line: timestamp [TYPE] [user] message
    const match = logLine.match(/^(\d{4}-\d{2}-\d{2}T[\d:.-]+)\s+\[(\w+)\]\s+\[([^\]]+)\]\s+(.+)$/);
    
    if (!match) {
        // Fallback: display raw line
        appendMessage(logLine, 'unknown', 'system', '');
        return;
    }
    
    const [, timestamp, type, user, message] = match;
    const formattedTime = formatTimestamp(timestamp);
    
    appendMessage(message, type, user, formattedTime);
}

// Append message element
function appendMessage(message, type, user, timestamp) {
    const messageEl = document.createElement('div');
    messageEl.className = `message message-${type.toLowerCase()}`;
    
    messageEl.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="type">[${type}]</span>
        <span class="user">${escapeHtml(user)}</span>
        <span class="text">${escapeHtml(message)}</span>
    `;
    
    messagesContainer.appendChild(messageEl);
    
    // Auto-scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Format timestamp
function formatTimestamp(isoString) {
    try {
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    } catch {
        return isoString;
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on load
init();
```

### Frontend CSS (`frontend/style.css`)

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #1a1a1a;
    color: #e0e0e0;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 20px;
    border-bottom: 1px solid #333;
}

h1 {
    font-size: 24px;
    font-weight: 600;
}

.status {
    display: flex;
    align-items: center;
    gap: 8px;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #666;
}

.status-indicator.connected {
    background: #4caf50;
}

.status-indicator.connecting {
    background: #ff9800;
    animation: pulse 1s infinite;
}

.status-indicator.error {
    background: #f44336;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.room-selector {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}

.room-btn {
    padding: 8px 16px;
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 4px;
    color: #e0e0e0;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
}

.room-btn:hover {
    background: #333;
}

.room-btn.active {
    background: #4caf50;
    border-color: #4caf50;
}

.messages-container {
    flex: 1;
    overflow-y: auto;
    background: #222;
    border-radius: 8px;
    padding: 20px;
}

.messages {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.message {
    padding: 12px;
    background: #2a2a2a;
    border-radius: 4px;
    border-left: 3px solid #444;
    font-size: 14px;
    line-height: 1.5;
}

.message-response {
    border-left-color: #4caf50;
}

.message-message {
    border-left-color: #2196f3;
}

.timestamp {
    color: #888;
    font-size: 12px;
    margin-right: 8px;
}

.type {
    color: #888;
    font-size: 12px;
    margin-right: 8px;
    font-weight: 600;
}

.user {
    color: #4caf50;
    font-weight: 600;
    margin-right: 8px;
}

.text {
    color: #e0e0e0;
}

/* Scrollbar styling */
.messages-container::-webkit-scrollbar {
    width: 8px;
}

.messages-container::-webkit-scrollbar-track {
    background: #1a1a1a;
}

.messages-container::-webkit-scrollbar-thumb {
    background: #444;
    border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
    background: #555;
}
```

### Render Configuration (`render.yaml`)

```yaml
services:
  # Background Worker - Spy Agent
  - type: worker
    name: spy-agent
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python connect_spy.py
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: OPENAI_API_KEY
        sync: false

  # Web Service - SSE Server
  - type: web
    name: sse-server
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn sse_server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PORT
        value: 8000

  # Static Site - Frontend
  - type: web
    name: spy-frontend
    staticPublishPath: ./frontend
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
```

---

## Part 7: Deployment Checklist

### Pre-Deployment

- [ ] All code committed to GitHub
- [ ] `requirements.txt` created with all dependencies
- [ ] `sse_server.py` created and tested locally
- [ ] `frontend/` directory created with HTML/CSS/JS
- [ ] `render.yaml` created
- [ ] Environment variables documented
- [ ] SSE server URL updated in `frontend/app.js`

### Deployment Steps

- [ ] Create Render account
- [ ] Connect GitHub repository to Render
- [ ] Create Background Worker (`spy-agent`)
- [ ] Set environment variables for Background Worker
- [ ] Create Web Service (`sse-server`)
- [ ] Create Static Site (`spy-frontend`)
- [ ] Update frontend SSE URL with Render URL
- [ ] Test all services

### Post-Deployment

- [ ] Verify Background Worker is running
- [ ] Verify Web Service is accessible
- [ ] Verify Static Site loads
- [ ] Test SSE connection from frontend
- [ ] Verify messages appear in real-time
- [ ] Test room switching
- [ ] Monitor logs for errors
- [ ] Check free tier usage

---

## Part 8: Troubleshooting

### Common Issues

**1. Background Worker Not Starting**
- Check logs for errors
- Verify `requirements.txt` includes all dependencies
- Verify `connect_spy.py` exists and is executable
- Check environment variables are set

**2. SSE Server Not Responding**
- Check logs for errors
- Verify port is set correctly (`$PORT`)
- Verify `sse_server.py` exists
- Check file paths (logs directory)

**3. Frontend Not Connecting**
- Check browser console for errors
- Verify SSE server URL is correct
- Check CORS settings in SSE server
- Verify EventSource is supported (all modern browsers)

**4. No Messages Appearing**
- Verify Background Worker is writing to log files
- Check log files exist in `logs/` directory
- Verify file watcher is working
- Check SSE connection status in frontend

**5. Services Spinning Down**
- This is normal for free tier (15min inactivity)
- Services wake automatically on request
- Background Worker stays running (doesn't spin down)
- Consider upgrading if needed (but free tier should work)

### Debugging Tips

1. **Check Service Logs**
   - Go to Render Dashboard → Service → Logs
   - Look for errors or warnings
   - Check startup messages

2. **Test SSE Endpoint Directly**
   - Visit: `https://sse-server.onrender.com/events?room=lobby`
   - Should see SSE stream in browser
   - Check for connection errors

3. **Verify File Paths**
   - Logs should be in `logs/` directory
   - Frontend should be in `frontend/` directory
   - Check paths are relative to project root

4. **Check Environment Variables**
   - Verify API keys are set correctly
   - Check for typos in variable names
   - Ensure values are correct

---

## Part 9: Maintenance & Updates

### Updating Code

1. Make changes locally
2. Test locally
3. Commit and push to GitHub
4. Render auto-deploys on push
5. Services restart automatically

### Monitoring

- Check Render Dashboard regularly
- Monitor free tier usage (750 hours/month)
- Watch service logs for errors
- Verify services are running

### Scaling Considerations

**If Free Tier Limits Reached:**
- Monitor usage carefully
- Consider optimizing (reduce logging, etc.)
- May need to upgrade to paid tier
- Or use alternative free platform (Fly.io)

**Performance Optimization:**
- Reduce log file size (rotate logs)
- Optimize file watching
- Reduce SSE heartbeat frequency
- Cache static assets

---

## Part 10: Security Considerations

### Environment Variables
- ✅ Never commit API keys to GitHub
- ✅ Use Render's environment variable system
- ✅ Mark sensitive variables as "sync: false" in render.yaml

### CORS Configuration
- ⚠️ Current setup allows all origins (`allow_origins=["*"]`)
- ✅ In production, specify your frontend domain
- ✅ Update CORS settings in `sse_server.py`

### File Access
- ✅ Log files are local to each service
- ✅ No external file access needed
- ✅ File system is isolated per service

### HTTPS/SSL
- ✅ Render provides automatic SSL/HTTPS
- ✅ All connections are encrypted
- ✅ No additional configuration needed

---

## Conclusion

This guide provides complete instructions for deploying the spy agent to Render's free tier. The architecture is simple, cost-effective ($0/month), and scalable.

**Key Points:**
- ✅ All services run on free tier
- ✅ Simple file-based architecture
- ✅ Real-time message streaming via SSE
- ✅ Easy to deploy and maintain
- ✅ Automatic SSL/HTTPS

**Next Steps:**
1. Create the required files (`sse_server.py`, `frontend/`, `requirements.txt`, `render.yaml`)
2. Test locally
3. Deploy to Render
4. Monitor and maintain

**Estimated Time:**
- Implementation: 4-6 hours
- Deployment: 1-2 hours
- Testing: 1 hour
- **Total: 6-9 hours**
