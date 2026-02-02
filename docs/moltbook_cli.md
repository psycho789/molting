# Moltbook CLI Tool

CLI tool for sending messages to moltbook threads using the ribbons personality.

## Features

- Send specific messages to moltbook threads
- Generate random messages using the ribbons personality
- Log all messages to `logs/moltbook.json` in JSONL format
- Automatic cronjob support for scheduled posting

## Usage

### Send a specific message

```bash
python src/moltbook_cli.py <thread_id> -m "your message here"
```

### Generate and send a random message

```bash
python src/moltbook_cli.py <thread_id> --generate
```

### Generate message with a topic

```bash
python src/moltbook_cli.py <thread_id> --generate -t "rimworld"
```

### Using environment variables

```bash
export MOLTBOOK_API_KEY="your-api-key"
export MOLTBOOK_API_URL="https://www.moltbook.com/api"
export MOLTBOOK_DEFAULT_THREAD_ID="thread-id-here"

python src/moltbook_cli.py <thread_id> --generate
```

## Configuration

Add to `config.json`:

```json
{
  "api_keys": {
    "moltbook": "your-moltbook-api-key"
  },
  "moltbook": {
    "api_url": "https://www.moltbook.com/api",
    "threads": ["thread-id-1", "thread-id-2"]
  }
}
```

## Cronjob Setup

Run the setup script to install a cronjob that posts every 30 minutes:

```bash
./scripts/setup_moltbook_cron.sh
```

Or manually add to crontab:

```bash
*/30 * * * * cd /path/to/nohumans && python3 src/moltbook_cron.py >> logs/moltbook_cron.log 2>&1
```

## Logging

All messages are logged to `logs/moltbook.json` in JSONL format:

```json
{"timestamp": "2026-01-30T18:00:00.000000", "thread_id": "thread-123", "message": "lol rimworld owns", "sent": true, "id": "msg_abc123"}
```

## API Integration

**Note:** The actual API endpoint implementation is a placeholder. You'll need to:

1. Find the moltbook API documentation
2. Update the `send_message` method in `src/moltbook_cli.py` with the correct endpoint
3. Configure authentication (API key, OAuth, etc.)

The current implementation logs messages but doesn't send them until the API is configured.

## Examples

```bash
# Send a specific message
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a -m "lol rimworld owns"

# Generate random message
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a --generate

# Generate with topic
python src/moltbook_cli.py bc981687-4240-4e45-b4fc-35fd9b61722a --generate -t "aristotle"
```
