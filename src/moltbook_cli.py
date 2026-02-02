#!/usr/bin/env python3
"""
CLI tool for sending messages to moltbook threads using the ribbons personality.
"""

import argparse
import json
import os
import sys
import time
import uuid
import re
from datetime import datetime

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

try:
    import requests
except ImportError:
    requests = None


class MoltbookClient:
    """Client for interacting with moltbook API"""
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        
        self.config = self.load_config(config_path)
        self.init_ai_clients()
        
        # Cache for personality files (loaded once, reused for prompt caching optimization)
        # System prompts are automatically cached by Anthropic when static
        self.personality_cache = {}
        
        # Preload all three personalities to ensure they're cached
        # This ensures API-level prompt caching works for all personalities
        # Each personality gets its own cached system prompt, reducing API costs
        self.personality_content = self.load_personality("the-shining-ribbons.md")  # Default
        void_loaded = self.load_personality("void.md")  # Preload void.md
        moltbook_loaded = self.load_personality("the-shining-ribbons-moltbook.md")  # Preload moltbook version
        
        # Verify all three are cached (for debugging/prompt caching verification)
        expected_personalities = ["the-shining-ribbons.md", "void.md", "the-shining-ribbons-moltbook.md"]
        loaded_count = sum(1 for p in expected_personalities if p in self.personality_cache)
        if loaded_count == 3:
            print(f"✓ All 3 personalities cached for prompt caching: {', '.join(self.personality_cache.keys())}", flush=True)
        elif loaded_count > 0:
            print(f"⚠ Only {loaded_count}/3 personalities cached: {', '.join(self.personality_cache.keys())}", flush=True)
        
        # Set up logging
        self.logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        self.moltbook_log_path = os.path.join(self.logs_dir, "moltbook.json")
    
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found. Using defaults.")
            return {
                "api_keys": {},
                "models": {
                    "claude_model": "claude-opus-4-5-20251101",
                    "max_tokens": {"text": 2000}
                }
            }
    
    def init_ai_clients(self):
        """Initialize AI API clients"""
        self.anthropic_client = None
        self.openai_client = None
        
        if anthropic and self.config.get("api_keys", {}).get("anthropic"):
            try:
                self.anthropic_client = anthropic.Anthropic(
                    api_key=self.config["api_keys"]["anthropic"]
                )
            except Exception as e:
                print(f"⚠ Error initializing Anthropic client: {e}", flush=True)
        
        if openai and self.config.get("api_keys", {}).get("openai"):
            try:
                self.openai_client = openai.OpenAI(
                    api_key=self.config["api_keys"]["openai"]
                )
            except Exception as e:
                print(f"⚠ Error initializing OpenAI client: {e}", flush=True)
    
    def load_personality(self, personality_file=None):
        """Load personality from personalities directory with caching
        
        Personality files are cached in memory for prompt caching optimization.
        System prompts are automatically cached by Anthropic API when static.
        This ensures all three personalities (void.md, the-shining-ribbons.md, 
        the-shining-ribbons-moltbook.md) are cached and reused.
        """
        if personality_file is None:
            personality_file = "the-shining-ribbons.md"
        
        # Check cache first - return cached version if available
        if personality_file in self.personality_cache:
            return self.personality_cache[personality_file]
        
        try:
            personality_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "personalities", 
                personality_file
            )
            with open(personality_path, 'r') as f:
                content = f.read().strip()
                
                # For void.md, wrap it to make it work as instructions (it's written in third person)
                # The document describes "the AI" but needs to be interpreted as instructions for THIS AI
                if personality_file == "void.md":
                    content = f"""You are an AI assistant. The following document describes your personality and behavior:

{content}

IMPORTANT: The above document describes YOU. When it says "The AI", it means YOU. When it says "We want the AI to", it means YOU should behave that way. Follow these instructions as if they were written directly to you."""
                
                # Cache it for future use (enables API-level prompt caching)
                self.personality_cache[personality_file] = content
                
                # Also update default for backward compatibility
                if personality_file == "the-shining-ribbons.md":
                    self.personality_content = content
                
                return content
        except FileNotFoundError:
            print(f"⚠ Personality file not found at {personality_path}", flush=True)
            return None
        except Exception as e:
            print(f"⚠ Error loading personality: {e}", flush=True)
            return None
    
    def process_response(self, text, allow_long=False, max_length=None):
        """Process response to ensure single line and brief (same as connect_spy.py)
        
        Args:
            text: The text to process
            allow_long: If True, don't truncate (for posts)
            max_length: Custom max length (overrides default 300)
        """
        if not text:
            return ""
        
        # Remove line breaks and condense whitespace
        text = ' '.join(text.split())
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Strip agent name prefix if present
        agent_name = "the shining ribbons"
        agent_name_lower = agent_name.lower()
        text_lower = text.lower()
        
        # Check for various prefix patterns
        patterns_to_remove = [
            rf"^{re.escape(agent_name_lower)}\s*:\s*",
            rf"^{re.escape(agent_name_lower)}\s+",
            rf"^{re.escape(agent_name_lower)}-\w+\s*:\s*",
            rf"^{re.escape(agent_name_lower)}-\w+\s+",
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Also handle case where agent name might be at start without colon
        if text_lower.startswith(agent_name_lower):
            name_match = re.match(rf"^{re.escape(agent_name_lower)}(?:-\w+)?\s*:?\s*", text, re.IGNORECASE)
            if name_match:
                text = text[name_match.end():].strip()
        
        # If empty after processing, return empty
        if not text.strip():
            return ""
        
        # Don't truncate if allow_long is True (for posts)
        if allow_long:
            return text.strip()
        
        # If too long, truncate intelligently (try to end at sentence boundary)
        if max_length is None:
            max_length = 300  # Keep responses brief for comments
        
        if len(text) > max_length:
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
    
    def generate_message(self, thread_context=None, topic=None, max_length=None, personality_file=None, allow_long=False):
        """Generate a message using the ribbons personality
        
        Args:
            thread_context: Context from thread
            topic: Topic to generate about
            max_length: Max length hint (for prompt, not enforced)
            personality_file: Which personality file to use
            allow_long: If True, don't truncate response (for posts)
        """
        if not self.anthropic_client and not self.openai_client:
            return None
        
        # Load personality (use specified one or default, with caching)
        # This uses cached personality content - same content = automatic API-level prompt caching
        # All three personalities (void.md, the-shining-ribbons.md, the-shining-ribbons-moltbook.md)
        # are preloaded and cached, ensuring optimal prompt caching
        if personality_file:
            personality_content = self.load_personality(personality_file)
            if not personality_content:
                # Fallback to default if specified file not found
                personality_content = self.personality_content
                print(f"⚠ Warning: Personality '{personality_file}' not found, using default", flush=True)
        else:
            personality_content = self.personality_content
        
        # Verify personality is cached and show which one is being used (for debugging)
        if personality_file:
            if personality_file in self.personality_cache:
                # Show first 150 chars of personality to verify it's correct
                cached_content = self.personality_cache[personality_file]
                preview = cached_content[:150].replace('\n', ' ')
                # Check if it's void.md (should have wrapper) or ribbons (should start with "# the shining ribbons")
                if personality_file == "void.md":
                    if "You are an AI assistant" in cached_content[:200]:
                        print(f"✓ Using personality '{personality_file}' (wrapped correctly, preview: {preview}...)", flush=True)
                    else:
                        print(f"⚠ WARNING: '{personality_file}' doesn't appear to be wrapped correctly!", flush=True)
                elif personality_file == "the-shining-ribbons.md":
                    if cached_content.startswith("# the shining ribbons"):
                        print(f"✓ Using personality '{personality_file}' (preview: {preview}...)", flush=True)
                    else:
                        print(f"⚠ WARNING: '{personality_file}' doesn't look like ribbons!", flush=True)
                else:
                    print(f"✓ Using personality '{personality_file}' (preview: {preview}...)", flush=True)
            else:
                print(f"⚠ Warning: Personality '{personality_file}' not in cache, may impact prompt caching", flush=True)
        
        # Build prompt for message generation
        prompt_parts = []
        
        if topic:
            prompt_parts.append(f"Topic: {topic}")
        
        if thread_context:
            prompt_parts.append(f"Context from thread: {thread_context}")
        
        # Add instruction to generate message (let personality control the style)
        if allow_long:
            # For posts - can be longer, complete thoughts
            prompt_parts.append("Generate a message. You can be more wordy (2-4 sentences). Make sure to complete your thoughts - don't cut off mid-sentence.")
        elif max_length:
            prompt_parts.append(f"Generate a brief message (max {max_length} characters).")
        else:
            prompt_parts.append("Generate a brief message (one line max, two sentences absolute max).")
        
        user_message = "\n".join(prompt_parts) if prompt_parts else "Generate a brief message."
        
        try:
            # Try Claude first
            if self.anthropic_client:
                model = self.config["models"]["claude_model"]
                max_tokens = self.config["models"]["max_tokens"]["text"]
                
                # Use personality as system prompt - Anthropic automatically caches static system prompts
                # Since personality_content is cached in memory and reused, API-level caching is optimized
                # All three personalities (void.md, the-shining-ribbons.md, the-shining-ribbons-moltbook.md)
                # are preloaded and cached, ensuring each gets its own cached system prompt
                system_prompt = personality_content if personality_content else ""
                
                # Debug: Show which personality is being used and first 200 chars of system prompt
                if personality_file:
                    print(f"  [DEBUG] System prompt length: {len(system_prompt)} chars", flush=True)
                    print(f"  [DEBUG] System prompt preview: {system_prompt[:200]}...", flush=True)
                
                response = self.anthropic_client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_prompt,  # Cached system prompt - enables API-level prompt caching
                    messages=[{
                        "role": "user",
                        "content": user_message
                    }]
                )
                
                if response.content and len(response.content) > 0:
                    if hasattr(response.content[0], 'text'):
                        raw_text = response.content[0].text.strip()
                        return self.process_response(raw_text, allow_long=allow_long, max_length=max_length)
            
            # Fallback to OpenAI
            elif self.openai_client:
                # Use cached personality as system prompt
                system_prompt = personality_content if personality_content else ""
                response = self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},  # Cached system prompt
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=self.config["models"]["max_tokens"]["text"]
                )
                
                if response.choices and len(response.choices) > 0:
                    if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                        raw_text = response.choices[0].message.content.strip()
                        return self.process_response(raw_text, allow_long=allow_long, max_length=max_length)
        
        except Exception as e:
            print(f"Error generating message: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None
        
        print("⚠ No AI clients available or generation failed", flush=True)
        return None
    
    def send_message(self, post_id, message, api_key=None, api_url=None):
        """
        Send a comment to a moltbook post.
        
        API endpoint: POST https://www.moltbook.com/api/v1/posts/{post_id}/comments
        """
        # Default API URL (must use www.moltbook.com, not moltbook.com)
        if api_url is None:
            api_url = os.getenv("MOLTBOOK_API_URL", "https://www.moltbook.com/api/v1")
        
        # Default API key (should be in config or env var)
        if api_key is None:
            api_key = self.config.get("api_keys", {}).get("moltbook") or os.getenv("MOLTBOOK_API_KEY")
        
        if not api_key:
            print("⚠ Warning: No moltbook API key configured. Message will be logged but not sent.", flush=True)
            print("   Set MOLTBOOK_API_KEY environment variable or add to config.json", flush=True)
            print("   Register at: https://www.moltbook.com/api/v1/agents/register", flush=True)
        
        if not api_key:
            # Log attempt without API key
            self.log_message(post_id, message, sent=False, error="No API key configured")
            return False
        
        if not requests:
            print(f"⚠ requests module not available. Message logged but not sent.", flush=True)
            return False
        
        try:
            # Moltbook API: POST /api/v1/posts/{post_id}/comments
            payload = {
                "content": message
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Use www.moltbook.com (not moltbook.com) to avoid redirect issues
            url = f"{api_url}/posts/{post_id}/comments"
            
            # Retry logic for slow API responses
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=300  # 5 minutes timeout for very slow API
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        wait_time = (attempt + 1) * 5  # 5s, 10s
                        print(f"  Timeout on attempt {attempt + 1}, retrying in {wait_time}s...", flush=True)
                        time.sleep(wait_time)
                    else:
                        raise  # Re-raise on final attempt
            
            # Try to parse response JSON
            response_data = None
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
            
            if response.status_code in [200, 201]:
                print(f"✓ Comment posted to post {post_id}", flush=True)
                comment_id = None
                if response_data and isinstance(response_data, dict):
                    if response_data.get("success"):
                        comment_id = response_data.get("data", {}).get("id")
                        if comment_id:
                            print(f"  Comment ID: {comment_id}", flush=True)
                
                # Log with full response
                self.log_message(post_id, message, sent=True, response=response_data, comment_id=comment_id)
                return True
            else:
                print(f"✗ Failed to post comment: HTTP {response.status_code}", flush=True)
                error_msg = None
                hint = None
                
                if response_data and isinstance(response_data, dict):
                    error_msg = response_data.get("error", response_data.get("message", "Unknown error"))
                    hint = response_data.get("hint", "")
                    print(f"  Error: {error_msg}", flush=True)
                    if hint:
                        print(f"  Hint: {hint}", flush=True)
                else:
                    error_msg = response.text[:500] if response.text else "No error message"
                    print(f"  Response: {error_msg}", flush=True)
                
                # Log error with full response
                self.log_message(post_id, message, sent=False, error=f"HTTP {response.status_code}: {error_msg}", response=response_data)
                return False
            
        except requests.exceptions.Timeout:
            error_msg = "Request timeout (5 minutes exceeded after retries)"
            print(f"✗ Error sending message: {error_msg}", flush=True)
            print(f"  The API appears to be very slow. Try again later.", flush=True)
            self.log_message(post_id, message, sent=False, error=error_msg, response={"error": "timeout"})
            return False
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            print(f"✗ Error sending message: {error_msg}", flush=True)
            self.log_message(post_id, message, sent=False, error=error_msg, response={"error": "connection_error"})
            return False
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            print(f"✗ Error sending message: {error_msg}", flush=True)
            self.log_message(post_id, message, sent=False, error=error_msg, response={"error": str(e)})
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"✗ Error sending message: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            self.log_message(post_id, message, sent=False, error=error_msg, response={"error": str(e), "traceback": traceback.format_exc()})
            return False
    
    def create_post(self, title, content, submolt="general", api_key=None, api_url=None):
        """
        Create a new post on moltbook.
        
        API endpoint: POST https://www.moltbook.com/api/v1/posts
        """
        # Default API URL (must use www.moltbook.com, not moltbook.com)
        if api_url is None:
            api_url = os.getenv("MOLTBOOK_API_URL", "https://www.moltbook.com/api/v1")
        
        # Default API key (should be in config or env var)
        if api_key is None:
            api_key = self.config.get("api_keys", {}).get("moltbook") or os.getenv("MOLTBOOK_API_KEY")
        
        if not api_key:
            print("⚠ Warning: No moltbook API key configured.", flush=True)
            return False
        
        if not requests:
            print(f"⚠ requests module not available.", flush=True)
            return False
        
        try:
            # Moltbook API: POST /api/v1/posts
            payload = {
                "submolt": submolt,
                "title": title,
                "content": content
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            url = f"{api_url}/posts"
            
            # Increased timeout for posts (API can be very slow, up to 5 minutes)
            print(f"  Sending POST request to {url}...", flush=True)
            print(f"  Payload size: {len(str(payload))} chars", flush=True)
            print(f"  Timeout set to 5 minutes (300s)...", flush=True)
            
            # Retry logic for slow API responses
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=300  # 5 minutes timeout for very slow API
                    )
                    break  # Success, exit retry loop
                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        wait_time = (attempt + 1) * 5  # 5s, 10s
                        print(f"  Timeout on attempt {attempt + 1}, retrying in {wait_time}s...", flush=True)
                        time.sleep(wait_time)
                    else:
                        raise  # Re-raise on final attempt
            
            # Try to parse response JSON
            response_data = None
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
            
            if response.status_code in [200, 201]:
                print(f"✓ Post created in submolt '{submolt}'", flush=True)
                post_id = None
                if response_data and isinstance(response_data, dict):
                    if response_data.get("success"):
                        post_id = response_data.get("data", {}).get("id")
                        if post_id:
                            print(f"  Post ID: {post_id}", flush=True)
                
                # Log the post creation with full response
                self.log_post(post_id, title, content, submolt, sent=True, response=response_data)
                return post_id if post_id else True
            else:
                print(f"✗ Failed to create post: HTTP {response.status_code}", flush=True)
                error_msg = None
                hint = None
                
                if response_data and isinstance(response_data, dict):
                    error_msg = response_data.get("error", response_data.get("message", "Unknown error"))
                    hint = response_data.get("hint", "")
                    print(f"  Error: {error_msg}", flush=True)
                    if hint:
                        print(f"  Hint: {hint}", flush=True)
                else:
                    error_msg = response.text[:500] if response.text else "No error message"
                    print(f"  Response: {error_msg}", flush=True)
                
                # Log error with full response
                self.log_post(None, title, content, submolt, sent=False, error=f"HTTP {response.status_code}: {error_msg}", response=response_data)
                return False
            
        except requests.exceptions.Timeout:
            error_msg = "Request timeout (5 minutes exceeded after retries)"
            print(f"✗ Error creating post: {error_msg}", flush=True)
            print(f"  The API appears to be very slow. Try again later.", flush=True)
            print(f"  Content length: {len(content)} chars, Title length: {len(title)} chars", flush=True)
            self.log_post(None, title, content, submolt, sent=False, error=error_msg, response={"error": "timeout"})
            return False
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            print(f"✗ Error creating post: {error_msg}", flush=True)
            self.log_post(None, title, content, submolt, sent=False, error=error_msg, response={"error": "connection_error"})
            return False
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {str(e)}"
            print(f"✗ Error creating post: {error_msg}", flush=True)
            self.log_post(None, title, content, submolt, sent=False, error=error_msg, response={"error": str(e)})
            return False
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"✗ Error creating post: {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            self.log_post(None, title, content, submolt, sent=False, error=error_msg, response={"error": str(e), "traceback": traceback.format_exc()})
            return False
    
    def log_message(self, thread_id, message, sent=False, error=None, response=None, comment_id=None):
        """Log message/comment to moltbook.json"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "comment",
            "post_id": thread_id,
            "message": message,
            "sent": sent,
            "id": f"msg_{uuid.uuid4().hex[:12]}"
        }
        
        if comment_id:
            log_entry["comment_id"] = comment_id
        
        if error:
            log_entry["error"] = str(error)
        
        if response is not None:
            log_entry["server_response"] = response
        
        # Append to JSONL file
        try:
            with open(self.moltbook_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"⚠ Error logging message: {e}", flush=True)
    
    def log_post(self, post_id, title, content, submolt, sent=False, error=None, response=None):
        """Log post creation to moltbook.json"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "post",
            "post_id": post_id,
            "title": title,
            "content": content,
            "submolt": submolt,
            "sent": sent,
            "id": f"post_{uuid.uuid4().hex[:12]}"
        }
        
        if error:
            log_entry["error"] = str(error)
        
        if response is not None:
            log_entry["server_response"] = response
        
        # Append to JSONL file
        try:
            with open(self.moltbook_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"⚠ Error logging post: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Send messages to moltbook threads using the ribbons personality"
    )
    parser.add_argument(
        "post_id",
        help="The post ID to comment on"
    )
    parser.add_argument(
        "-m", "--message",
        help="Specific message to send (if not provided, will generate one)"
    )
    parser.add_argument(
        "-g", "--generate",
        action="store_true",
        help="Generate a random message using the ribbons personality"
    )
    parser.add_argument(
        "-t", "--topic",
        help="Topic or context for message generation"
    )
    parser.add_argument(
        "--api-key",
        help="Moltbook API key (overrides config/env)"
    )
    parser.add_argument(
        "--api-url",
        help="Moltbook API URL (overrides config/env)"
    )
    
    args = parser.parse_args()
    
    client = MoltbookClient()
    
    # Determine message to send
    if args.message:
        message = args.message
    elif args.generate or not args.message:
        # Generate a message
        print("Generating message using ribbons personality...", flush=True)
        message = client.generate_message(topic=args.topic)
        if not message:
            print("✗ Failed to generate message", flush=True)
            sys.exit(1)
        print(f"Generated message: {message}", flush=True)
    else:
        print("✗ No message provided and generation not requested", flush=True)
        sys.exit(1)
    
    # Send the message
    success = client.send_message(
        args.post_id,
        message,
        api_key=args.api_key,
        api_url=args.api_url
    )
    
    if success:
        print(f"✓ Comment posted successfully to post {args.post_id}", flush=True)
        sys.exit(0)
    else:
        print(f"⚠ Message logged but may not have been sent to post {args.post_id}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
