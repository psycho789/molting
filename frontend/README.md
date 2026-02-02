# Frontend - Local Development

Discord-like chat interface for viewing spy agent messages in real-time.

## Features

- ✅ Real-time message streaming via SSE
- ✅ Room tabs (like Discord channels)
- ✅ Auto-scroll to latest messages
- ✅ Message count badges
- ✅ Connection status indicator
- ✅ Clean, Discord-inspired UI

## Quick Start

### 1. Install Dependencies

Make sure you have the SSE server dependencies installed:

```bash
pip install fastapi uvicorn watchdog
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### 2. Start SSE Server

In one terminal:

```bash
python sse_server.py
```

Server will start on `http://localhost:8000`

### 3. Start Spy Agent

In another terminal:

```bash
python connect_spy.py
```

This will start writing messages to `logs/{room}.log` files.

### 4. Open Frontend

Open `frontend/index.html` in your browser, or visit:

```
http://localhost:8000
```

The SSE server will serve the frontend automatically.

## Usage

1. **Switch Rooms**: Click on room tabs in the sidebar
2. **View Messages**: Messages appear automatically as they come in
3. **Auto-Scroll**: Automatically scrolls to latest messages
4. **Clear Messages**: Click "Clear" button to clear current room

## File Structure

```
frontend/
├── index.html    # Main HTML structure
├── style.css     # Discord-like styling
├── app.js        # JavaScript logic
└── README.md     # This file
```

## Customization

### Change SSE Server URL

Edit `frontend/app.js`:

```javascript
const SSE_SERVER_URL = 'http://localhost:8000'; // Change this
```

### Add More Rooms

1. Add room to `ROOMS` array in `sse_server.py`
2. Add room tab HTML in `index.html`
3. Add room badge element in `index.html`

## Troubleshooting

**No messages appearing:**
- Check that `connect_spy.py` is running
- Check that log files exist in `logs/` directory
- Check browser console for errors
- Verify SSE server is running on port 8000

**Connection errors:**
- Make sure SSE server is running
- Check CORS settings if accessing from different origin
- Check browser console for detailed errors

**Messages not updating:**
- Check file watcher is working (SSE server logs)
- Verify log files are being written to
- Check browser EventSource connection status
