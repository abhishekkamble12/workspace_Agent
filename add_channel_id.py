"""
Quick script to add Slack Channel ID to .env file
"""
import os
from dotenv import load_dotenv, set_key, find_dotenv

print("=" * 60)
print("Add Slack Channel ID")
print("=" * 60)
print()

print("📋 How to get your Slack Channel ID:")
print()
print("1. Open Slack in your browser")
print("2. Go to the channel: #ai_experiment_tasks")
print("3. Look at the URL in the address bar")
print()
print("   The URL will look like:")
print("   https://app.slack.com/client/T09LRCYQDM3/C1234567890/...")
print()
print("4. Copy the part after the last '/' (the channel ID)")
print("   Example: C1234567890")
print()
print("=" * 60)
print()

# Get channel ID from user
channel_id = input("Enter your Slack Channel ID: ").strip()

if channel_id:
    # Remove any leading/trailing quotes or spaces
    channel_id = channel_id.strip('"').strip("'").strip()
    
    print()
    print(f"✓ Channel ID: {channel_id}")
    print()
    
    # Update .env file
    env_path = find_dotenv()
    if env_path:
        set_key(env_path, "SLACK_CHANNEL_ID", channel_id)
        print(f"✅ Added SLACK_CHANNEL_ID to {env_path}")
        print()
        print("Now run: python gmail.py")
    else:
        print("❌ Could not find .env file")
else:
    print()
    print("❌ No channel ID provided")

print()
print("=" * 60)

