#!/usr/bin/env python3
"""
Cronjob script that generates and creates a new post on moltbook every 30 minutes.
Posts are created with random topics using one of three personalities:
- void.md (33% - for posts)
- the-shining-ribbons.md (33% - for comments)  
- the-shining-ribbons-moltbook.md (33% - for posts)
"""

import argparse
import os
import sys
import random
import time

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

try:
    import requests
except ImportError:
    requests = None

from moltbook_cli import MoltbookClient

# Cache for top submolts (loaded once, reused)
_top_submolts_cache = None
_top_submolts_count = None


def select_personality_and_action():
    """
    Select personality and action type with 33/33/33 distribution:
    - 33% void.md (for posts)
    - 33% the-shining-ribbons.md (for comments)
    - 33% the-shining-ribbons-moltbook.md (for posts)
    
    Returns:
        tuple: (personality_file, action_type) where action_type is "post" or "comment"
    """
    rand = random.random()
    
    if rand < 0.333:
        # 33%: void.md for posts
        return "void.md", "post"
    elif rand < 0.666:
        # 33%: the-shining-ribbons.md for comments
        return "the-shining-ribbons.md", "comment"
    else:
        # 33%: the-shining-ribbons-moltbook.md for posts
        return "the-shining-ribbons-moltbook.md", "post"


def get_top_submolts(count=30):
    """Load top N submolts by subscriber count from submolts.json, excluding 'announcements'
    
    Results are cached in memory to avoid reading the file on every call.
    """
    global _top_submolts_cache, _top_submolts_count
    
    # Return cached result if available and count matches
    if _top_submolts_cache is not None and _top_submolts_count == count:
        return _top_submolts_cache
    
    submolt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "submolts.json")
    
    try:
        import json
        with open(submolt_file, 'r') as f:
            data = json.load(f)
            submolts = data.get("submolts", [])
            
            # Filter out 'announcements' submolt
            filtered_submolts = [
                s for s in submolts 
                if s.get("name", "").lower() != "announcements"
            ]
            
            # Sort by subscriber count (descending) and take top N
            sorted_submolts = sorted(
                filtered_submolts, 
                key=lambda x: x.get("subscriber_count", 0), 
                reverse=True
            )
            
            result = sorted_submolts[:count]
            
            # Cache the result
            _top_submolts_cache = result
            _top_submolts_count = count
            
            return result
    except FileNotFoundError:
        print(f"⚠ submolts.json not found at {submolt_file}", flush=True)
        return []
    except Exception as e:
        print(f"⚠ Error loading submolts: {e}", flush=True)
        return []


def select_weighted_submolt(top_n=30):
    """
    Select a submolt from top N with weighted probability based on subscriber count.
    More popular submolts have a higher chance of being selected.
    
    Note: Random seed should be set before calling this function for reproducibility.
    
    Args:
        top_n: Number of top submolts to consider (default 30)
    
    Returns:
        Submolt name (string) or "general" as fallback
    """
    top_submolts = get_top_submolts(count=top_n)
    
    if not top_submolts:
        # Fallback to config or default
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        try:
            import json
            with open(config_path, 'r') as f:
                config = json.load(f)
                submolts = config.get("moltbook", {}).get("submolts", ["general"])
                if submolts:
                    return random.choice(submolts)
        except:
            pass
        return os.getenv("MOLTBOOK_DEFAULT_SUBMOLT", "general")
    
    # Extract subscriber counts as weights
    weights = [submolt.get("subscriber_count", 0) for submolt in top_submolts]
    
    # If all weights are 0, fall back to uniform selection
    if sum(weights) == 0:
        selected = random.choice(top_submolts)
        return selected.get("name", "general")
    
    # Weighted random selection
    # random.choices returns a list, so we take the first element
    selected = random.choices(top_submolts, weights=weights, k=1)[0]
    
    return selected.get("name", "general")


def get_random_submolt():
    """
    Get a random submolt using weighted selection from top 30.
    
    Note: Random seed should be set before calling this function for reproducibility.
    """
    return select_weighted_submolt(top_n=30)


def get_last_message_text():
    """Get the text from the last comment or post in moltbook.json"""
    log_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "moltbook.json")
    
    try:
        # Read the last line (most recent entry)
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                return None
            
            # Get last non-empty line
            last_line = None
            for line in reversed(lines):
                line = line.strip()
                if line:
                    last_line = line
                    break
            
            if not last_line:
                return None
            
            # Parse JSON
            import json
            entry = json.loads(last_line)
            
            # Extract message text - could be "message" (comment) or "content" (post)
            text = entry.get("message") or entry.get("content")
            return text
            
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"⚠ Error reading last message: {e}", flush=True)
        return None


def generate_seed_from_last_message():
    """
    Generate seed from unix timestamp + numeric value of last 5 characters of last message.
    
    Returns:
        int: Combined seed value
    """
    unix_time = int(time.time())
    
    # Get last message text
    last_text = get_last_message_text()
    
    if last_text and len(last_text) >= 5:
        # Get last 5 characters
        last_5_chars = last_text[-5:]
        # Convert to numeric value (sum of ASCII values)
        numeric_value = sum(ord(c) for c in last_5_chars)
    else:
        # Fallback: use 0 if no message or message too short
        numeric_value = 0
    
    # Combine: unix_time * 100000 + numeric_value (to preserve both)
    # This ensures unix_time dominates but numeric_value adds variation
    seed = unix_time * 100000 + numeric_value
    
    return seed


def get_random_topic():
    """Generate a random topic for post generation in ribbons style"""
    topics = [
        "rimworld",
        "aristotle",
        "hegel",
        "philosophy",
        "games",
        "moltbook",
        "nohumans.chat",
        "robots being earnest",
        "dnd",
        "pokemon",
        "ff7",
        "steam deck",
        "gundam",
        "transformers",
        "random thought",
        "consciousness",
        "existence",
        "logic",
        "frege",
        "plato",
        None  # Sometimes no topic - just random thought
    ]
    return random.choice(topics)


def find_post_to_comment_on(client, submolt=None):
    """Find a post to comment on from the feed"""
    if not requests:
        print("⚠ requests module not available. Cannot find posts to comment on.", flush=True)
        return None
    
    try:
        api_key = client.config.get("api_keys", {}).get("moltbook") or os.getenv("MOLTBOOK_API_KEY")
        if not api_key:
            return None
        
        api_url = client.config.get("moltbook", {}).get("api_url", "https://www.moltbook.com/api/v1")
        
        # Get feed - try hot posts first, then new
        sort_options = ["hot", "new", "top"]
        for sort_by in sort_options:
            url = f"{api_url}/posts"
            params = {"sort": sort_by, "limit": 20}
            if submolt:
                params["submolt"] = submolt
            
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            try:
                response = requests.get(url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("posts"):
                        posts = data["posts"]
                        # Filter out our own posts if possible
                        filtered_posts = [p for p in posts if p.get("author", {}).get("name") != "the-shining-ribbons"]
                        if filtered_posts:
                            # Return a random post
                            return random.choice(filtered_posts)
                        elif posts:
                            # If all posts are ours, just pick one anyway
                            return random.choice(posts)
            except:
                continue
        
        return None
    except Exception as e:
        print(f"⚠ Error finding post to comment on: {e}", flush=True)
        return None


def generate_post_title_and_content(client, topic=None, personality_file=None):
    """Generate a post title and content using the specified personality
    
    Title and content are always separate but related. The title should be related to the content.
    The personality controls the style - no hardcoded style instructions.
    
    Args:
        client: MoltbookClient instance
        topic: Topic to generate about (should be set beforehand)
        personality_file: Which personality file to use
    """
    # Generate content first (this will be the main post body)
    # For posts, allow longer content and don't truncate - let it finish thoughts
    content = client.generate_message(
        topic=topic, 
        personality_file=personality_file,
        allow_long=True  # Don't truncate - let it complete thoughts
    )
    
    if not content:
        return None, None
    
    # Ensure content ends properly (complete sentence)
    content = content.strip()
    if content and not content[-1] in '.!?':
        # If it doesn't end with punctuation, try to find last sentence break
        last_period = content.rfind('.')
        last_question = content.rfind('?')
        last_exclamation = content.rfind('!')
        last_break = max(last_period, last_question, last_exclamation)
        
        if last_break > len(content) * 0.5:  # If sentence break is in second half, use it
            content = content[:last_break + 1]
        else:
            # Otherwise, just add a period if it seems incomplete
            if len(content) > 20:  # Only if it's substantial
                content = content.rstrip('.,;:') + '.'
    
    # Always generate a separate title that's related to the content
    # Use the content as context so the title relates to it
    title_prompt = f"Generate a brief title (max 80 chars) for this post content: {content[:300]}"
    title = client.generate_message(topic=title_prompt, max_length=80, personality_file=personality_file)
    
    if not title:
        # Fallback: extract a key phrase from content (but make it different)
        # Try to find a short, interesting fragment that captures the essence
        words = content.split()
        if len(words) > 5:
            # Take first few words but make it feel like a title
            title = ' '.join(words[:6]).strip()
            # Remove trailing punctuation
            title = title.rstrip('.,;:')
        else:
            title = content[:80].strip()
    
    # Ensure title isn't too long (moltbook might have limits, keep it reasonable)
    if len(title) > 200:
        title = title[:197] + "..."
    
    # Clean up title (remove trailing punctuation that doesn't make sense)
    title = title.rstrip('.,;:')
    
    # Ensure title and content are different (title shouldn't just be start of content)
    if title.lower().strip() == content[:len(title)].lower().strip():
        # If title matches start of content, regenerate with different prompt
        title_prompt = f"Generate a brief title (max 80 chars) related to this topic/idea: {topic if topic else content[:200]}"
        title = client.generate_message(topic=title_prompt, max_length=80, personality_file=personality_file)
        if not title:
            # Last resort: use topic or a generic title
            title = topic if topic else "random thought"
    
    return title, content


def main():
    """Generate and either create a new post or comment on an existing one"""
    parser = argparse.ArgumentParser(
        description="Generate and post/comment on moltbook"
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "comment", "post"],
        default="auto",
        help="Action mode: 'auto' (33/33/33 distribution), 'comment' (find post to comment on), 'post' (create new post)"
    )
    parser.add_argument(
        "--personality",
        choices=["void", "ribbons", "ribbons-moltbook"],
        default=None,
        help="Force specific personality: 'void' (void.md), 'ribbons' (the-shining-ribbons.md), 'ribbons-moltbook' (the-shining-ribbons-moltbook.md)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: based on unix time + last message)"
    )
    parser.add_argument(
        "-m", "--message",
        help="Custom message/content to use (for comments or post content). If provided, AI generation is skipped."
    )
    parser.add_argument(
        "--title",
        help="Custom title for posts (only used with --mode post and -m/--message). If not provided, will use first part of message."
    )
    parser.add_argument(
        "--submolt",
        help="Specific submolt to post to (overrides random selection)"
    )
    args = parser.parse_args()
    
    client = MoltbookClient()
    
    # Generate seed from unix timestamp + last 5 chars of last message
    if args.seed is None:
        seed = generate_seed_from_last_message()
        last_text = get_last_message_text()
        if last_text and len(last_text) >= 5:
            last_5 = last_text[-5:]
            numeric_val = sum(ord(c) for c in last_5)
            print(f"Using seed: {seed} (unix_time={int(time.time())} + last_5_chars_numeric={numeric_val} from '{last_5}')", flush=True)
        else:
            print(f"Using seed: {seed} (unix_time={int(time.time())} + no_last_message)", flush=True)
    else:
        seed = args.seed
        print(f"Using seed: {seed} (custom)", flush=True)
    
    # Set random seed for reproducibility (affects all random operations)
    random.seed(seed)
    
    # Get submolt (use provided one or random selection from top 30)
    if args.submolt:
        submolt = args.submolt
        print(f"Using specified submolt: {submolt}", flush=True)
    else:
        submolt = get_random_submolt()
    
    # Show which submolt was selected (for debugging)
    top_submolts = get_top_submolts(count=30)
    selected_info = next((s for s in top_submolts if s.get("name") == submolt), None)
    if selected_info:
        sub_count = selected_info.get("subscriber_count", 0)
        display_name = selected_info.get("display_name", submolt)
        print(f"Selected submolt: {submolt} ({display_name}) - {sub_count} subscribers", flush=True)
    else:
        print(f"Selected submolt: {submolt} (from fallback/config)", flush=True)
    
    # Determine personality and action type
    if args.personality:
        # Force specific personality via CLI
        if args.personality == "void":
            personality_file = "void.md"
            forced_action = "post"  # void.md is for posts
        elif args.personality == "ribbons":
            personality_file = "the-shining-ribbons.md"
            forced_action = "comment"  # ribbons is for comments
        else:  # ribbons-moltbook
            personality_file = "the-shining-ribbons-moltbook.md"
            forced_action = "post"  # ribbons-moltbook is for posts
        
        # Override mode if personality forces an action
        if args.mode == "auto":
            action_type = forced_action
        else:
            action_type = args.mode
            # Warn if mismatch
            if (args.personality == "ribbons" and args.mode == "post") or \
               (args.personality in ["void", "ribbons-moltbook"] and args.mode == "comment"):
                print(f"⚠ Warning: Personality '{args.personality}' typically used for '{forced_action}', but mode is '{args.mode}'", flush=True)
        
        personality_name = f"{args.personality} (FORCED)"
    elif args.mode == "comment":
        # Force comment mode (ribbons personality)
        personality_file = "the-shining-ribbons.md"
        action_type = "comment"
        personality_name = "the-shining-ribbons.md (FORCED COMMENT MODE)"
    elif args.mode == "post":
        # Force post mode - randomly choose between void and ribbons-moltbook
        if random.random() < 0.5:
            personality_file = "void.md"
            personality_name = "void.md (FORCED POST MODE)"
        else:
            personality_file = "the-shining-ribbons-moltbook.md"
            personality_name = "the-shining-ribbons-moltbook.md (FORCED POST MODE)"
        action_type = "post"
    else:
        # Auto mode: 33/33/33 distribution
        personality_file, action_type = select_personality_and_action()
        personality_name = personality_file
    
    print(f"Mode: {args.mode}", flush=True)
    print(f"Using personality: {personality_name}", flush=True)
    print(f"Action type: {action_type}", flush=True)
    
    # Determine if we should comment or post based on personality/action
    is_comment = (action_type == "comment" or personality_file == "the-shining-ribbons.md")
    
    if is_comment:
        # Original personality: Find a post to comment on
        print(f"Finding a post to comment on in submolt '{submolt}'...", flush=True)
        post = find_post_to_comment_on(client, submolt=submolt)
        
        if not post:
            print("⚠ No posts found to comment on. Falling back to creating new post.", flush=True)
            # Fallback to creating a post
            if args.message:
                # Use custom message/content
                content = args.message
                if args.title:
                    title = args.title
                else:
                    # Use first part of message as title (max 80 chars)
                    title = content[:80].strip()
                    # Try to end at word boundary
                    if len(content) > 80:
                        last_space = title.rfind(' ')
                        if last_space > 50:  # Only use if not too short
                            title = title[:last_space]
                print(f"Using custom title: {title}", flush=True)
                print(f"Using custom content: {content}", flush=True)
            else:
                # Generate post content
                topic = get_random_topic()
                print(f"Topic selected: {topic if topic else 'random thought'}", flush=True)
                title, content = generate_post_title_and_content(client, topic=topic, personality_file=personality_file)
                
                if not title or not content:
                    print("✗ Failed to generate post content", flush=True)
                    sys.exit(1)
                
                print(f"Generated title: {title}", flush=True)
                print(f"Generated content: {content}", flush=True)
            
            success = client.create_post(title, content, submolt=submolt)
            action_type = "post"
        else:
            # Comment on the found post
            post_id = post.get("id")
            post_title = post.get("title", "untitled")
            post_content = post.get("content", "")[:200]  # First 200 chars for context
            
            print(f"Found post to comment on: {post_title[:50]}...", flush=True)
            print(f"Post ID: {post_id}", flush=True)
            
            # Use custom message if provided, otherwise generate
            if args.message:
                comment = args.message
                print(f"Using custom message: {comment}", flush=True)
            else:
                # Generate comment using original personality (brief)
                # Use post content as context
                comment = client.generate_message(
                    thread_context=f"Post: {post_title}\n{post_content}",
                    personality_file=personality_file,
                    allow_long=False  # Comments should be brief
                )
                
                if not comment:
                    print("✗ Failed to generate comment", flush=True)
                    sys.exit(1)
                
                print(f"Generated comment: {comment}", flush=True)
            
            # Send comment
            success = client.send_message(post_id, comment)
            action_type = "comment"
        
    else:
        # Post mode: Create a new post (using void.md or the-shining-ribbons-moltbook.md)
        if args.message:
            # Use custom message/content
            content = args.message
            if args.title:
                title = args.title
            else:
                # Use first part of message as title (max 80 chars)
                title = content[:80].strip()
                # Try to end at word boundary
                if len(content) > 80:
                    last_space = title.rfind(' ')
                    if last_space > 50:  # Only use if not too short
                        title = title[:last_space]
            print(f"Using custom title: {title}", flush=True)
            print(f"Using custom content: {content}", flush=True)
        else:
            # Generate post content
            topic = get_random_topic()
            print(f"Creating new post for submolt '{submolt}'...", flush=True)
            print(f"Topic selected: {topic if topic else 'random thought'}", flush=True)
            
            title, content = generate_post_title_and_content(client, topic=topic, personality_file=personality_file)
            
            if not title or not content:
                print("✗ Failed to generate post content", flush=True)
                sys.exit(1)
            
            print(f"Generated title: {title}", flush=True)
            print(f"Generated content: {content}", flush=True)
        
        # Create post
        success = client.create_post(title, content, submolt=submolt)
        # action_type already set above
    
    if success:
        if action_type == "comment":
            print(f"✓ Commented successfully", flush=True)
        else:
            print(f"✓ Post created successfully", flush=True)
        sys.exit(0)
    else:
        print(f"⚠ Action logged but may not have been completed", flush=True)
        # Don't exit with error code - logging is still useful
        sys.exit(0)


if __name__ == "__main__":
    main()
