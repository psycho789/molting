#!/usr/bin/env python3
"""
Test critical issues found in pre-connection analysis
"""

import sys
import os
import unittest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.connect_spy import SpyAgent

class TestCriticalIssues(unittest.TestCase):
    def setUp(self):
        self.mock_config = {
            "api_keys": {"anthropic": "test-key"},
            "models": {"claude_model": "test", "max_tokens": {"text": 2000}},
            "agent": {"name": "test-agent", "rooms": ["lobby"]},
            "response": {"max_context_messages": 10, "rate_limiting": {"enabled": False}},
            "reconnection": {"enabled": False}
        }
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_api_response_empty_content(self, mock_personality, mock_ai, mock_config):
        """Test handling of empty API response content"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.anthropic_client = Mock()
        
        # Mock empty content response
        mock_response = Mock()
        mock_response.content = []  # Empty list
        
        agent.anthropic_client.messages.create = Mock(return_value=mock_response)
        
        # Should handle gracefully
        result = agent.generate_response('lobby', {'from': 'test', 'text': 'hello'})
        
        # Should return None or handle error
        # Currently will raise IndexError - this is the bug!
        # Let's see what happens
        try:
            result = agent.generate_response('lobby', {'from': 'test', 'text': 'hello'})
            # If we get here, it handled it (good)
            # If IndexError, that's the bug
        except IndexError:
            self.fail("IndexError on empty response content - needs fix!")
        except Exception as e:
            # Other exceptions are okay, just not IndexError
            pass
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_empty_response_filtering(self, mock_personality, mock_ai, mock_config):
        """Test that empty/whitespace responses are filtered"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        # Test process_response with empty/whitespace
        empty_result = agent.process_response("   ")
        whitespace_result = agent.process_response("\n\n\t")
        
        # Should return empty string
        self.assertEqual(empty_result, "")
        self.assertEqual(whitespace_result, "")
        
        # Empty responses should not be sent
        # This is checked in generate_response with `if response_text:`
        # So empty strings should be filtered
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    @patch('connect_spy.requests.post')
    def test_registration_max_retries(self, mock_post, mock_personality, mock_ai, mock_config):
        """Test that registration doesn't retry infinitely"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        # Simulate repeated 409 errors
        mock_response = Mock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"error": "name taken"}
        mock_post.return_value = mock_response
        
        # This could theoretically retry forever
        # Need to add max retry counter
        # For now, just verify it doesn't crash
        try:
            result = agent.register()
            # Should eventually give up or succeed
        except RecursionError:
            self.fail("Registration retries infinitely - needs max retry limit!")
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_empty_personality(self, mock_personality, mock_ai, mock_config):
        """Test behavior with empty personality file"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = ""  # Empty personality
        mock_ai.return_value = None
        
        agent = SpyAgent()
        
        prompt = agent.get_spy_system_prompt('lobby')
        
        # Should handle empty personality gracefully
        # Currently returns empty string - might want to warn or use default
        self.assertIsInstance(prompt, str)
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_malformed_message_handling(self, mock_personality, mock_ai, mock_config):
        """Test handling of malformed WebSocket messages"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        mock_ws = Mock()
        
        # Test various malformed messages
        test_cases = [
            "",  # Empty
            "not json",  # Invalid JSON
            '{"type": "message"}',  # Missing fields
            '{"type": "message", "room": null}',  # Null room
            '{"type": "message", "room": "", "from": "", "text": ""}',  # Empty fields
        ]
        
        for msg in test_cases:
            try:
                agent.on_message(mock_ws, msg)
                # Should not crash
            except Exception as e:
                # Some exceptions are okay (JSON decode), but shouldn't crash the agent
                if isinstance(e, (json.JSONDecodeError, KeyError, AttributeError)):
                    pass  # Expected for malformed messages
                else:
                    self.fail(f"Unexpected exception for message '{msg}': {e}")
    
    @patch('connect_spy.SpyAgent.load_config')
    @patch('connect_spy.SpyAgent.init_ai_clients')
    @patch('connect_spy.SpyAgent.load_personality')
    def test_room_name_validation(self, mock_personality, mock_ai, mock_config):
        """Test handling of invalid room names"""
        mock_config.return_value = self.mock_config
        mock_personality.return_value = "test"
        mock_ai.return_value = None
        
        agent = SpyAgent()
        agent.connected = True
        agent.ws = Mock()
        
        # Test sending to invalid room
        invalid_rooms = [None, "", "invalid-room-name", "room with spaces"]
        
        for room in invalid_rooms:
            try:
                agent.send_message(room, "test")
                # Should handle gracefully
            except Exception as e:
                # Should not crash, but might fail to send (which is okay)
                pass

def run_analysis_summary():
    """Print summary of critical issues"""
    print("=" * 80)
    print("CRITICAL ISSUES ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    
    issues = [
        {
            "priority": "HIGH",
            "issue": "API Response Validation",
            "location": "generate_response() lines 333, 347",
            "problem": "No check if response.content or response.choices is empty",
            "impact": "IndexError crash on unexpected API response"
        },
        {
            "priority": "MEDIUM",
            "issue": "Registration Retry Loop",
            "location": "register() line 153",
            "problem": "Recursive retry with no max limit",
            "impact": "Could theoretically retry forever"
        },
        {
            "priority": "MEDIUM",
            "issue": "Empty Response Filtering",
            "location": "generate_response() → process_response()",
            "problem": "Empty/whitespace responses might be sent",
            "impact": "Could send empty messages"
        },
        {
            "priority": "MEDIUM",
            "issue": "Thread Safety",
            "location": "All callback methods",
            "problem": "Shared state modified without locks",
            "impact": "Race conditions possible"
        },
        {
            "priority": "LOW",
            "issue": "Empty Personality",
            "location": "load_personality()",
            "problem": "No validation that personality is not empty",
            "impact": "Agent has no personality instructions"
        }
    ]
    
    print("Issues Found:")
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. [{issue['priority']}] {issue['issue']}")
        print(f"   Location: {issue['location']}")
        print(f"   Problem: {issue['problem']}")
        print(f"   Impact: {issue['impact']}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION: Fix HIGH priority issues before connecting")
    print("=" * 80)

if __name__ == "__main__":
    print("Running critical issues tests...")
    print()
    
    # Run tests
    unittest.main(argv=[''], exit=False, verbosity=1)
    
    print()
    print()
    
    # Print analysis summary
    run_analysis_summary()
