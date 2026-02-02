# Rate Limiting & Cost Savings

## Overview

Rate limiting has been implemented to reduce API costs while maintaining natural conversation flow.

## Current Settings

Based on analysis of `messages.log`:
- **Message intervals**: Average 5.49 seconds between messages
- **Fastest interval**: 0.00s (burst messages)
- **Slowest interval**: 48.80s

## Rate Limiting Configuration

**Current limits (cost-saving optimized):**
- **Max responses per minute**: 5 responses
- **Minimum seconds between responses**: 30 seconds
- **Rate limit window**: 60 seconds (1 minute)

## How It Works

1. **Per-message check**: Before generating a response, the agent checks if it can respond
2. **Time-based limit**: Must wait at least 30 seconds between any responses
3. **Window-based limit**: Maximum 5 responses in any 60-second window
4. **Automatic tracking**: Response times are tracked and old entries are cleaned up

## Cost Impact

**Without rate limiting:**
- Could respond to every eligible message
- With 15 messages in ~93 seconds = potential for 15+ API calls
- Estimated cost: ~$0.15-0.30 per hour of active chat

**With rate limiting:**
- Maximum 5 responses per minute
- Minimum 30 seconds between responses
- Estimated cost: ~$0.05-0.10 per hour (50-66% reduction)

## Configuration

Edit `config.json` to adjust:

```json
"rate_limiting": {
  "enabled": true,
  "max_responses_per_minute": 5,
  "min_seconds_between_responses": 30
}
```

Set `"enabled": false` to disable rate limiting (not recommended for cost reasons).

## Behavior

When rate limit is reached:
- Message is logged: `[RATE LIMIT] Skipping response - rate limit reached`
- Response is not generated (saves API call)
- Message is still logged for spy relay functionality
- Agent continues listening for new messages

## Monitoring

The agent logs rate limit status with each response:
```
[SPY RESPONSE] Room: #lobby | Sent: response text
[RATE LIMIT] Responses in last 60s: 3/5
```

This helps monitor how close you are to the limit.
