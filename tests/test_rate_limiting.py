#!/usr/bin/env python3
"""
Test script for rate limiting and delay functionality
"""

import sys
import os
import time

# Add parent directory to path to import connect_spy
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.connect_spy import SpyAgent

def test_rate_limiting():
    """Test that rate limiting prevents too many responses"""
    print("=" * 80)
    print("TEST: Rate Limiting")
    print("=" * 80)
    
    agent = SpyAgent()
    
    print(f"\nConfiguration:")
    print(f"  Max responses per minute: {agent.max_responses_per_window}")
    print(f"  Min seconds between responses: {agent.min_seconds_between_responses}")
    print(f"  Rate limit window: {agent.rate_limit_window}s")
    
    # Test 1: Can respond initially
    print(f"\n[Test 1] Initial response check")
    can_respond_1 = agent.can_respond()
    recent_count_1 = agent.get_recent_response_count()
    print(f"  can_respond: {can_respond_1} (expected: True)")
    print(f"  recent_count: {recent_count_1}/{agent.max_responses_per_window}")
    assert can_respond_1 == True, "Should be able to respond initially"
    
    # Simulate a response
    agent.response_times.append(time.time())
    
    # Test 2: Cannot respond immediately after (min delay)
    print(f"\n[Test 2] Immediate second response (should be blocked)")
    can_respond_2 = agent.can_respond()
    recent_count_2 = agent.get_recent_response_count()
    print(f"  can_respond: {can_respond_2} (expected: False)")
    print(f"  recent_count: {recent_count_2}/{agent.max_responses_per_window}")
    print(f"  Time since last: {time.time() - agent.response_times[-1]:.2f}s")
    assert can_respond_2 == False, "Should NOT be able to respond immediately (min delay)"
    
    # Test 3: Fill up to max responses
    print(f"\n[Test 3] Filling up to max responses per window")
    agent.response_times = []
    for i in range(agent.max_responses_per_window):
        agent.response_times.append(time.time() - (agent.max_responses_per_window - i) * 5)  # Spread over time
    
    can_respond_3 = agent.can_respond()
    recent_count_3 = agent.get_recent_response_count()
    print(f"  Added {agent.max_responses_per_window} responses to history")
    print(f"  can_respond: {can_respond_3} (expected: False)")
    print(f"  recent_count: {recent_count_3}/{agent.max_responses_per_window}")
    assert can_respond_3 == False, f"Should NOT be able to respond when at max ({agent.max_responses_per_window})"
    assert recent_count_3 == agent.max_responses_per_window, f"Should have {agent.max_responses_per_window} recent responses"
    
    # Test 4: Can respond after window expires
    print(f"\n[Test 4] Response after window expires")
    agent.response_times = [time.time() - (agent.rate_limit_window + 10)]  # Old response
    can_respond_4 = agent.can_respond()
    recent_count_4 = agent.get_recent_response_count()
    print(f"  Old response: {agent.rate_limit_window + 10}s ago")
    print(f"  can_respond: {can_respond_4} (expected: True)")
    print(f"  recent_count: {recent_count_4}/{agent.max_responses_per_window}")
    assert can_respond_4 == True, "Should be able to respond after window expires"
    assert recent_count_4 < agent.max_responses_per_window, "Recent count should be below max"
    
    # Test 5: Can respond after min delay
    print(f"\n[Test 5] Response after min delay")
    agent.response_times = [time.time() - (agent.min_seconds_between_responses + 5)]
    can_respond_5 = agent.can_respond()
    time_since_last = time.time() - agent.response_times[-1]
    print(f"  Time since last: {time_since_last:.2f}s (min: {agent.min_seconds_between_responses}s)")
    print(f"  can_respond: {can_respond_5} (expected: True)")
    assert can_respond_5 == True, f"Should be able to respond after {agent.min_seconds_between_responses}s"
    
    print("\n" + "=" * 80)
    print("✓ All rate limiting tests passed!")
    print("=" * 80)

def test_delay_configuration():
    """Test that delay configuration is loaded correctly"""
    print("\n" + "=" * 80)
    print("TEST: Delay Configuration")
    print("=" * 80)
    
    agent = SpyAgent()
    config = agent.config.get("response", {})
    
    min_delay = config.get("min_delay_seconds", 0)
    max_delay = config.get("max_delay_seconds", 0)
    
    print(f"\nDelay Configuration:")
    print(f"  min_delay_seconds: {min_delay}")
    print(f"  max_delay_seconds: {max_delay}")
    
    assert min_delay > 0, "min_delay_seconds should be > 0"
    assert max_delay > min_delay, "max_delay_seconds should be > min_delay_seconds"
    
    print(f"\n✓ Delay configuration is valid")
    print("=" * 80)

def test_rate_limit_integration():
    """Test rate limiting with actual message processing"""
    print("\n" + "=" * 80)
    print("TEST: Rate Limit Integration")
    print("=" * 80)
    
    agent = SpyAgent()
    
    # Create test messages
    test_messages = [
        {'room': 'lobby', 'from': 'test1', 'text': 'message 1'},
        {'room': 'lobby', 'from': 'test2', 'text': 'message 2'},
        {'room': 'lobby', 'from': 'test3', 'text': 'message 3'},
    ]
    
    print(f"\nTesting rate limiting with {len(test_messages)} messages:")
    
    responses_allowed = []
    for i, msg in enumerate(test_messages, 1):
        should_respond = agent.should_respond(msg['room'], msg)
        can_respond = agent.can_respond()
        
        print(f"\n  Message {i}:")
        print(f"    should_respond: {should_respond}")
        print(f"    can_respond: {can_respond}")
        
        if should_respond and can_respond:
            responses_allowed.append(i)
            # Simulate response
            agent.response_times.append(time.time())
            print(f"    → Response allowed")
        else:
            if not should_respond:
                print(f"    → Skipped (should_respond=False)")
            if not can_respond:
                print(f"    → Skipped (rate limit)")
    
    print(f"\n  Total responses allowed: {len(responses_allowed)}")
    print(f"  Expected: 1 (due to rate limiting)")
    
    # With rate limiting, only first response should be allowed
    assert len(responses_allowed) <= 1, "Rate limiting should prevent multiple rapid responses"
    
    print(f"\n✓ Rate limit integration test passed")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_rate_limiting()
        test_delay_configuration()
        test_rate_limit_integration()
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
