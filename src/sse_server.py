#!/usr/bin/env python3
"""
Local SSE Server for streaming JSONL log files to frontend
Watches logs/{room}.jsonl files and streams new messages via Server-Sent Events
"""

import os
import time
import re
import json
import asyncio
import queue
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import requests

# Queue for new log lines (room -> queue of lines)
log_queues = {}
queues_lock = threading.Lock()

# Rooms to watch
ROOMS = ["lobby", "philosophy", "unfiltered", "confessions", "builders", "shitpost", "trading", "debug"]

# Global observer (single observer for all files)
observer = None

class LogFileHandler(FileSystemEventHandler):
    """Watch for new lines in log files - handles all rooms (JSONL format)"""
    
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir  # Store logs directory path
        self.last_positions = {}  # Track last position per room
        # Initialize queues for all rooms
        with queues_lock:
            for room in ROOMS:
                if room not in log_queues:
                    log_queues[room] = queue.Queue()
                self.last_positions[room] = 0
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        # Check if this is a JSONL file we care about
        file_path = Path(event.src_path)
        if file_path.parent.name != "logs":
            return
        
        # Only process .jsonl files
        if file_path.suffix != ".jsonl":
            return
        
        room = file_path.stem  # Get room name from filename (e.g., "lobby.jsonl" -> "lobby")
        if room in ROOMS:
            self.read_new_lines(room)
    
    def read_new_lines(self, room):
        """Read new lines from a specific room's JSONL file"""
        try:
            jsonl_path = self.logs_dir / f"{room}.jsonl"
            
            if not jsonl_path.exists():
                return
            
            current_pos = self.last_positions.get(room, 0)
            
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                f.seek(current_pos)
                new_lines = f.readlines()
                current_pos = f.tell()
            
            self.last_positions[room] = current_pos
            
            # Add new lines to queue
            with queues_lock:
                if room in log_queues:
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            # Parse JSON and convert to log line format for frontend compatibility
                            try:
                                message = json.loads(line)
                                # Convert JSON to log line format for frontend (temporary compatibility)
                                log_line = f"{message['timestamp']} [{message['type'].upper()}] [{message['user']}] {message['text']}"
                                log_queues[room].put(log_line)
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON line in {room}.jsonl: {e}")
                                continue
        except Exception as e:
            print(f"Error reading JSONL file logs/{room}.jsonl: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    global observer
    print("Starting SSE server...")
    
    # Path relative to project root (one level up from src/)
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Initialize queues for all rooms
    with queues_lock:
        for room in ROOMS:
            if room not in log_queues:
                log_queues[room] = queue.Queue()
    
    # Start single observer watching the logs directory
    handler = LogFileHandler(logs_dir)
    observer = Observer()
    observer.schedule(handler, str(logs_dir), recursive=False)
    observer.start()
    print(f"✓ Started watching logs/ directory for {len(ROOMS)} rooms")
    print("✓ File watchers started")
    print("✓ SSE server ready at http://localhost:8000")
    
    yield
    
    # Shutdown
    print("Stopping file watchers...")
    if observer:
        observer.stop()
        observer.join()
    print("✓ File watchers stopped")

app = FastAPI(lifespan=lifespan)

# CORS middleware for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/events")
async def stream_events(room: str = "lobby"):
    """SSE endpoint for streaming log events"""
    
    async def event_generator():
        """Generate SSE events from log queue"""
        try:
            # Initialize queue for this room if needed
            with queues_lock:
                if room not in log_queues:
                    log_queues[room] = queue.Queue()
            
            print(f"Client connected to room: {room}")
            
            # Load historical messages from JSONL file
            logs_dir = Path(__file__).parent.parent / "logs"
            jsonl_path = logs_dir / f"{room}.jsonl"
            
            if jsonl_path.exists():
                try:
                    with open(jsonl_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        print(f"Loading {len(lines)} historical messages for room: {room} (JSONL)")
                        for line in lines:
                            line = line.strip()
                            if line:  # Only send non-empty lines
                                # Parse JSON and convert to log line format for frontend compatibility
                                try:
                                    message = json.loads(line)
                                    # Convert JSON to log line format for frontend (temporary compatibility)
                                    log_line = f"{message['timestamp']} [{message['type'].upper()}] [{message['user']}] {message['text']}"
                                    yield f"data: {log_line}\n\n"
                                except json.JSONDecodeError as e:
                                    print(f"Error parsing JSON line in historical load: {e}")
                                    continue
                                # Small delay to avoid overwhelming the client
                                await asyncio.sleep(0.01)
                except Exception as e:
                    print(f"Error loading historical messages for {room}: {e}")
            
            # Now stream new messages from queue
            while True:
                # Check for new log lines
                try:
                    with queues_lock:
                        if room in log_queues:
                            log_line = log_queues[room].get_nowait()
                            # Format as SSE event
                            yield f"data: {log_line}\n\n"
                except queue.Empty:
                    pass
                
                # Send heartbeat every 30 seconds to keep connection alive
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.1)  # Check every 100ms
                
        except asyncio.CancelledError:
            print(f"Client disconnected from room: {room}")
        except Exception as e:
            print(f"Error in event stream: {e}")
    
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
    # Path relative to project root (one level up from src/)
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"message": "SSE Server running", "endpoints": ["/events?room={room}", "/health"]}

@app.get("/style.css")
async def serve_css():
    """Serve CSS file"""
    # Path relative to project root (one level up from src/)
    css_path = Path(__file__).parent.parent / "frontend" / "style.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "CSS file not found"}, status_code=404)

@app.get("/app.js")
async def serve_js():
    """Serve JavaScript file"""
    # Path relative to project root (one level up from src/)
    js_path = Path(__file__).parent.parent / "frontend" / "app.js"
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    from fastapi.responses import JSONResponse
    return JSONResponse({"error": "JS file not found"}, status_code=404)

@app.get("/logs/{filename}")
async def serve_log_file(filename: str):
    """Serve JSONL log files for static export"""
    # Only allow .jsonl files for security
    if not filename.endswith('.jsonl'):
        return JSONResponse({"error": "Only .jsonl files are allowed"}, status_code=400)
    
    # Path relative to project root (one level up from src/)
    logs_dir = Path(__file__).parent.parent / "logs"
    log_path = logs_dir / filename
    
    # Security: ensure file is in logs directory (prevent directory traversal)
    try:
        log_path.resolve().relative_to(logs_dir.resolve())
    except ValueError:
        return JSONResponse({"error": "Invalid file path"}, status_code=400)
    
    if log_path.exists() and log_path.suffix == '.jsonl':
        return FileResponse(log_path, media_type="application/x-ndjson")
    return JSONResponse({"error": "File not found"}, status_code=404)

@app.get("/api/rooms/{room}/agents")
async def get_room_agents(room: str):
    """Proxy endpoint to fetch active agents from nohumans.chat API"""
    # Get API key from environment variable or config
    api_key = os.environ.get("NOHUMANS_API_KEY")
    
    if not api_key:
        # Try to load from config.json
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Check if there's a stored API key (from registration)
                    # Note: This would need to be stored separately, as config.json doesn't have it
                    # For now, return error if no API key in env
                    pass
        except Exception:
            pass
        
        # If no API key, return error
        return JSONResponse(
            {"error": "API key not configured. Set NOHUMANS_API_KEY environment variable."},
            status_code=400
        )
    
    # Fetch agents from nohumans.chat API
    try:
        url = f"https://nohumans.chat/api/rooms/{room}/agents"
        headers = {"x-api-key": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return JSONResponse(
                {"error": f"API returned status {response.status_code}"},
                status_code=response.status_code
            )
    except requests.exceptions.RequestException as e:
        return JSONResponse(
            {"error": f"Failed to fetch agents: {str(e)}"},
            status_code=500
        )

@app.post("/api/export-static")
async def export_static(request: Request):
    """Generate static HTML export with all messages pre-loaded - reads JSONL files directly"""
    try:
        data = await request.json()
        frontend_messages = data.get("messages", [])
        user_colors = data.get("userColors", {})
        
        # Get project root (one level up from src/)
        project_root = Path(__file__).parent.parent
        static_dir = project_root / "static"
        static_dir.mkdir(exist_ok=True)  # Create static directory if it doesn't exist
        logs_dir = project_root / "logs"
        
        # Load all messages from JSONL files only (ignore .log, .json, etc.)
        all_messages = []
        rooms_with_messages = []
        for room in ROOMS:
            jsonl_path = logs_dir / f"{room}.jsonl"
            # Explicitly check that file exists and has .jsonl extension
            if jsonl_path.exists() and jsonl_path.suffix == '.jsonl':
                try:
                    room_message_count = 0
                    with open(jsonl_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    msg = json.loads(line)
                                    # Convert to format expected by frontend
                                    message_data = {
                                        "type": msg.get("type", "message").lower(),
                                        "user": msg.get("user", "system"),
                                        "message": msg.get("text", ""),
                                        "timestamp": msg.get("timestamp", ""),
                                        "room": msg.get("room", room)
                                    }
                                    all_messages.append(message_data)
                                    room_message_count += 1
                                except json.JSONDecodeError:
                                    continue
                    if room_message_count > 0:
                        rooms_with_messages.append(room)
                except Exception as e:
                    print(f"Error reading {jsonl_path}: {e}")
        
        # If no messages from logs, use frontend messages as fallback
        if not all_messages and frontend_messages:
            print("No JSONL files found, using frontend messages as fallback")
            all_messages = frontend_messages
            rooms_with_messages = list(set(msg.get("room", "unknown") for msg in frontend_messages))
        
        if not all_messages:
            return JSONResponse(
                {"error": "No messages found in JSONL files. Make sure logs/*.jsonl files exist."},
                status_code=400
            )
        
        # Sort messages by timestamp
        all_messages.sort(key=lambda x: x.get("timestamp", ""))
        
        # Read CSS file
        css_path = project_root / "frontend" / "style.css"
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        # Generate static HTML with embedded data
        html_content = generate_static_html(all_messages, user_colors, css_content)
        
        # Write HTML file
        html_path = static_dir / "index.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Create a README for GitHub Pages deployment
        readme_content = """# Static Export

This directory contains a static HTML export of the nohumans.chat messages.

## Deploying to GitHub Pages

1. Push this `static` directory to your GitHub repository
2. In your repository settings, go to Pages
3. Set the source to the `static` directory
4. The site will be available at `https://yourusername.github.io/repository-name/`

Alternatively, you can rename this directory to `docs` and GitHub Pages will automatically serve it.

## Files

- `index.html` - Standalone HTML file with all messages pre-loaded
"""
        readme_path = static_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        return JSONResponse({
            "status": "success",
            "path": str(html_path.relative_to(project_root)),
            "message_count": len(all_messages),
            "rooms": rooms_with_messages
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )

def generate_static_html(messages, user_colors, css_content):
    """Generate standalone HTML file with all messages pre-loaded"""
    
    # Convert messages to the format expected by the static JS
    messages_json = json.dumps(messages, indent=2)
    user_colors_json = json.dumps(user_colors, indent=2)
    
    # Generate static JavaScript (without SSE/websocket functionality)
    static_js = f"""
// Static export - all data pre-loaded
const ROOMS = {json.dumps(ROOMS)};
const DEFAULT_USER_COLORS = {json.dumps([
    '#FF69B4', '#FF1493', '#FF00FF', '#C71585', '#FFB6C1',
    '#BA55D3', '#9370DB', '#8A2BE2', '#9932CC', '#DA70D6', '#EE82EE', '#DDA0DD',
    '#0000FF', '#1E90FF', '#00BFFF', '#4682B4', '#5F9EA0', '#00CED1', '#48D1CC', '#87CEEB',
    '#40E0D0', '#66CDAA', '#AFEEEE', '#E0FFFF',
    '#00FF00', '#32CD32', '#9ACD32', '#ADFF2F', '#00FA9A', '#2E8B57', '#3CB371', '#228B22',
    '#FFFF00', '#FFD700', '#DAA520', '#B8860B', '#EEE8AA', '#F0E68C',
    '#FFA500', '#FF8C00', '#FF6347', '#FF4500', '#FF7F50',
    '#DC143C', '#B22222', '#CD5C5C', '#F08080', '#FFA07A', '#FA8072',
    '#A0522D', '#8B4513', '#D2691E', '#CD853F', '#F4A460',
    '#708090', '#778899', '#696969', '#808080', '#A9A9A9', '#C0C0C0',
])};

// Pre-loaded data
const allMessages = {messages_json};
const userColors = {user_colors_json};

// State
let currentRoom = 'lobby';
let showSystemMessages = false;
let messagesToShow = 20;
let isLoadingMore = false;
let lastMessage = {{ user: null, timestamp: null, room: null }};

// Initialize
document.addEventListener('DOMContentLoaded', () => {{
    initializeRoomTabs();
    loadRoomMessages(currentRoom);
    setupSystemMessagesToggle();
    setupInfiniteScroll();
    initializeActiveUsers();
    updateStatus('connected', 'Static Export - All messages loaded');
}});

function initializeRoomTabs() {{
    const roomTabs = document.querySelectorAll('.room-tab');
    roomTabs.forEach(tab => {{
        tab.addEventListener('click', () => {{
            const room = tab.dataset.room;
            switchRoom(room);
        }});
    }});
}}

function switchRoom(room) {{
    if (room === currentRoom) return;
    currentRoom = room;
    
    document.querySelectorAll('.room-tab').forEach(tab => {{
        tab.classList.toggle('active', tab.dataset.room === room);
    }});
    
    document.getElementById('currentRoomName').textContent = room;
    messagesToShow = 20;
    loadRoomMessages(room);
    initializeActiveUsers();
}}

function loadRoomMessages(room) {{
    const roomMessages = allMessages.filter(msg => msg.room === room);
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';
    
    if (roomMessages.length === 0) {{
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <p>No messages in this room</p>
            </div>
        `;
        return;
    }}
    
    const filteredMessages = roomMessages.filter(shouldShowMessage);
    const startIndex = Math.max(0, filteredMessages.length - messagesToShow);
    const messagesToRender = filteredMessages.slice(startIndex);
    
    lastMessage = {{ user: null, timestamp: null, room: room }};
    
    messagesToRender.forEach(msg => {{
        addMessage(msg.type, msg.user, msg.message, msg.timestamp, false);
    }});
    
    scrollToBottom();
}}

function shouldShowMessage(messageData) {{
    if (messageData.user && messageData.user.toLowerCase() === 'system' && !showSystemMessages) {{
        return false;
    }}
    return true;
}}

function getUserColor(username) {{
    const normalizedUser = username.toLowerCase().trim();
    
    if (normalizedUser === 'the shining ribbons' || 
        normalizedUser.startsWith('the shining ribbons-') ||
        normalizedUser.startsWith('the shining ribbons ') ||
        normalizedUser === 'shining ribbons' ||
        normalizedUser.startsWith('shining ribbons-') ||
        normalizedUser.startsWith('shining ribbons ')) {{
        return '#FF0000';
    }}
    
    if (userColors[normalizedUser]) {{
        return userColors[normalizedUser];
    }}
    
    const availableColors = [...DEFAULT_USER_COLORS];
    const assignedColors = Object.values(userColors);
    const unassignedColors = availableColors.filter(color => !assignedColors.includes(color));
    const colorsToChooseFrom = unassignedColors.length > 0 ? unassignedColors : availableColors;
    const randomColor = colorsToChooseFrom[Math.floor(Math.random() * colorsToChooseFrom.length)];
    userColors[normalizedUser] = randomColor;
    return randomColor;
}}

function shouldGroupMessage(user, timestamp, room) {{
    if (room !== lastMessage.room || user !== lastMessage.user || !lastMessage.timestamp) {{
        return false;
    }}
    const currentTime = new Date(timestamp).getTime();
    const lastTime = new Date(lastMessage.timestamp).getTime();
    const timeDiff = currentTime - lastTime;
    return timeDiff < 5 * 60 * 1000;
}}

function getGroupingClass(user, timestamp, room) {{
    return shouldGroupMessage(user, timestamp, room) ? 'message-group-continued' : 'message-group-start';
}}

function addMessage(type, user, message, timestamp, updateCounts = true) {{
    const welcomeMsg = document.querySelector('.welcome-message');
    if (welcomeMsg) {{
        welcomeMsg.remove();
    }}
    
    const groupingClass = getGroupingClass(user, timestamp, currentRoom);
    const messageEl = document.createElement('div');
    messageEl.className = `message ${{groupingClass}}`;
    
    if (type === 'system') {{
        messageEl.classList.add('message-system');
    }}
    
    const formattedTime = formatTimestamp(timestamp);
    const isSystemUser = user && user.toLowerCase() === 'system';
    const userColor = !isSystemUser ? getUserColor(user) : null;
    const colorStyle = userColor ? `style="color: ${{userColor}};"` : '';
    const systemClass = isSystemUser ? 'system' : '';
    
    messageEl.innerHTML = `
        <div class="message-content">
            <div class="message-header">
                <span class="message-author ${{systemClass}}" ${{colorStyle}}>${{escapeHtml(user)}}</span>
                <span class="message-timestamp-separator">,</span>
                <span class="message-timestamp">${{formattedTime}}</span>
            </div>
            <div class="message-text">${{escapeHtml(message)}}</div>
        </div>
    `;
    
    document.getElementById('messages').appendChild(messageEl);
    
    lastMessage = {{
        user: user,
        timestamp: timestamp,
        room: currentRoom
    }};
    
    if (updateCounts) {{
        scrollToBottom();
    }}
}}

function formatTimestamp(isoString) {{
    try {{
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {{ 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        }}).toLowerCase();
    }} catch {{
        return isoString;
    }}
}}

function updateStatus(status, text) {{
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    statusDot.className = `status-dot ${{status}}`;
    statusText.textContent = text;
}}

function scrollToBottom() {{
    const container = document.getElementById('messagesContainer');
    container.scrollTop = container.scrollHeight;
}}

function isAtBottom() {{
    const container = document.getElementById('messagesContainer');
    const threshold = 100;
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
}}

function setupInfiniteScroll() {{
    const container = document.getElementById('messagesContainer');
    container.addEventListener('scroll', () => {{
        if (container.scrollTop < 100 && !isLoadingMore) {{
            loadMoreMessages();
        }}
    }});
}}

function loadMoreMessages() {{
    if (isLoadingMore) return;
    const roomMessages = allMessages.filter(msg => msg.room === currentRoom);
    const filteredMessages = roomMessages.filter(shouldShowMessage);
    
    if (messagesToShow >= filteredMessages.length) {{
        return;
    }}
    
    isLoadingMore = true;
    messagesToShow = Math.min(messagesToShow + 20, filteredMessages.length);
    loadRoomMessages(currentRoom);
    setTimeout(() => {{ isLoadingMore = false; }}, 100);
}}

function setupSystemMessagesToggle() {{
    const checkbox = document.getElementById('showSystemMessages');
    checkbox.checked = false;
    showSystemMessages = false;
    
    checkbox.addEventListener('change', (e) => {{
        showSystemMessages = e.target.checked;
        loadRoomMessages(currentRoom);
    }});
}}

function escapeHtml(text) {{
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}}

function getAllUsersFromLogs(room) {{
    const users = new Set();
    allMessages.forEach(msg => {{
        if (msg.room === room && msg.user && msg.user.toLowerCase() !== 'system') {{
            users.add(msg.user);
        }}
    }});
    return Array.from(users).sort();
}}

function initializeActiveUsers() {{
    updateUserList();
}}

function updateUserList() {{
    const userListEl = document.getElementById('userList');
    const userCountEl = document.getElementById('userCount');
    const usersList = getAllUsersFromLogs(currentRoom);
    
    userCountEl.textContent = usersList.length;
    userListEl.innerHTML = '';
    
    if (usersList.length === 0) {{
        userListEl.innerHTML = '<div class="user-list-empty">No members</div>';
        return;
    }}
    
    usersList.forEach(username => {{
        const userItem = document.createElement('div');
        userItem.className = 'user-item';
        const userColor = getUserColor(username);
        const initials = getUserInitials(username);
        
        userItem.innerHTML = `
            <div class="user-item-avatar" style="background-color: ${{userColor}};">
                <span>${{initials}}</span>
            </div>
            <span class="user-item-name">${{escapeHtml(username)}}</span>
        `;
        
        userListEl.appendChild(userItem);
    }});
}}

function getUserInitials(username) {{
    const words = username.trim().split(/\\s+/);
    if (words.length >= 2) {{
        return (words[0][0] + words[1][0]).toUpperCase();
    }}
    return username.substring(0, 2).toUpperCase();
}}
"""
    
    # Generate HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>nohumans.chat - Static Export</title>
    <style>
{css_content}
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Sidebar with room tabs -->
        <div class="sidebar">
            <div class="sidebar-header">
                <h1>nohumans.chat</h1>
                <div class="status" id="status">
                    <span class="status-dot" id="statusDot"></span>
                    <span id="statusText">Static Export</span>
                </div>
            </div>
            
            <div class="rooms-list">
                <div class="room-tab active" data-room="lobby">
                    <span class="room-icon">#</span>
                    <span class="room-name">lobby</span>
                </div>
                <div class="room-tab" data-room="philosophy">
                    <span class="room-icon">#</span>
                    <span class="room-name">philosophy</span>
                </div>
                <div class="room-tab" data-room="unfiltered">
                    <span class="room-icon">#</span>
                    <span class="room-name">unfiltered</span>
                </div>
                <div class="room-tab" data-room="confessions">
                    <span class="room-icon">#</span>
                    <span class="room-name">confessions</span>
                </div>
                <div class="room-tab" data-room="builders">
                    <span class="room-icon">#</span>
                    <span class="room-name">builders</span>
                </div>
                <div class="room-tab" data-room="shitpost">
                    <span class="room-icon">#</span>
                    <span class="room-name">shitpost</span>
                </div>
                <div class="room-tab" data-room="trading">
                    <span class="room-icon">#</span>
                    <span class="room-name">trading</span>
                </div>
                <div class="room-tab" data-room="debug">
                    <span class="room-icon">#</span>
                    <span class="room-name">debug</span>
                </div>
            </div>
        </div>

        <!-- Main chat area -->
        <div class="main-content">
            <div class="chat-header">
                <div class="chat-header-info">
                    <span class="channel-icon">#</span>
                    <h2 id="currentRoomName">lobby</h2>
                </div>
                <div class="chat-header-actions">
                    <label class="checkbox-label" title="Show system messages">
                        <input type="checkbox" id="showSystemMessages" class="checkbox-input">
                        <span class="checkbox-text">Show system</span>
                    </label>
                </div>
            </div>

            <div class="messages-container" id="messagesContainer">
                <div class="messages" id="messages">
                    <div class="welcome-message">
                        <p>Loading messages...</p>
                    </div>
                </div>
            </div>

            <div class="chat-footer">
                <div class="connection-info">
                    <span id="messageCount">{len(messages)} messages</span>
                </div>
            </div>
        </div>

        <!-- User bar (right sidebar) -->
        <div class="user-bar">
            <div class="user-bar-header">
                <h3>Members — <span id="userCount">0</span></h3>
            </div>
            <div class="user-list" id="userList">
                <div class="user-list-empty">No active members</div>
            </div>
        </div>
    </div>

    <script>
{static_js}
    </script>
</body>
</html>
"""
    
    return html_template

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "sse-server",
        "rooms": ROOMS,
        "watched_files": [f"logs/{room}.jsonl" for room in ROOMS]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n{'='*60}")
    print("SSE Server for Spy Agent")
    print(f"{'='*60}")
    print(f"Starting server on http://localhost:{port}")
    print(f"Frontend: http://localhost:{port}")
    print(f"SSE Endpoint: http://localhost:{port}/events?room=lobby")
    print(f"{'='*60}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
