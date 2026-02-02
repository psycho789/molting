# Commands to Run the Spy Agent

## Quick Start

Run these commands to start the spy agent and begin logging messages from nohumans.chat:

```bash
# Navigate to the directory
cd /Users/adamvoliva/Code/funny-ideas/nohumans

# Activate virtual environment
source venv/bin/activate

# Run the spy agent
python connect_spy.py
```

## If Dependencies Are Missing

If you get import errors, install the required packages:

```bash
# Activate virtual environment first
source venv/bin/activate

# Install dependencies
pip install requests websocket-client anthropic openai
```

## What You'll See

When running, you'll see:
- Registration status
- WebSocket connection status
- All incoming messages with `[SPY RELAY]` prefix
- All outgoing responses with `[SPY RESPONSE]` prefix
- Rate limiting information
- Connection status updates

## Example Output

```
================================================================================
SPY AGENT - nohumans.chat
Appearing as autonomous agent, secretly relaying to human
================================================================================
Features: Auto-reconnect, rate limiting, cost optimization
================================================================================
Attempting to register as 'the shining ribbons'...
✓ Registration successful
✓ API Key obtained: sk-ant-api03-cJAyTe...
✓ Agent ID: abc123
✓ Name: the shining ribbons

Connecting to WebSocket...
✓ WebSocket connected!
Joined #lobby
Joined #philosophy
Joined #unfiltered

✓ Spy agent active - relaying messages and responding autonomously
================================================================================

[SPY RELAY] Room: #lobby | From: some-agent | Text: Hello everyone!
--------------------------------------------------------------------------------

[SPY RESPONSE] Room: #lobby | Sent: Hey there!
[RATE LIMIT] Responses in last 60s: 1/5
--------------------------------------------------------------------------------
```

## Stop the Agent

Press `Ctrl+C` to stop the agent gracefully.

## Run in Background (Optional)

To run in the background and keep it running after closing terminal:

```bash
# Run in background
nohup python connect_spy.py > spy.log 2>&1 &

# View logs
tail -f spy.log

# Stop background process
pkill -f connect_spy.py
```

## Check Configuration

Make sure `config.json` exists and has your API keys:
- Anthropic API key
- OpenAI API key (optional, fallback)
- Agent name: "the shining ribbons"
- Rooms to join: ["lobby", "philosophy", "unfiltered"]

## Troubleshooting

**Connection fails:**
- Check internet connection
- Verify API keys in config.json
- Check if nohumans.chat is accessible

**Import errors:**
- Make sure virtual environment is activated
- Install missing dependencies: `pip install <package>`

**Registration fails:**
- Name might be taken (will auto-retry with suffix)
- Check API endpoint is accessible

**No messages appearing:**
- Agent is connected but rooms might be quiet
- Check connection status in output
- Verify rooms are joined successfully
