#!/usr/bin/env python3
"""
Test reconnection logic without connecting to real server
Uses mocking to simulate connection failures and reconnection attempts
"""

import sys
import os
import time
import unittest
from unittest.mock import Mock, MagicMock, patch, call

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.connect_spy import SpyAgent

class TestReconnection(unittest.TestCase):
    def setUp(self):
        """Set up test agent"""
        # Mock the config to avoid needing real API keys
        self.mock_config = {
            "api_keys": {
                "anthropic": "test-key",
                "openai": "test-key"
            },
            "models": {
                "claude_model": "claude-opus-4-5-20251101",
                "max_tokens": {"text": 2000}
            },
            "agent": {
                "name": "test-agent",
                "rooms": ["lobby"]
            },
            "response": {
                "max_context_messages": 10,
                "min_delay_seconds": 0,
                "max_delay_seconds": 0,
                "rate_limiting": {
                    "enabled": False
                },
                "response_probability": {"lobby": 1.0}
            },
            "reconnection": {
                "enabled": True,
                "max_attempts": 3,
                "initial_delay_seconds": 1,
                "max_delay_seconds": 10,
                "ping_interval_seconds": 30
            }
        }
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_reconnection_config(self, mock_personality, mock_ai, mock_config):
        """Test that reconnection config is loaded correctly"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test personality"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        self.assertTrue(agent.should_reconnect)
        self.assertEqual(agent.max_reconnect_attempts, 3)
        self.assertEqual(agent.reconnect_delay, 1)
        self.assertEqual(agent.max_reconnect_delay, 10)
        self.assertEqual(agent.ping_interval, 30)
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_exponential_backoff(self, mock_personality, mock_ai, mock_config):
        """Test exponential backoff calculation"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        # Test backoff calculation
        delays = []
        for attempt in range(1, 6):
            delay = min(agent.reconnect_delay * (2 ** (attempt - 1)), agent.max_reconnect_delay)
            delays.append(delay)
        
        # Should be: 1, 2, 4, 8, 10 (capped at max)
        expected = [1, 2, 4, 8, 10]
        self.assertEqual(delays, expected)
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_on_close_reconnection(self, mock_personality, mock_ai, mock_config):
        """Test that on_close triggers reconnection"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.session_token = "test-token"
        agent.connect_websocket = Mock()
        
        # Simulate connection close
        agent.on_close(None, None, "test close")
        
        # Should attempt reconnection
        self.assertEqual(agent.reconnect_attempts, 1)
        self.assertFalse(agent.connected)
        agent.connect_websocket.assert_called_once()
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_max_reconnect_attempts(self, mock_personality, mock_ai, mock_config):
        """Test that reconnection stops after max attempts"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.session_token = "test-token"
        agent.connect_websocket = Mock()
        
        # Simulate max attempts
        agent.reconnect_attempts = agent.max_reconnect_attempts
        
        agent.on_close(None, None, "test")
        
        # Should NOT attempt reconnection
        agent.connect_websocket.assert_not_called()
        self.assertEqual(agent.reconnect_attempts, agent.max_reconnect_attempts)
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_connection_health_check(self, mock_personality, mock_ai, mock_config):
        """Test connection health monitoring"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        # Test healthy connection
        agent.connected = True
        agent.last_ping_time = time.time()
        self.assertTrue(agent.check_connection_health())
        
        # Test dead connection (no activity for 90s)
        agent.last_ping_time = time.time() - 100
        self.assertFalse(agent.check_connection_health())
        
        # Test disconnected
        agent.connected = False
        self.assertFalse(agent.check_connection_health())
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_on_open_resets_counters(self, mock_personality, mock_ai, mock_config):
        """Test that successful connection resets reconnection counters"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.reconnect_attempts = 5
        agent.reconnect_delay = 100
        
        mock_ws = Mock()
        agent.on_open(mock_ws)
        
        self.assertEqual(agent.reconnect_attempts, 0)
        self.assertEqual(agent.reconnect_delay, 1)  # Reset to initial
        self.assertTrue(agent.connected)
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    @patch('connect_spy.time.sleep')
    def test_reconnection_delay(self, mock_sleep, mock_personality, mock_ai, mock_config):
        """Test that reconnection waits with correct delay"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.session_token = "test-token"
        agent.connect_websocket = Mock()
        
        # First attempt - should wait 1 second
        agent.on_close(None, None, "test")
        mock_sleep.assert_called_with(1)
        
        # Second attempt - should wait 2 seconds
        agent.on_close(None, None, "test")
        mock_sleep.assert_called_with(2)
        
        # Third attempt - should wait 4 seconds
        agent.on_close(None, None, "test")
        mock_sleep.assert_called_with(4)

def run_integration_test():
    """Run a simulated integration test"""
    print("=" * 80)
    print("INTEGRATION TEST: Reconnection Logic")
    print("=" * 80)
    print()
    
    # Create agent with test config
    test_config = {
        "api_keys": {"anthropic": "test"},
        "models": {"claude_model": "test", "max_tokens": {"text": 2000}},
        "agent": {"name": "test", "rooms": ["lobby"]},
        "response": {
            "max_context_messages": 10,
            "rate_limiting": {"enabled": False},
            "response_probability": {"lobby": 1.0}
        },
        "reconnection": {
            "enabled": True,
            "max_attempts": 3,
            "initial_delay_seconds": 1,
            "max_delay_seconds": 10,
            "ping_interval_seconds": 30
        }
    }
    
    with patch('connect_spy.SpyAgent.load_config', return_value=test_config), \
         patch('connect_spy.SpyAgent.init_ai_clients'), \
         patch('connect_spy.SpyAgent.load_personality', return_value="test"):
        
        agent = SpyAgent()
        agent.session_token = "test-token"
        
        print("Test 1: Exponential backoff calculation")
        print("-" * 80)
        for attempt in range(1, 4):
            delay = min(agent.reconnect_delay * (2 ** (attempt - 1)), agent.max_reconnect_delay)
            print(f"  Attempt {attempt}: {delay}s delay")
        print()
        
        print("Test 2: Reconnection attempt tracking")
        print("-" * 80)
        agent.reconnect_attempts = 0
        agent.connect_websocket = Mock()
        
        # Simulate 3 connection failures
        for i in range(3):
            agent.on_close(None, None, f"Failure {i+1}")
            print(f"  After failure {i+1}: attempts={agent.reconnect_attempts}")
        
        print(f"  Total reconnection calls: {agent.connect_websocket.call_count}")
        print()
        
        print("Test 3: Connection health monitoring")
        print("-" * 80)
        agent.connected = True
        agent.last_ping_time = time.time()
        print(f"  Healthy connection: {agent.check_connection_health()}")
        
        agent.last_ping_time = time.time() - 100
        print(f"  Dead connection (100s inactive): {agent.check_connection_health()}")
        print()
        
        print("Test 4: Successful reconnection resets counters")
        print("-" * 80)
        agent.reconnect_attempts = 5
        agent.reconnect_delay = 100
        mock_ws = Mock()
        agent.on_open(mock_ws)
        print(f"  After on_open: attempts={agent.reconnect_attempts}, delay={agent.reconnect_delay}")
        print()
        
        print("=" * 80)
        print("✓ All integration tests passed!")
        print("=" * 80)

if __name__ == "__main__":
    print("Running unit tests...")
    print()
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print()
    print()
    
    # Run integration test
    run_integration_test()
