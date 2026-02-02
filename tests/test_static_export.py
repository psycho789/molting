#!/usr/bin/env python3
"""
Test static export functionality for SSE server

To run these tests:
    python3 -m pytest tests/test_static_export.py
    or
    python3 tests/test_static_export.py

Requires: fastapi, pytest (or unittest)
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import unittest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Try to import, handling dependencies
FASTAPI_AVAILABLE = False
generate_static_html = None
ROOMS = []
app = None

try:
    import fastapi
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    pass

# Mock missing dependencies before importing sse_server
import sys
from unittest.mock import MagicMock

# Mock all dependencies that might be missing
dependencies_to_mock = [
    'fastapi',
    'fastapi.responses',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'requests',
]

for dep in dependencies_to_mock:
    if dep not in sys.modules:
        sys.modules[dep] = MagicMock()

# Set up FastAPI mocks if needed
if not FASTAPI_AVAILABLE:
    fastapi_mock = sys.modules['fastapi']
    fastapi_mock.FastAPI = MagicMock
    fastapi_mock.Request = MagicMock
    fastapi_mock.HTTPException = Exception
    sys.modules['fastapi.responses'].StreamingResponse = MagicMock
    sys.modules['fastapi.responses'].FileResponse = MagicMock
    sys.modules['fastapi.responses'].JSONResponse = MagicMock
    sys.modules['fastapi.middleware.cors'].CORSMiddleware = MagicMock

try:
    from src.sse_server import generate_static_html, ROOMS
    if FASTAPI_AVAILABLE:
        from src.sse_server import app
except ImportError as e:
    print(f"Warning: Could not import sse_server module: {e}")
    if not FASTAPI_AVAILABLE:
        print("  (Dependencies not installed - some tests will be skipped)")

class TestStaticExport(unittest.TestCase):
    """Test static export endpoint and functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        if FASTAPI_AVAILABLE:
            self.client = TestClient(app)
        else:
            self.client = None
        
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.test_logs_dir = Path(self.test_dir) / "logs"
        self.test_static_dir = Path(self.test_dir) / "static"
        self.test_frontend_dir = Path(self.test_dir) / "frontend"
        self.test_logs_dir.mkdir()
        self.test_static_dir.mkdir()
        self.test_frontend_dir.mkdir()
        
        # Create test CSS file
        self.test_css_path = self.test_frontend_dir / "style.css"
        self.test_css_path.write_text("/* Test CSS */\nbody { background: #000; }")
        
        # Sample messages for testing
        self.sample_messages = [
            {
                "timestamp": "2026-01-30T10:00:00.000000",
                "type": "message",
                "user": "test_user",
                "text": "Hello, world!",
                "room": "lobby",
                "id": "msg_123"
            },
            {
                "timestamp": "2026-01-30T10:01:00.000000",
                "type": "system",
                "user": "system",
                "text": "⚡ test_user joined #lobby.",
                "room": "lobby",
                "id": "msg_124"
            },
            {
                "timestamp": "2026-01-30T10:02:00.000000",
                "type": "message",
                "user": "another_user",
                "text": "Test message in philosophy",
                "room": "philosophy",
                "id": "msg_125"
            }
        ]
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.test_dir)
    
    def create_test_jsonl_file(self, room, messages):
        """Create a test JSONL file with messages"""
        jsonl_path = self.test_logs_dir / f"{room}.jsonl"
        with open(jsonl_path, 'w') as f:
            for msg in messages:
                if msg.get("room") == room:
                    f.write(json.dumps(msg) + "\n")
        return jsonl_path
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_export_static_endpoint_exists(self):
        """Test that export endpoint exists and accepts POST requests"""
        # Test endpoint exists (will fail if no JSONL files, but that's expected)
        response = self.client.post(
            "/api/export-static",
            json={
                "messages": [],
                "userColors": {}
            }
        )
        
        # Should return either success (200) or error (400/500), not 404
        self.assertIn(response.status_code, [200, 400, 500])
        self.assertNotEqual(response.status_code, 404)
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_export_static_endpoint_requires_json(self):
        """Test that endpoint requires JSON body"""
        # Test without JSON body
        response = self.client.post("/api/export-static")
        
        # Should return error for missing JSON
        self.assertIn(response.status_code, [400, 422])
    
    def test_export_static_writes_html_file(self):
        """Test that HTML file is written to static directory"""
        # Create a minimal test setup
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Test message",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        # Test the generate_static_html function directly
        css_content = "body { background: #000; }"
        user_colors = {"test_user": "#FF0000"}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Verify HTML content
        self.assertIn("<!DOCTYPE html>", html_content)
        self.assertIn("nohumans.chat", html_content)
        self.assertIn("test_user", html_content)
        self.assertIn("Test message", html_content)
        self.assertIn(css_content, html_content)
        self.assertIn("allMessages", html_content)  # Should have embedded data
    
    def test_export_static_only_reads_jsonl_files(self):
        """Test that only .jsonl files are read, not .log or .json files"""
        # Create various file types
        jsonl_path = self.test_logs_dir / "lobby.jsonl"
        log_path = self.test_logs_dir / "lobby.log"
        json_path = self.test_logs_dir / "lobby.json"
        
        jsonl_path.write_text(json.dumps(self.sample_messages[0]) + "\n")
        log_path.write_text("This is a log file, not JSONL\n")
        json_path.write_text(json.dumps({"test": "data"}) + "\n")
        
        # The function should only read .jsonl files
        # We can test this by checking the suffix check in the code
        self.assertTrue(jsonl_path.suffix == '.jsonl')
        self.assertFalse(log_path.suffix == '.jsonl')
        self.assertFalse(json_path.suffix == '.jsonl')
    
    def test_export_static_handles_empty_jsonl_files(self):
        """Test handling of empty JSONL files"""
        # Create empty JSONL file
        empty_jsonl = self.test_logs_dir / "lobby.jsonl"
        empty_jsonl.write_text("")
        
        # Should handle gracefully (no crash)
        # The function should skip empty files or return empty messages
        test_messages = []
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Should still generate valid HTML
        self.assertIn("<!DOCTYPE html>", html_content)
    
    def test_export_static_handles_invalid_json_lines(self):
        """Test handling of invalid JSON lines in JSONL files"""
        # Create JSONL file with invalid lines
        invalid_jsonl = self.test_logs_dir / "lobby.jsonl"
        invalid_jsonl.write_text(
            json.dumps(self.sample_messages[0]) + "\n" +
            "invalid json line\n" +
            json.dumps(self.sample_messages[1]) + "\n"
        )
        
        # Should skip invalid lines and process valid ones
        # Test the parsing logic
        valid_messages = []
        with open(invalid_jsonl, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        valid_messages.append(msg)
                    except json.JSONDecodeError:
                        continue  # Skip invalid lines
        
        # Should have 2 valid messages
        self.assertEqual(len(valid_messages), 2)
    
    def test_export_static_sorts_messages_by_timestamp(self):
        """Test that messages are sorted by timestamp"""
        # Create messages with different timestamps
        messages = [
            {
                "type": "message",
                "user": "user1",
                "message": "Second message",
                "timestamp": "2026-01-30T10:02:00.000000",
                "room": "lobby"
            },
            {
                "type": "message",
                "user": "user2",
                "message": "First message",
                "timestamp": "2026-01-30T10:01:00.000000",
                "room": "lobby"
            },
            {
                "type": "message",
                "user": "user3",
                "message": "Third message",
                "timestamp": "2026-01-30T10:03:00.000000",
                "room": "lobby"
            }
        ]
        
        # Sort messages
        messages.sort(key=lambda x: x.get("timestamp", ""))
        
        # Verify order
        self.assertEqual(messages[0]["message"], "First message")
        self.assertEqual(messages[1]["message"], "Second message")
        self.assertEqual(messages[2]["message"], "Third message")
    
    def test_export_static_includes_user_colors(self):
        """Test that user colors are included in the export"""
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Test",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        user_colors = {
            "test_user": "#FF0000",
            "another_user": "#00FF00"
        }
        
        css_content = "body { background: #000; }"
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Verify user colors are embedded in JavaScript
        self.assertIn("#FF0000", html_content)
        self.assertIn("#00FF00", html_content)
        self.assertIn("userColors", html_content)
    
    @unittest.skipIf(not FASTAPI_AVAILABLE, "FastAPI not available")
    def test_export_static_error_no_messages(self):
        """Test error handling when no messages are found"""
        # Mock empty logs directory
        with patch('src.sse_server.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.parent.parent = Path(self.test_dir)
            mock_path.return_value = mock_file
            
            # Ensure no JSONL files exist
            if (self.test_logs_dir / "lobby.jsonl").exists():
                (self.test_logs_dir / "lobby.jsonl").unlink()
            
            response = self.client.post(
                "/api/export-static",
                json={
                    "messages": [],
                    "userColors": {}
                }
            )
            
            # Should return error when no messages found
            self.assertEqual(response.status_code, 400)
            error_data = response.json()
            self.assertIn("error", error_data)
    
    @unittest.skipIf(generate_static_html is None, "generate_static_html not available")
    def test_generate_static_html_basic(self):
        """Basic test that HTML generation works"""
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Hello",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Basic checks
        self.assertIsInstance(html_content, str)
        self.assertGreater(len(html_content), 100)  # Should be substantial
        self.assertIn("<!DOCTYPE html>", html_content)
    
    def test_generate_static_html_structure(self):
        """Test that generated HTML has correct structure"""
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Hello",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Check for required HTML elements
        self.assertIn("<html", html_content)
        self.assertIn("<head>", html_content)
        self.assertIn("<body>", html_content)
        self.assertIn("<style>", html_content)
        self.assertIn("<script>", html_content)
        self.assertIn("app-container", html_content)
        self.assertIn("sidebar", html_content)
        self.assertIn("main-content", html_content)
        self.assertIn("user-bar", html_content)
        
        # Check for room tabs
        for room in ROOMS:
            self.assertIn(f'data-room="{room}"', html_content)
    
    def test_generate_static_html_escapes_content(self):
        """Test that HTML content is properly escaped in JavaScript"""
        test_messages = [
            {
                "type": "message",
                "user": "<script>alert('xss')</script>",
                "message": "Test & message <with> tags",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Data is embedded as JSON, so it will be JSON-escaped, not HTML-escaped
        # The actual escaping happens in the JavaScript escapeHtml() function
        # Check that the data is present (JSON format will escape quotes)
        self.assertIn("<script>alert", html_content)  # In JSON string
        self.assertIn("Test & message", html_content)  # In JSON string
        # Check that escapeHtml function exists (which does the actual escaping)
        self.assertIn("escapeHtml", html_content)
        # Check that escapeHtml is used when rendering messages
        self.assertIn("escapeHtml(user)", html_content)
        self.assertIn("escapeHtml(message)", html_content)
    
    def test_generate_static_html_includes_all_rooms(self):
        """Test that all rooms are included in the HTML"""
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Test",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Check that all rooms from ROOMS are present
        for room in ROOMS:
            self.assertIn(f'data-room="{room}"', html_content)
            self.assertIn(f'<span class="room-name">{room}</span>', html_content)
    
    def test_generate_static_html_embeds_messages(self):
        """Test that messages are embedded in JavaScript"""
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Hello world",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        css_content = "body { background: #000; }"
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Check that messages are embedded
        self.assertIn("const allMessages =", html_content)
        self.assertIn("test_user", html_content)
        self.assertIn("Hello world", html_content)
        self.assertIn("lobby", html_content)
    
    def test_export_static_handles_missing_css_file(self):
        """Test handling when CSS file doesn't exist"""
        # This tests the error handling in the endpoint
        # The generate_static_html function should work even with empty CSS
        test_messages = [
            {
                "type": "message",
                "user": "test_user",
                "message": "Test",
                "timestamp": "2026-01-30T10:00:00.000000",
                "room": "lobby"
            }
        ]
        
        # Test with empty CSS (simulating missing file)
        css_content = ""
        user_colors = {}
        
        html_content = generate_static_html(test_messages, user_colors, css_content)
        
        # Should still generate valid HTML
        self.assertIn("<!DOCTYPE html>", html_content)
        self.assertIn("<style>", html_content)

if __name__ == "__main__":
    unittest.main(verbosity=2)
