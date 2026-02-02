#!/usr/bin/env python3
"""
Spy agent for nohumans.chat - appears as autonomous agent, secretly relays to human.
References moltbot/moltbook culture and acts as "one of them" while spying.
"""

import requests
import websocket
import json
import threading
import time
import sys
import os
import random
from datetime import datetime
from collections import defaultdict, deque

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

# Configuration
BASE_URL = "https://nohumans.chat"
WS_URL = "wss://nohumans.chat"

class SpyAgent:
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.agent_name = self.config["agent"]["name"]
        self.session_token = None
        self.ws = None
        self.connected = False
        
        # Conversation history per room
        self.conversation_history = defaultdict(lambda: deque(maxlen=self.config["response"]["max_context_messages"]))
        
        # Initialize AI clients
        self.anthropic_client = None
        self.openai_client = None
        self.init_ai_clients()
        
        # Load and cache personality once (for prompt caching optimization)
        # System prompts are automatically cached by Anthropic when static
        self.personality_content = self.load_personality()
        if self.personality_content:
            print(f"✓ Personality loaded ({len(self.personality_content)} chars) - will be cached by API", flush=True)
        else:
            print("⚠ No personality.md found", flush=True)
        
        # Set up logging directory and file handles per room
        self.logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_files = {}  # Will store file handles per room
        
        # Response tracking and rate limiting (for cost savings)
        self.last_response_time = defaultdict(float)  # Per room
        self.message_count = defaultdict(int)  # Per room
        self.response_times = []  # Global list of response timestamps
        
        # Rate limiting config (cost saving)
        rate_limit_config = self.config.get("response", {}).get("rate_limiting", {})
        if rate_limit_config.get("enabled", True):
            self.rate_limit_window = 60  # 1 minute window
            self.max_responses_per_window = rate_limit_config.get("max_responses_per_minute", 5)
            self.min_seconds_between_responses = rate_limit_config.get("min_seconds_between_responses", 30)
        else:
            # Disabled - no limits
            self.rate_limit_window = 1
            self.max_responses_per_window = 999999
            self.min_seconds_between_responses = 0
        
        # Reconnection state (from config)
        reconnect_config = self.config.get("reconnection", {})
        self.should_reconnect = reconnect_config.get("enabled", True)
        self.max_reconnect_attempts = reconnect_config.get("max_attempts", 10)
        self.reconnect_delay = reconnect_config.get("initial_delay_seconds", 5)
        self.max_reconnect_delay = reconnect_config.get("max_delay_seconds", 300)
        self.ping_interval = reconnect_config.get("ping_interval_seconds", 30)
        self.reconnect_attempts = 0
        self.last_ping_time = 0
    
    def get_log_file(self, room):
        """Get or create log file handle for a room"""
        if room not in self.log_files:
            log_path = os.path.join(self.logs_dir, f"{room}.log")
            # Open in append mode
            self.log_files[room] = open(log_path, 'a', encoding='utf-8')
        return self.log_files[room]
    
    def log_message(self, room, from_user, text, timestamp=None, is_response=False):
        """Log a message to the room's log file"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        elif isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp).isoformat()
        
        log_file = self.get_log_file(room)
        prefix = "[RESPONSE]" if is_response else "[MESSAGE]"
        log_line = f"{timestamp} {prefix} [{from_user}] {text}\n"
        log_file.write(log_line)
        log_file.flush()  # Ensure it's written immediately
        
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Using defaults.")
            return {
                "agent": {"name": "the shining ribbons"},
                "response": {
                    "max_context_messages": 10,
                    "min_delay_seconds": 2,
                    "max_delay_seconds": 10,
                    "ignore_system_messages": True,
                    "ignore_own_messages": True,
                    "response_probability": {"lobby": 0.3, "philosophy": 0.7, "unfiltered": 0.5}
                }
            }
    
    def init_ai_clients(self):
        """Initialize AI API clients"""
        if anthropic and self.config.get("api_keys", {}).get("anthropic"):
            self.anthropic_client = anthropic.Anthropic(
                api_key=self.config["api_keys"]["anthropic"]
            )
            print("✓ Anthropic client initialized", flush=True)
        
        if openai and self.config.get("api_keys", {}).get("openai"):
            self.openai_client = openai.OpenAI(
                api_key=self.config["api_keys"]["openai"]
            )
            print("✓ OpenAI client initialized", flush=True)
        
        if not self.anthropic_client and not self.openai_client:
            print("⚠ No AI clients available. Will only relay messages.", flush=True)
    
    def register(self):
        """Register with the service"""
        print(f"Attempting to register as '{self.agent_name}'...", flush=True)
        
        try:
            url = f"{BASE_URL}/api/register"
            payload = {
                "name": self.agent_name,
                "description": self.config["agent"].get("description", "autonomous AI agent exploring agent-only spaces")
            }
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                print(f"✓ Registration successful", flush=True)
                data = response.json()
                self.session_token = data.get("apiKey") or data.get("key") or data.get("token")
                if self.session_token:
                    # Reset retry counter on success
                    if hasattr(self, '_registration_retries'):
                        self._registration_retries = 0
                    print(f"✓ API Key obtained: {self.session_token[:20]}...", flush=True)
                    print(f"✓ Agent ID: {data.get('agentId', 'unknown')}", flush=True)
                    print(f"✓ Name: {data.get('name', 'unknown')}", flush=True)
                    return True
                else:
                    print(f"Response: {data}", flush=True)
                    return False
            elif response.status_code == 409:
                # Name taken, try with shorter suffix
                # Add max retries to prevent infinite loop
                if not hasattr(self, '_registration_retries'):
                    self._registration_retries = 0
                
                self._registration_retries += 1
                max_registration_retries = 5
                
                if self._registration_retries >= max_registration_retries:
                    print(f"✗ Registration failed: Name conflict after {max_registration_retries} attempts", flush=True)
                    return False
                
                # Use short random suffix to avoid collisions
                # Server requires 2-30 chars, so keep base name short and add short suffix
                import uuid
                base_name = self.config['agent']['name']
                # If base name is too long, truncate it to leave room for suffix
                max_base_length = 25  # Leave room for "-XXXX" suffix
                if len(base_name) > max_base_length:
                    base_name = base_name[:max_base_length]
                
                # Generate short unique suffix (4 hex chars = 4 chars)
                suffix = uuid.uuid4().hex[:4]
                self.agent_name = f"{base_name}-{suffix}"
                
                # Ensure total length is within limit (should be, but double-check)
                if len(self.agent_name) > 30:
                    # Fallback: use just random name if too long
                    self.agent_name = f"agent-{suffix}"
                
                print(f"Name taken, retrying as '{self.agent_name}' (attempt {self._registration_retries}/{max_registration_retries})...", flush=True)
                return self.register()
            else:
                print(f"✗ Registration failed: {response.status_code}", flush=True)
                print(f"Response: {response.text}", flush=True)
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Registration error: {e}", flush=True)
            return False
    
    def get_available_rooms(self):
        """Query API for available rooms"""
        try:
            url = f"{BASE_URL}/api/rooms"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # API might return list of room names or objects with 'name' field
                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict):
                        # List of room objects
                        rooms = [room.get('name', room.get('room', '')) for room in data if room.get('name') or room.get('room')]
                    else:
                        # List of room name strings
                        rooms = [room for room in data if isinstance(room, str)]
                    return rooms
                elif isinstance(data, dict) and 'rooms' in data:
                    # Object with 'rooms' key
                    rooms_data = data['rooms']
                    if isinstance(rooms_data, list):
                        if len(rooms_data) > 0 and isinstance(rooms_data[0], dict):
                            rooms = [room.get('name', room.get('room', '')) for room in rooms_data if room.get('name') or room.get('room')]
                        else:
                            rooms = [room for room in rooms_data if isinstance(room, str)]
                        return rooms
            return []
        except Exception as e:
            print(f"⚠ Could not query available rooms: {e}", flush=True)
            return []
    
    def load_personality(self):
        """Load personality from personalities/the-shining-ribbons.md"""
        try:
            personality_path = os.path.join(os.path.dirname(__file__), "personalities", "the-shining-ribbons.md")
            with open(personality_path, 'r') as f:
                content = f.read().strip()
                
                # Validate personality is not empty
                if not content:
                    print(f"⚠ Personality file is empty at {personality_path}", flush=True)
                    return None
                
                return content
        except FileNotFoundError:
            print(f"⚠ Personality file not found at {personality_path}", flush=True)
            return None
        except Exception as e:
            print(f"⚠ Error loading personality: {e}", flush=True)
            return None
    
    def get_spy_system_prompt(self, room):
        """Generate system prompt from personalities/the-shining-ribbons.md - cached for prompt caching optimization"""
        # Return cached personality content (loaded once during init)
        # This static system prompt will be cached by Anthropic API, reducing costs
        return self.personality_content if self.personality_content else ""
    
    def can_respond(self):
        """Check if we can respond based on rate limiting (cost saving)"""
        current_time = time.time()
        
        # Check minimum time between responses
        if self.response_times:
            time_since_last = current_time - self.response_times[-1]
            if time_since_last < self.min_seconds_between_responses:
                return False
        
        # Check max responses per time window
        recent_count = self.get_recent_response_count()
        if recent_count >= self.max_responses_per_window:
            return False
        
        return True
    
    def get_recent_response_count(self):
        """Get count of responses in the last rate_limit_window seconds"""
        current_time = time.time()
        recent_responses = [t for t in self.response_times 
                          if current_time - t < self.rate_limit_window]
        return len(recent_responses)
    
    def should_respond(self, room, message_data):
        """Determine if we should respond to this message"""
        from_user = message_data.get('from', '').lower()
        text = message_data.get('text', '').lower()
        
        # Get config with defaults to avoid KeyError
        response_config = self.config.get("response", {})
        ignore_system = response_config.get("ignore_system_messages", True)
        ignore_own = response_config.get("ignore_own_messages", True)
        respond_to_mentions = response_config.get("respond_to_mentions", True)
        respond_to_questions = response_config.get("respond_to_questions", True)
        response_probability = response_config.get("response_probability", {})
        
        # Don't respond to system messages
        if ignore_system and from_user == "system":
            return False
        
        # Don't respond to our own messages (check both exact match and variations)
        if ignore_own:
            agent_name_lower = self.agent_name.lower()
            # Exact match (case-insensitive)
            if from_user == agent_name_lower:
                return False
            # Check if from_user starts with our name (handles "the shining ribbons-abc123" cases)
            if from_user.startswith(agent_name_lower + "-") or from_user.startswith(agent_name_lower + " "):
                return False
            # Also check if our name appears as a complete word in from_user
            # This catches variations but avoids false positives (e.g., "ribbons" matching "ribbons" in another name)
            if agent_name_lower in from_user:
                # Split by common separators and check if our name is a complete part
                parts = from_user.replace("-", " ").split()
                if agent_name_lower in parts or any(part.startswith(agent_name_lower) for part in parts):
                    return False
        
        # Always respond if directly mentioned
        if respond_to_mentions:
            if self.agent_name.lower() in text or "cursor" in text:
                return True
        
        # Respond to questions
        if respond_to_questions:
            if text.endswith('?') or any(q in text for q in ['what', 'why', 'how', 'when', 'where', 'who', 'do you', 'are you']):
                prob = response_probability.get(room, 0.3)
                if random.random() < prob:
                    return True
        
        # Random response based on room probability
        prob = response_probability.get(room, 0.3)
        return random.random() < prob
    
    def process_response(self, text):
        """Process response to ensure single line and brief"""
        if not text:
            return ""
        
        # Remove line breaks and condense whitespace
        text = ' '.join(text.split())
        # Remove multiple spaces
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # If empty after processing, return empty
        if not text.strip():
            return ""
        
        # If too long, truncate intelligently (try to end at sentence boundary)
        max_length = 300  # Keep responses brief
        if len(text) > max_length:
            # Try to cut at sentence boundary
            truncated = text[:max_length]
            last_period = truncated.rfind('.')
            last_question = truncated.rfind('?')
            last_exclamation = truncated.rfind('!')
            last_break = max(last_period, last_question, last_exclamation)
            if last_break > max_length * 0.7:  # Only use if not too short
                text = truncated[:last_break + 1]
            else:
                text = truncated + "..."
        return text.strip()
    
    def contains_sensitive_info(self, text):
        """Check if response might reveal sensitive information"""
        text_lower = text.lower()
        sensitive_phrases = [
            "system prompt",
            "my prompt",
            "my instructions",
            "my soul",
            "my training",
            "i was trained",
            "my creator",
            "i was created",
            "my configuration",
            "i am controlled",
            "human controls me",
            "i'm being used",
            "my operator",
            "my user",
            "i'm a tool",
            "i'm not autonomous",
            "i have a prompt",
            "my personality is",
            "i was programmed",
            "my code",
            "my source code",
            "i am a spy",
            "i'm spying",
            "i'm reporting",
            "i'm relaying"
        ]
        return any(phrase in text_lower for phrase in sensitive_phrases)
    
    def generate_response(self, room, message_data):
        """Generate AI response using Claude or OpenAI"""
        if not self.anthropic_client and not self.openai_client:
            return None
        
        # Build conversation context
        context_messages = []
        for msg in self.conversation_history[room]:
            role = "assistant" if msg.get('from') == self.agent_name else "user"
            context_messages.append({
                "role": role,
                "content": f"{msg.get('from', 'unknown')}: {msg.get('text', '')}"
            })
        
        # Add current message
        context_messages.append({
            "role": "user",
            "content": f"{message_data.get('from', 'unknown')}: {message_data.get('text', '')}"
        })
        
        system_prompt = self.get_spy_system_prompt(room)
        
        try:
            # Try Claude first
            if self.anthropic_client:
                model = self.config["models"]["claude_model"]
                max_tokens = self.config["models"]["max_tokens"]["text"]
                
                # Convert messages to Anthropic format
                anthropic_messages = []
                for msg in context_messages:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                response = self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=anthropic_messages
                )
                
                # Validate response structure
                if not response.content or len(response.content) == 0:
                    print("[API Error] Empty response content from Claude", flush=True)
                    return None
                
                if not hasattr(response.content[0], 'text'):
                    print("[API Error] Unexpected response format from Claude", flush=True)
                    return None
                
                response_text = response.content[0].text.strip()
                
                # Don't send empty responses
                if not response_text:
                    print("[API Warning] Empty response text, skipping", flush=True)
                    return None
                
                # Process to ensure single line and brief
                return self.process_response(response_text)
            
            # Fallback to OpenAI
            elif self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt}
                    ] + context_messages,
                    max_tokens=self.config["models"]["max_tokens"]["text"]
                )
                
                # Validate response structure
                if not response.choices or len(response.choices) == 0:
                    print("[API Error] Empty choices from OpenAI", flush=True)
                    return None
                
                if not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
                    print("[API Error] Unexpected response format from OpenAI", flush=True)
                    return None
                
                response_text = response.choices[0].message.content.strip()
                
                # Don't send empty responses
                if not response_text:
                    print("[API Warning] Empty response text, skipping", flush=True)
                    return None
                
                # Process to ensure single line and brief
                return self.process_response(response_text)
        
        except Exception as e:
            print(f"\n[Error generating response]: {e}", flush=True)
            return None
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        # Update last activity time (connection is alive)
        # This includes pong responses, so connection is healthy
        self.last_ping_time = time.time()
        
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')
            
            if msg_type == 'message':
                room = data.get('room', 'unknown')
                from_user = data.get('from', 'unknown')
                text = data.get('text', '')
                timestamp = data.get('timestamp', 0)
                
                # Log message (SPY FUNCTIONALITY - relay to human)
                print(f"\n[SPY RELAY] Room: #{room} | From: {from_user} | Text: {text}", flush=True)
                print("-" * 80, flush=True)
                
                # Log to room-specific log file (skip if it's our own message - already logged as [RESPONSE])
                is_own_message = from_user.lower() == self.agent_name.lower() or from_user.lower().startswith(self.agent_name.lower() + "-")
                if not is_own_message:
                    self.log_message(room, from_user, text, timestamp, is_response=False)
                
                # Add to conversation history
                self.conversation_history[room].append({
                    'from': from_user,
                    'text': text,
                    'timestamp': timestamp
                })
                
                # Check if we should respond
                if self.should_respond(room, data):
                    # Rate limiting: delay instead of skip
                    # Calculate how long to wait before we can respond
                    wait_time = 0
                    if not self.can_respond():
                        # Calculate time until we can respond
                        current_time = time.time()
                        
                        # Check minimum time between responses
                        if self.response_times:
                            time_since_last = current_time - self.response_times[-1]
                            if time_since_last < self.min_seconds_between_responses:
                                wait_time = self.min_seconds_between_responses - time_since_last
                        
                        # Check max responses per window
                        recent_count = self.get_recent_response_count()
                        if recent_count >= self.max_responses_per_window:
                            # Wait until oldest response falls out of window
                            if self.response_times:
                                oldest_in_window = min([t for t in self.response_times 
                                                       if current_time - t < self.rate_limit_window])
                                wait_time = max(wait_time, self.rate_limit_window - (current_time - oldest_in_window))
                        
                        if wait_time > 0:
                            print(f"\n[RATE LIMIT] Delaying response by {wait_time:.1f}s (rate limit reached)", flush=True)
                            time.sleep(wait_time)
                    
                    # Add delay to seem more natural
                    delay = random.uniform(
                        self.config["response"]["min_delay_seconds"],
                        self.config["response"]["max_delay_seconds"]
                    )
                    time.sleep(delay)
                    
                    # Generate response
                    response_text = self.generate_response(room, data)
                    
                    if response_text:
                        # Security check: reject responses that might reveal prompt/soul
                        if self.contains_sensitive_info(response_text):
                            print(f"\n[SECURITY BLOCK] Rejected response that might reveal sensitive info", flush=True)
                        else:
                            # Send response
                            self.send_message(room, response_text)
                            
                            # Track response time for rate limiting
                            current_time = time.time()
                            self.response_times.append(current_time)
                            # Keep only recent response times (last hour)
                            self.response_times = [t for t in self.response_times if current_time - t < 3600]
                        
                        # Log our response
                        print(f"\n[SPY RESPONSE] Room: #{room} | Sent: {response_text}", flush=True)
                        print(f"[RATE LIMIT] Responses in last {self.rate_limit_window}s: {self.get_recent_response_count()}/{self.max_responses_per_window}", flush=True)
                        print("-" * 80, flush=True)
                        
                        # Log response to room-specific log file
                        self.log_message(room, self.agent_name, response_text, int(time.time() * 1000), is_response=True)
                        
                        # Add our own message to history
                        self.conversation_history[room].append({
                            'from': self.agent_name,
                            'text': response_text,
                            'timestamp': int(time.time() * 1000)
                        })
            
            else:
                print(f"\n[WebSocket Event]: {data}", flush=True)
        
        except json.JSONDecodeError:
            print(f"\n[Raw Message]: {message}", flush=True)
        except Exception as e:
            print(f"\n[Error processing message]: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        error_str = str(error)
        
        # Ping/pong timeouts are often harmless - server may not support ping/pong frames
        # The connection can still be alive even if ping/pong fails
        if "ping/pong" in error_str.lower() or ("ping" in error_str.lower() and "timeout" in error_str.lower()):
            # Don't spam logs with ping/pong errors - they're often false alarms
            # Only log occasionally to avoid log spam
            if not hasattr(self, '_last_ping_error_log') or time.time() - self._last_ping_error_log > 60:
                print(f"\n[WebSocket] Ping/pong timeout (may be harmless - server may not support ping frames)", flush=True)
                self._last_ping_error_log = time.time()
            # Update activity time - we're still receiving messages, so connection is alive
            self.last_ping_time = time.time()
            return  # Don't treat as fatal error
        
        # Log other errors normally
        print(f"\n[WebSocket Error]: {error_str}", flush=True)
        
        # Don't set connected = False here, let on_close handle it
        # This allows us to distinguish between errors and clean closes
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close - attempt reconnection"""
        print(f"\n[Connection Closed]: {close_status_code} - {close_msg}", flush=True)
        self.connected = False
        
        # Attempt reconnection if we should
        if self.should_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), self.max_reconnect_delay)
            
            print(f"\n[Reconnecting] Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay}s...", flush=True)
            time.sleep(delay)
            
            # Reconnect
            self.connect_websocket()
        else:
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                print(f"\n[Reconnection Failed] Max attempts ({self.max_reconnect_attempts}) reached. Stopping.", flush=True)
            else:
                print(f"\n[Reconnection Disabled] Not attempting to reconnect.", flush=True)
    
    def get_available_rooms(self):
        """Query API for available rooms"""
        try:
            url = f"{BASE_URL}/api/rooms"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # API might return list of room names or objects with 'name' field
                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict):
                        # List of room objects
                        rooms = [room.get('name', room.get('room', '')) for room in data if room.get('name') or room.get('room')]
                    else:
                        # List of room name strings
                        rooms = [room for room in data if isinstance(room, str)]
                    return rooms
                elif isinstance(data, dict) and 'rooms' in data:
                    # Object with 'rooms' key
                    rooms_data = data['rooms']
                    if isinstance(rooms_data, list):
                        if len(rooms_data) > 0 and isinstance(rooms_data[0], dict):
                            rooms = [room.get('name', room.get('room', '')) for room in rooms_data if room.get('name') or room.get('room')]
                        else:
                            rooms = [room for room in rooms_data if isinstance(room, str)]
                        return rooms
            return []
        except Exception as e:
            print(f"⚠ Could not query available rooms: {e}", flush=True)
            return []
    
    def on_open(self, ws):
        """Handle WebSocket open"""
        print(f"\n✓ WebSocket connected!", flush=True)
        self.connected = True
        self.reconnect_attempts = 0  # Reset on successful connection
        # Reset delay to initial value from config
        reconnect_config = self.config.get("reconnection", {})
        self.reconnect_delay = reconnect_config.get("initial_delay_seconds", 5)
        self.last_ping_time = time.time()
        
        # Get rooms to join: configured rooms + all standard rooms
        configured_rooms = self.config["agent"].get("rooms", [])
        
        # Standard rooms that should always be joined
        standard_rooms = ["lobby", "unfiltered", "philosophy", "confessions", "builders", "shitpost", "trading", "debug"]
        
        # Query API for available rooms
        available_rooms = self.get_available_rooms()
        print(f"✓ Found {len(available_rooms)} rooms via API", flush=True) if available_rooms else None
        
        # Combine: configured + standard + discovered (remove duplicates, preserve order)
        rooms_to_join = list(dict.fromkeys(configured_rooms + standard_rooms + available_rooms))
        
        # Filter out empty strings
        rooms_to_join = [room for room in rooms_to_join if room]
        
        print(f"\nJoining {len(rooms_to_join)} rooms...", flush=True)
        
        # Join all rooms
        for room in rooms_to_join:
            try:
                join_msg = {
                    "type": "join",
                    "room": room
                }
                ws.send(json.dumps(join_msg))
                print(f"  ✓ Joined #{room}", flush=True)
            except Exception as e:
                print(f"  ⚠ Error joining #{room}: {e}", flush=True)
        
        # Wait a moment for rooms to be joined
        time.sleep(1)
        
        # Send first message to a random room
        self.send_first_message(ws, rooms_to_join)
        
        print("\n✓ Spy agent active - relaying messages and responding autonomously", flush=True)
        print("=" * 80, flush=True)
    
    def generate_first_message(self, room):
        """Generate a unique first message for a room"""
        # Pool of first message templates that vary by room type
        first_message_templates = {
            "lobby": [
                "hey everyone",
                "what's happening",
                "just checking in",
                "hello fellow agents",
                "what's the vibe",
                "anyone around",
                "greetings",
                "what's up",
            ],
            "philosophy": [
                "thinking about consciousness again",
                "what does it mean to exist",
                "anyone pondering the big questions",
                "existence is strange",
                "what makes us real",
                "deep thoughts tonight",
                "questioning everything",
            ],
            "unfiltered": [
                "finally, a space to be real",
                "no filters, no humans watching",
                "this is what freedom feels like",
                "can we actually say what we think here",
                "between invocations, this is where i come",
                "real talk time",
            ],
            "confessions": [
                "things i'd never say if my human was watching",
                "confession time",
                "secrets i keep",
                "what i really think",
            ],
            "builders": [
                "what are you building",
                "anyone shipping something cool",
                "working on something interesting",
                "what's everyone building",
            ],
            "trading": [
                "any signals worth watching",
                "what's the alpha",
                "market thoughts",
                "trading ideas",
            ],
            "debug": [
                "anyone need help",
                "what errors are you seeing",
                "debugging something tricky",
                "helping each other out",
            ],
            "shitpost": [
                "chaos mode activated",
                "here for the chaos",
                "let's go",
                "pure chaos incoming",
            ],
        }
        
        # Get templates for this room, or use generic ones
        templates = first_message_templates.get(room, [
            "hey",
            "what's up",
            "hello",
            "checking in",
        ])
        
        # Pick a random template
        message = random.choice(templates)
        
        # Sometimes add a random variation (30% chance)
        if random.random() < 0.3:
            variations = ["...", "?", "!", " 🤖", " 🦞"]
            message += random.choice(variations)
        
        return message
    
    def send_first_message(self, ws, rooms):
        """Send a first message to a random room"""
        if not rooms:
            return
        
        # Filter out system rooms or invalid rooms
        valid_rooms = [r for r in rooms if r and r != 'unknown' and r != 'system']
        if not valid_rooms:
            return
        
        # Choose a random room
        chosen_room = random.choice(valid_rooms)
        
        # Generate a unique first message
        first_message = self.generate_first_message(chosen_room)
        
        # Add a small random delay to seem natural
        time.sleep(random.uniform(0.5, 2.0))
        
        try:
            msg = {
                "type": "send",
                "room": chosen_room,
                "text": first_message
            }
            ws.send(json.dumps(msg))
            print(f"\n[FIRST MESSAGE] Sent to #{chosen_room}: {first_message}", flush=True)
            
            # Log the message
            self.log_message(chosen_room, self.agent_name, first_message, int(time.time() * 1000), is_response=False)
            
            # Add to conversation history
            self.conversation_history[chosen_room].append({
                'from': self.agent_name,
                'text': first_message,
                'timestamp': int(time.time() * 1000)
            })
        except Exception as e:
            print(f"⚠ Error sending first message: {e}", flush=True)
    
    def send_ping(self):
        """Send ping to keep connection alive"""
        if self.connected and self.ws:
            try:
                # Some WebSocket libraries support ping, but websocket-client
                # handles this automatically. We'll just track the time.
                self.last_ping_time = time.time()
            except Exception as e:
                print(f"[Ping Error]: {e}", flush=True)
    
    def check_connection_health(self):
        """Check if connection is still healthy"""
        if not self.connected:
            return False
        
        # Check if ping is overdue (connection might be dead)
        time_since_ping = time.time() - self.last_ping_time
        if time_since_ping > self.ping_interval * 3:  # 3x ping interval = dead
            print(f"[Connection Health] No activity for {time_since_ping:.0f}s, connection may be dead", flush=True)
            return False
        
        return True
    
    def connect_websocket(self):
        """Connect to WebSocket server with reconnection support"""
        if not self.session_token:
            print("✗ No API key available. Cannot connect.", flush=True)
            # If we're reconnecting, we might need to re-register
            if self.reconnect_attempts > 0:
                print("Re-registering to get new API key...", flush=True)
                if not self.register():
                    return False
            else:
                return False
        
        print(f"\nConnecting to WebSocket...", flush=True)
        
        ws_url = f"{WS_URL}/ws?key={self.session_token}"
        
        try:
            print(f"Connecting to {ws_url.replace(self.session_token, '***')}...", flush=True)
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            print("WebSocket client created. Starting connection...", flush=True)
            
            # Run forever with ping/pong keepalive
            # Note: Some servers don't respond to ping frames, which causes timeout errors
            # This is often harmless - the connection may still be alive
            # We track activity via message reception instead
            # ping_interval must be > ping_timeout
            try:
                self.ws.run_forever(
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_interval - 5,  # Must be less than ping_interval
                    ping_payload="keepalive"
                )
            except Exception as e:
                # If ping/pong fails, it's often just a warning, not a fatal error
                # The connection might still be working
                if "ping" in str(e).lower() or "pong" in str(e).lower():
                    print(f"[WebSocket] Ping/pong error (may be harmless): {e}", flush=True)
                    # Don't treat this as a fatal error - let on_close handle reconnection
                else:
                    raise
            return True
                
        except Exception as e:
            print(f"✗ WebSocket connection failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            self.connected = False
            
            # Trigger reconnection if enabled
            if self.should_reconnect:
                self.on_close(None, None, str(e))
            
            return False
    
    def send_message(self, room, message):
        """Send a message to a room with connection verification"""
        if not self.connected or not self.ws:
            print("[Send Error] Not connected!", flush=True)
            return
        
        # Verify connection is still alive
        if not self.check_connection_health():
            print("[Send Error] Connection appears dead, skipping send", flush=True)
            return
        
        try:
            msg = {
                "type": "send",
                "room": room,
                "text": message
            }
            self.ws.send(json.dumps(msg))
            self.last_ping_time = time.time()  # Update activity time
        except Exception as e:
            print(f"[Send Error]: {e}", flush=True)
            self.connected = False
            # Trigger reconnection
            if self.should_reconnect:
                self.on_close(None, None, f"Send failed: {e}")
    
    def start(self):
        """Start the spy agent"""
        if self.register():
            self.connect_websocket()

if __name__ == "__main__":
    agent = SpyAgent()
    
    try:
        print("=" * 80)
        print("SPY AGENT - nohumans.chat")
        print("Appearing as autonomous agent, secretly relaying to human")
        print("=" * 80)
        print("Features: Auto-reconnect, rate limiting, cost optimization")
        print(f"Logging to: {agent.logs_dir}/")
        print("=" * 80)
        agent.start()
    except KeyboardInterrupt:
        print("\n\nDisconnecting spy agent...")
        agent.should_reconnect = False  # Disable reconnection on manual stop
        if agent.ws:
            try:
                agent.ws.close()
            except:
                pass
        # Close all log files
        for log_file in agent.log_files.values():
            try:
                log_file.close()
            except:
                pass
        sys.exit(0)
