#!/usr/bin/env python3
"""
Conversion script to convert .log files to .jsonl format
Converts existing log files while preserving originals as backups
"""

import json
import re
import uuid
from pathlib import Path
from datetime import datetime

def convert_log_to_jsonl(log_path, jsonl_path):
    """
    Convert a .log file to .jsonl format
    
    Format: timestamp [TYPE] [user] message
    """
    pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}T[\d:.-]+)\s+\[(\w+)\]\s+\[([^\]]+)\]\s+(.+)$')
    
    converted_count = 0
    errors = []
    
    with open(log_path, 'r', encoding='utf-8') as log_file:
        with open(jsonl_path, 'w', encoding='utf-8') as jsonl_file:
            for line_num, line in enumerate(log_file, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = pattern.match(line)
                if match:
                    timestamp, msg_type, user, text = match.groups()
                    
                    # Normalize type
                    type_lower = msg_type.lower()
                    if type_lower == "response":
                        message_type = "response"
                        is_response = True
                    elif user.lower() == "system":
                        message_type = "system"
                        is_response = False
                    else:
                        message_type = "message"
                        is_response = False
                    
                    # Extract room from file name
                    room = log_path.stem
                    
                    # Generate message ID
                    message_id = f"msg_{uuid.uuid4().hex[:12]}"
                    
                    message_obj = {
                        "timestamp": timestamp,
                        "type": message_type,
                        "user": user,
                        "text": text,
                        "room": room,
                        "id": message_id
                    }
                    
                    if is_response:
                        message_obj["is_response"] = True
                    
                    jsonl_file.write(json.dumps(message_obj, ensure_ascii=False) + "\n")
                    converted_count += 1
                else:
                    # Handle malformed lines
                    errors.append({
                        "line": line_num,
                        "content": line[:100],  # First 100 chars
                        "error": "Pattern mismatch"
                    })
                    # Optionally create a fallback entry
                    message_obj = {
                        "timestamp": datetime.now().isoformat(),
                        "type": "system",
                        "user": "system",
                        "text": f"[CONVERSION ERROR] Original line: {line}",
                        "room": log_path.stem,
                        "id": f"msg_err_{uuid.uuid4().hex[:12]}",
                        "conversion_error": True
                    }
                    jsonl_file.write(json.dumps(message_obj, ensure_ascii=False) + "\n")
    
    return {
        "converted": converted_count,
        "errors": errors,
        "jsonl_path": jsonl_path
    }

def convert_all_logs(logs_dir):
    """Convert all .log files to .jsonl format"""
    logs_dir = Path(logs_dir)
    results = {}
    
    for log_file in logs_dir.glob("*.log"):
        room = log_file.stem
        jsonl_file = logs_dir / f"{room}.jsonl"
        
        print(f"Converting {log_file.name}...")
        result = convert_log_to_jsonl(log_file, jsonl_file)
        results[room] = result
        
        print(f"  ✓ Converted {result['converted']} messages")
        if result['errors']:
            print(f"  ⚠ {len(result['errors'])} errors encountered")
            # Print first few errors
            for error in result['errors'][:5]:
                print(f"    Line {error['line']}: {error['content']}")
            if len(result['errors']) > 5:
                print(f"    ... and {len(result['errors']) - 5} more errors")
    
    return results

def verify_conversion(log_path, jsonl_path):
    """Verify converted JSONL matches original log"""
    log_lines = []
    jsonl_messages = []
    
    # Read log file
    with open(log_path, 'r', encoding='utf-8') as f:
        log_lines = [l.strip() for l in f if l.strip()]
    
    # Read JSONL file
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    jsonl_messages.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  ✗ JSON decode error: {e}")
                    return False
    
    # Compare counts
    if len(log_lines) != len(jsonl_messages):
        print(f"  ✗ Line count mismatch: {len(log_lines)} vs {len(jsonl_messages)}")
        return False
    
    print(f"  ✓ Verification passed: {len(log_lines)} messages match")
    return True

if __name__ == "__main__":
    import sys
    
    # Get logs directory (one level up from scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    logs_dir = project_root / "logs"
    
    if not logs_dir.exists():
        print(f"Error: Logs directory not found at {logs_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("Log to JSONL Conversion Script")
    print("=" * 60)
    print(f"Logs directory: {logs_dir}")
    print()
    
    # Convert all logs
    results = convert_all_logs(logs_dir)
    
    if not results:
        print("\nNo .log files found to convert.")
        sys.exit(0)
    
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)
    
    # Verify conversions
    all_verified = True
    for room, result in results.items():
        log_path = logs_dir / f"{room}.log"
        jsonl_path = logs_dir / f"{room}.jsonl"
        
        print(f"\nVerifying {room}...")
        if verify_conversion(log_path, jsonl_path):
            print(f"  ✓ {room}.jsonl verified")
        else:
            print(f"  ✗ {room}.jsonl verification failed")
            all_verified = False
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    total_converted = sum(r['converted'] for r in results.values())
    total_errors = sum(len(r['errors']) for r in results.values())
    
    print(f"Total messages converted: {total_converted}")
    print(f"Total errors: {total_errors}")
    print(f"Rooms converted: {len(results)}")
    
    if all_verified:
        print("\n✓ All conversions verified successfully!")
        print("\nOriginal .log files are preserved as backups.")
        print("You can now update the code to use .jsonl format.")
    else:
        print("\n⚠ Some verifications failed. Please review the errors above.")
        sys.exit(1)
