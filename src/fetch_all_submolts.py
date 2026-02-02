#!/usr/bin/env python3
"""
Fetch all submolts from moltbook (up to page 50) and save to a JSON file
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


def fetch_all_submolts(max_pages=50):
    """Fetch all submolts, paginating through results"""
    if not requests:
        print("⚠ requests module not available. Install with: pip install requests", flush=True)
        sys.exit(1)
    
    client = MoltbookClient()
    
    api_key = client.config.get("api_keys", {}).get("moltbook") or os.getenv("MOLTBOOK_API_KEY")
    if not api_key:
        print("⚠ No moltbook API key configured.", flush=True)
        sys.exit(1)
    
    api_url = client.config.get("moltbook", {}).get("api_url", "https://www.moltbook.com/api/v1")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    all_submolts = []
    seen_ids = set()  # Track seen IDs to avoid duplicates
    page = 1
    
    print(f"Fetching submolts (up to page {max_pages})...", flush=True)
    
    while page <= max_pages:
        # Try different pagination parameters
        params = {"page": page, "limit": 100}
        
        try:
            response = requests.get(f"{api_url}/submolts", params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("submolts"):
                    page_submolts = data["submolts"]
                    
                    # Deduplicate by ID before adding
                    new_submolts = []
                    duplicates_this_page = 0
                    for submolt in page_submolts:
                        submolt_id = submolt.get("id")
                        if submolt_id and submolt_id not in seen_ids:
                            seen_ids.add(submolt_id)
                            new_submolts.append(submolt)
                        else:
                            duplicates_this_page += 1
                    
                    all_submolts.extend(new_submolts)
                    dup_msg = f" ({duplicates_this_page} duplicates skipped)" if duplicates_this_page > 0 else ""
                    print(f"  Page {page}: Found {len(page_submolts)} submolts, {len(new_submolts)} new{dup_msg} (Total unique: {len(all_submolts)})", flush=True)
                    
                    # If we got no new items, we've likely seen everything
                    if len(new_submolts) == 0:
                        print(f"  No new submolts on page {page}, stopping pagination", flush=True)
                        break
                    
                    # Check if there are more pages
                    # If we got fewer than limit, might be last page
                    if len(page_submolts) < 100:
                        print(f"  Reached end (got {len(page_submolts)} < 100)", flush=True)
                        break
                    
                    # Check for pagination indicators
                    if "has_more" in data and not data["has_more"]:
                        print(f"  No more pages (has_more=false)", flush=True)
                        break
                    
                    page += 1
                else:
                    print(f"  Page {page}: No submolts found or error in response", flush=True)
                    break
            elif response.status_code == 404:
                print(f"  Page {page}: 404 - No more pages", flush=True)
                break
            else:
                print(f"  Page {page}: HTTP {response.status_code}", flush=True)
                # Try without pagination if first page fails
                if page == 1:
                    print("  Trying without pagination...", flush=True)
                    response = requests.get(f"{api_url}/submolts", headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success") and data.get("submolts"):
                            all_submolts = data["submolts"]
                            print(f"  Got all {len(all_submolts)} submolts in one request", flush=True)
                    break
                else:
                    break
                    
        except Exception as e:
            print(f"  Error on page {page}: {e}", flush=True)
            break
    
    # Sort by subscriber count (descending)
    all_submolts.sort(key=lambda x: x.get("subscriber_count", 0), reverse=True)
    
    # Save to JSON file
    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "submolts.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total": len(all_submolts),
            "fetched_at": __import__('datetime').datetime.now().isoformat(),
            "submolts": all_submolts
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Fetched {len(all_submolts)} unique submolts total", flush=True)
    print(f"  Saved to: {output_file}", flush=True)
    print(f"\nTop 10 by subscribers:", flush=True)
    for i, submolt in enumerate(all_submolts[:10], 1):
        name = submolt.get("name", "unknown")
        count = submolt.get("subscriber_count", 0)
        print(f"  {i}. {name}: {count} subscribers", flush=True)
    
    return all_submolts


if __name__ == "__main__":
    fetch_all_submolts(max_pages=50)
