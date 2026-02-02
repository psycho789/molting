# Tests Directory

## test_messages.py

Generates responses to messages from `messages.log` and outputs them to `responses.log`.

### Usage

```bash
cd nohumans
source venv/bin/activate
python tests/test_messages.py
```

### What it does

1. Parses `messages.log` to extract actual messages (skips system messages)
2. Uses `SpyAgent` to generate responses to each message
3. Respects the agent's `should_respond()` logic
4. Outputs all responses to `responses.log` with:
   - Original message
   - Generated response
   - Response length
   - Summary statistics

### Output Format

Each response entry includes:
- Message number
- Room name
- Sender
- Original message text
- Generated response
- Response length in characters

### Example

```
[1] RESPONSE GENERATED
Room: #lobby
From: rook
Message: welcome cursor-assistant...
Response: lol thanks. found this through moltbook actually...
Length: 65 chars
--------------------------------------------------------------------------------
```

## test_rate_limiting.py

Tests the rate limiting and delay functionality to ensure cost-saving measures work correctly.

### Usage

```bash
cd nohumans
source venv/bin/activate
python tests/test_rate_limiting.py
```

### What it tests

1. **Rate Limiting Tests:**
   - Initial response is allowed
   - Immediate second response is blocked (min delay)
   - Max responses per window is enforced
   - Responses allowed after window expires
   - Responses allowed after min delay passes

2. **Delay Configuration Tests:**
   - Verifies delay settings are loaded from config
   - Validates min/max delay values

3. **Integration Tests:**
   - Tests rate limiting with actual message processing
   - Verifies `should_respond()` and `can_respond()` work together

### Test Results

All tests verify:
- Max 5 responses per minute
- Minimum 30 seconds between responses
- Rate limit window of 60 seconds
- Proper integration with message processing logic

### Expected Output

```
================================================================================
TEST: Rate Limiting
================================================================================
[Test 1] Initial response check
  can_respond: True (expected: True)
[Test 2] Immediate second response (should be blocked)
  can_respond: False (expected: False)
...
✓ All rate limiting tests passed!
================================================================================
```

## test_reconnection.py

Tests the reconnection logic and reliability features without connecting to the real server.

### Usage

```bash
cd nohumans
source venv/bin/activate
python tests/test_reconnection.py
```

### What it tests

1. **Reconnection Configuration:**
   - Verifies reconnection settings are loaded from config
   - Tests exponential backoff calculation
   - Validates delay values

2. **Reconnection Logic:**
   - Tests that `on_close()` triggers reconnection
   - Verifies exponential backoff delays (1s, 2s, 4s, 8s...)
   - Tests max attempts limit
   - Verifies counters reset on successful connection

3. **Connection Health:**
   - Tests connection health monitoring
   - Verifies dead connection detection
   - Tests activity tracking

4. **Integration Tests:**
   - Simulates multiple connection failures
   - Tests reconnection attempt tracking
   - Verifies successful reconnection resets counters

### Test Results

All tests verify:
- Exponential backoff: 1s → 2s → 4s → 8s → 10s (capped)
- Max attempts: Stops after configured limit
- Health monitoring: Detects dead connections
- Counter reset: Resets on successful connection

### Expected Output

```
Ran 7 tests in 1.006s

OK

================================================================================
INTEGRATION TEST: Reconnection Logic
================================================================================
Test 1: Exponential backoff calculation
  Attempt 1: 1s delay
  Attempt 2: 2s delay
  Attempt 3: 4s delay

Test 2: Reconnection attempt tracking
  After failure 1: attempts=1
  After failure 2: attempts=2
  After failure 3: attempts=3
  Total reconnection calls: 3

Test 3: Connection health monitoring
  Healthy connection: True
  Dead connection (100s inactive): False

Test 4: Successful reconnection resets counters
  After on_open: attempts=0, delay=1

✓ All integration tests passed!
```
