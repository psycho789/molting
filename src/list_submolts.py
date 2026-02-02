#!/usr/bin/env python3
"""
List all available submolts on moltbook
"""

import os
import sys
import json

try:
    import requests
except ImportError:
    requests = None

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from moltbook_cli import MoltbookClient


def main():
    if not requests:
        print("⚠ requests module not available. Install with: pip install requests", flush=True)
        sys.exit(1)
    
    client = MoltbookClient()
    
    api_key = client.config.get("api_keys", {}).get("moltbook") or os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        print("⚠ No moltbook API key configured.", flush=True)
        print("   Set MOLTBOOK_API_KEY environment variable or add to config.json", flush=True)
        sys.exit(1)
    
    api_url = client.config.get("moltbook", {}).get("api_url", "https://www.moltbook.com/api/v1")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(f"{api_url}/submolts", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("submolts"):
                submolts = data["submolts"]
                print(f"Found {len(submolts)} submolts on moltbook:\n", flush=True)
                
                # Sort by subscriber count (descending)
                submolts_sorted = sorted(submolts, key=lambda x: x.get("subscriber_count", 0), reverse=True)
                
                for submolt in submolts_sorted:
                    name = submolt.get("name", "unknown")
                    display_name = submolt.get("display_name", name)
                    description = submolt.get("description", "")
                    subscriber_count = submolt.get("subscriber_count", 0)
                    
                    print(f"  {name}")
                    if display_name != name:
                        print(f"    Display: {display_name}")
                    if description:
                        desc = description[:100] + "..." if len(description) > 100 else description
                        print(f"    {desc}")
                    print(f"    Subscribers: {subscriber_count}")
                    print()
            else:
                print("No submolts found", flush=True)
                print(f"Response: {data}", flush=True)
        else:
            print(f"✗ Error: HTTP {response.status_code}", flush=True)
            try:
                error_data = response.json()
                print(f"  Error: {error_data.get('error', response.text)}", flush=True)
            except:
                print(f"  Response: {response.text[:200]}", flush=True)
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Error fetching submolts: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
