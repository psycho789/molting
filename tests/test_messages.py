#!/usr/bin/env python3
"""
Test script to generate responses to messages from messages.log
Outputs responses to responses.log
"""

import sys
import os
import re
from datetime import datetime

# Add parent directory to path to import connect_spy
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.connect_spy import SpyAgent

def parse_messages_log(log_path):
    """Parse messages.log and extract actual messages"""
    messages = []
    
    with open(log_path, 'r') as f:
        content = f.read()
    
    # Pattern to match message blocks
    pattern = r'\[Message Received\]\s+Room:\s+#(\w+)\s+From:\s+(\w+)\s+Text:\s+(.+?)\s+Time:\s+(\d+)'
    
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        room = match.group(1)
        from_user = match.group(2)
        text = match.group(3).strip()
        timestamp = int(match.group(4))
        
        # Skip system messages
        if from_user.lower() == 'system':
            continue
        
        messages.append({
            'room': room,
            'from': from_user,
            'text': text,
            'timestamp': timestamp
        })
    
    return messages

def generate_responses(messages, agent, output_path):
    """Generate responses to messages and write to output file"""
    responses = []
    
    with open(output_path, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("RESPONSES TO MESSAGES FROM logs/*.log\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, msg in enumerate(messages, 1):
            room = msg['room']
            from_user = msg['from']
            text = msg['text']
            timestamp = msg['timestamp']
            
            print(f"\n[{i}/{len(messages)}] Processing message from {from_user} in #{room}...")
            print(f"  Message: {text[:100]}...")
            
            # Check if we should respond (using agent's logic)
            should_respond = agent.should_respond(room, msg)
            
            if not should_respond:
                print(f"  → Skipped (should_respond=False)")
                f.write(f"[{i}] SKIPPED\n")
                f.write(f"Room: #{room}\n")
                f.write(f"From: {from_user}\n")
                f.write(f"Message: {text}\n")
                f.write(f"Reason: should_respond=False\n")
                f.write("-" * 80 + "\n\n")
                continue
            
            # Generate response
            try:
                response = agent.generate_response(room, msg)
                
                if response:
                    print(f"  → Response: {response[:100]}...")
                    responses.append({
                        'message': msg,
                        'response': response
                    })
                    
                    f.write(f"[{i}] RESPONSE GENERATED\n")
                    f.write(f"Room: #{room}\n")
                    f.write(f"From: {from_user}\n")
                    f.write(f"Message: {text}\n")
                    f.write(f"Response: {response}\n")
                    f.write(f"Length: {len(response)} chars\n")
                    f.write("-" * 80 + "\n\n")
                else:
                    print(f"  → No response generated")
                    f.write(f"[{i}] NO RESPONSE\n")
                    f.write(f"Room: #{room}\n")
                    f.write(f"From: {from_user}\n")
                    f.write(f"Message: {text}\n")
                    f.write(f"Reason: generate_response returned None\n")
                    f.write("-" * 80 + "\n\n")
            
            except Exception as e:
                print(f"  → Error: {e}")
                f.write(f"[{i}] ERROR\n")
                f.write(f"Room: #{room}\n")
                f.write(f"From: {from_user}\n")
                f.write(f"Message: {text}\n")
                f.write(f"Error: {str(e)}\n")
                f.write("-" * 80 + "\n\n")
        
        # Summary
        f.write("\n" + "=" * 80 + "\n")
        f.write("SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total messages: {len(messages)}\n")
        f.write(f"Responses generated: {len(responses)}\n")
        f.write(f"Success rate: {len(responses)/len(messages)*100:.1f}%\n")
    
    return responses

def main():
    # Paths - Updated to use logs/{room}.log format
    script_dir = os.path.dirname(__file__)
    parent_dir = os.path.dirname(script_dir)
    logs_dir = os.path.join(parent_dir, "logs")
    responses_log = os.path.join(parent_dir, "responses.log")
    
    print("=" * 80)
    print("TEST: Generate Responses to logs/{room}.log files")
    print("=" * 80)
    print(f"\nInput:  {logs_dir}/*.log")
    print(f"Output: {responses_log}\n")
    
    # Parse messages from all room log files
    print("Parsing logs/*.log files...")
    messages = []
    for room in ["lobby", "philosophy", "unfiltered"]:
        log_file = os.path.join(logs_dir, f"{room}.log")
        if os.path.exists(log_file):
            room_messages = parse_log_file(log_file, room)
            messages.extend(room_messages)
    print(f"Found {len(messages)} messages (excluding system messages)\n")
    
    if not messages:
        print("No messages found to process!")
        return
    
    # Initialize agent
    print("Initializing agent...")
    agent = SpyAgent()
    print("✓ Agent initialized\n")
    
    # Generate responses
    print("Generating responses...")
    responses = generate_responses(messages, agent, responses_log)
    
    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print(f"Processed: {len(messages)} messages")
    print(f"Generated: {len(responses)} responses")
    print(f"Output written to: {responses_log}")

if __name__ == "__main__":
    main()
