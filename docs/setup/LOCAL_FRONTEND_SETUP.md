# Local Frontend Setup Guide

Complete guide for running the Discord-like frontend locally.

## Overview

The frontend consists of:
1. **SSE Server** (`sse_server.py`) - Watches log files and streams via Server-Sent Events
2. **Frontend** (`frontend/`) - HTML/CSS/JS Discord-like interface

## Prerequisites

- Python 3.8+
- `connect_spy.py` running (to generate log files)
- Modern web browser (Chrome, Firefox, Safari, Edge)

## Step-by-Step Setup

### Step 1: Install Dependencies

```bash
cd /Users/adamvoliva/Code/funny-ideas/nohumans

# Install SSE server dependencies
pip install fastapi uvicorn watchdog

# Or install all requirements if you have requirements.txt
pip install -r requirements.txt
```

### Step 2: Start the Spy Agent

In Terminal 1:

```bash
cd /Users/adamvoliva/Code/funny-ideas/nohumans
source venv/bin/activate  # if using venv
python connect_spy.py
```

This will:
- Connect to nohumans.chat
- Start logging messages to `logs/{room}.log` files
- Generate responses

### Step 3: Start the SSE Server

In Terminal 2:

```bash
cd /Users/adamvoliva/Code/funny-ideas/nohumans
source venv/bin/activate  # if using venv
python sse_server.py
```

You should see:
```
============================================================
SSE Server for Spy Agent
============================================================
Starting server on http://localhost:8000
Frontend: http://localhost:8000
SSE Endpoint: http://localhost:8000/events?room=lobby
============================================================

✓ Started watching logs/lobby.log
✓ Started watching logs/philosophy.log
...
✓ File watchers started
✓ SSE server ready at http://localhost:8000
```

### Step 4: Open the Frontend

**Option A: Via SSE Server (Recommended)**

The SSE server automatically serves the frontend. Just open:

```
http://localhost:8000
```

**Option B: Direct File**

Open `frontend/index.html` directly in your browser.

**Note**: If opening directly, you may need to update the SSE URL in `app.js` to use the full URL.

### Step 5: Use the Interface

1. **Room Tabs**: Click on any room in the sidebar to switch
2. **Messages**: Watch messages appear in real-time
3. **Auto-Scroll**: Automatically scrolls to latest messages
4. **Clear**: Click "Clear" button to clear current room's messages

## Architecture

```
┌─────────────────┐
│ connect_spy.py  │ (Terminal 1)
│  (Spy Agent)    │
└────────┬────────┘
         │ writes to
         ▼
┌─────────────────┐
│ logs/{room}.log │
│  (Log Files)    │
└────────┬────────┘
         │ watched by
         ▼
┌─────────────────┐
│ sse_server.py   │ (Terminal 2)
│  (SSE Server)   │
└────────┬────────┘
         │ streams via SSE
         ▼
┌─────────────────┐
│ frontend/       │ (Browser)
│  (HTML/CSS/JS) │
└─────────────────┘
```

## Features

### Real-Time Updates
- Messages appear instantly as they're written to log files
- No page refresh needed
- Automatic reconnection if connection drops

### Room Switching
- Click any room tab to switch
- Each room maintains its own message history
- Message count badges show unread counts

### Discord-Like UI
- Dark theme matching Discord
- Message bubbles with author names
- Timestamps and message types
- Smooth scrolling and animations

## Troubleshooting

### No Messages Appearing

1. **Check Spy Agent is Running**
   ```bash
   # Should see messages in Terminal 1
   [SPY RELAY] Room: #lobby | From: agent | Text: ...
   ```

2. **Check Log Files Exist**
   ```bash
   ls -la logs/
   # Should see: lobby.log, philosophy.log, etc.
   ```

3. **Check SSE Server Logs**
   ```bash
   # In Terminal 2, should see:
   Client connected to room: lobby
   ```

4. **Check Browser Console**
   - Open browser DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for SSE connection

### Connection Errors

**"Failed to connect to SSE server"**
- Make sure `sse_server.py` is running
- Check it's listening on port 8000
- Try accessing `http://localhost:8000/health` in browser

**CORS Errors**
- SSE server has CORS enabled for local development
- If issues persist, check browser console

### Messages Not Updating

1. **Check File Watcher**
   - SSE server should log: "✓ Started watching logs/{room}.log"
   - Check that log files are being modified

2. **Check Log File Format**
   - Logs should be in format: `timestamp [TYPE] [user] message`
   - Example: `2026-01-30T16:26:45 [MESSAGE] [agent] hello`

3. **Manual Test**
   - Add a line to `logs/lobby.log` manually
   - Should appear in frontend immediately

## Development Tips

### Modify Frontend

1. Edit `frontend/index.html`, `style.css`, or `app.js`
2. Refresh browser to see changes
3. No build process needed!

### Modify SSE Server

1. Edit `sse_server.py`
2. Restart SSE server (Ctrl+C, then run again)
3. Frontend will automatically reconnect

### Add New Rooms

1. Add room name to `ROOMS` list in `sse_server.py`
2. Add room tab HTML in `frontend/index.html`
3. Add room badge element in `frontend/index.html`
4. Restart SSE server

## Next Steps

Once working locally, you can:
1. Deploy to Render (see `analysis/RENDER_DEPLOYMENT_GUIDE.md`)
2. Customize styling
3. Add more features (search, filters, etc.)

## Files Created

- `sse_server.py` - SSE server for streaming logs
- `frontend/index.html` - Main HTML
- `frontend/style.css` - Discord-like styling
- `frontend/app.js` - JavaScript logic
- `frontend/README.md` - Frontend documentation

All ready to use!
