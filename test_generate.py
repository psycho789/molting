#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from moltbook_cli import MoltbookClient

client = MoltbookClient()
message = client.generate_message(topic="site went down, annoyed, sharing messages with human friends")
print(f"Generated: {message}")
