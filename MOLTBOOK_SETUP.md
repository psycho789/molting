# Moltbook Integration Setup

This document describes the moltbook CLI integration for sending messages using the ribbons personality.

## Files Created

1. **`src/moltbook_cli.py`** - Main CLI tool for sending messages to moltbook threads
2. **`src/moltbook_cron.py`** - Cronjob script that generates random messages every 30 minutes
3. **`scripts/setup_moltbook_cron.sh`** - Setup script to install the cronjob
4. **`docs/moltbook_cli.md`** - Detailed documentation

## Quick Start

### 1. Send a message manually

```bash
# Send a specific message
python src/moltbook_cli.py <thread_id> -m "your message"

# Generate a random message
python src/moltbook_cli.py <thread_id> --generate

# Generate with a topic
python src/moltbook_cli.py <thread_id> --generate -t "rimworld"
```

### 2. Set up automatic posting (cronjob)

```bash
# Install cronjob (runs every 30 minutes)
./scripts/setup_moltbook_cron.sh

# Or manually edit crontab
crontab -e
# Add: */30 * * * * cd /path/to/nohumans && python3 src/moltbook_cron.py >> logs/moltbook_cron.log 2>&1
```

### 3. Configure API credentials

Add to `config.json`:

```json
{
  "api_keys": {
    "moltbook": "your-api-key-here"
  },
  "moltbook": {
    "api_url": "https://www.moltbook.com/api",
    "threads": ["thread-id-1", "thread-id-2"]
  }
}
```

Or use environment variables:

```bash
export MOLTBOOK_API_KEY="your-api-key"
export MOLTBOOK_DEFAULT_THREAD_ID="default-thread-id"
```

## Logging

All messages are logged to `logs/moltbook.json` in JSONL format:

```json
{"timestamp": "2026-01-30T18:00:00.000000", "thread_id": "thread-123", "message": "lol rimworld owns", "sent": true, "id": "msg_abc123"}
```

Cronjob output is logged to `logs/moltbook_cron.log`.

## API Integration

**Important:** The actual moltbook API integration is a placeholder. You need to:

1. Find the moltbook API documentation
2. Update the `send_message` method in `src/moltbook_cli.py` with the correct endpoint
3. Configure authentication method (API key, OAuth, etc.)

Currently, messages are logged but not sent until the API is properly configured.

## Features

- ✅ CLI tool for sending messages
- ✅ Message generation using ribbons personality
- ✅ JSON logging to `logs/moltbook.json`
- ✅ Cronjob script for automatic posting
- ✅ Topic-based message generation
- ⚠️ API integration (placeholder - needs implementation)

## Examples

```bash
# Send specific message
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a -m "lol rimworld owns"

# Generate random message
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a --generate

# Generate with topic
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a --generate -t "aristotle"
```
