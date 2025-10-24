import os
import base64
import re
import datetime
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from notion_client import Client
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from langchain_cerebras import ChatCerebras

# --- Load environment variables ---
load_dotenv()

# Gmail API Setup
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Maintenance Categories
MAINTENANCE_CATEGORIES = [
    "Electrical",
    "Plumbing", 
    "IT Support",
    "HVAC",
    "General Inquiry"
]

def get_gmail_service():
    """Get Gmail service using OAuth 2.0"""
    creds = None
    token_file = "gmail_token.json"
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("❌ Error: credentials.json not found!")
                print("\n📋 To fix this:")
                print("1. Go to: https://console.cloud.google.com/")
                print("2. Create a project and enable Gmail API")
                print("3. Create OAuth 2.0 credentials (Desktop app)")
                print("4. Download credentials.json and save it in this folder")
                raise FileNotFoundError("credentials.json not found.")
            
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)

gmail_service = get_gmail_service()

# Notion Setup
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID")

if NOTION_TOKEN and NOTION_DB_ID:
    notion = Client(auth=NOTION_TOKEN)
else:
    print("⚠️ Notion not configured. Skipping Notion integration.")
    print("   Set NOTION_TOKEN and NOTION_DATABASE_ID in .env file to enable.")
    notion = None

# Slack Setup
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID")

if SLACK_BOT_TOKEN and SLACK_CHANNEL:
    slack_client = WebClient(token=SLACK_BOT_TOKEN)
else:
    print("⚠️ Slack not fully configured. Skipping Slack notifications.")
    print("   Set SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in .env file to enable.")
    slack_client = None

# Cerebras LLM Setup
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")

if CEREBRAS_API_KEY:
    try:
        cerebras_llm = ChatCerebras(
            api_key=CEREBRAS_API_KEY,
            model="llama-4-scout-17b-16e-instruct"
        )
        print("✓ Cerebras LLM initialized successfully")
    except Exception as e:
        print(f"⚠️ Failed to initialize Cerebras LLM: {e}")
        cerebras_llm = None
else:
    print("⚠️ Cerebras API key not configured. Skipping AI summaries.")
    print("   Set CEREBRAS_API_KEY in .env file to enable.")
    cerebras_llm = None


# ----------------------------- #
# 1️⃣ FETCH EMAILS FROM GMAIL
# ----------------------------- #
def fetch_gmail_issues():
    """Fetch recent emails from Gmail"""
    messages = gmail_service.users().messages().list(userId="me", maxResults=10).execute()
    issue_list = []

    for msg in messages.get("messages", []):
        msg_data = gmail_service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = msg_data["payload"]["headers"]

        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")
        snippet = msg_data.get("snippet", "")

        issue = {
            "id": msg["id"],
            "subject": subject, 
            "sender": sender, 
            "date": date, 
            "snippet": snippet
        }
        issue_list.append(issue)

    return issue_list


# ----------------------------- #
# 2️⃣ CLASSIFY & ANALYZE MAINTENANCE ISSUE
# ----------------------------- #
def classify_maintenance_issue(issue):
    """
    Use AI to classify the maintenance issue and provide detailed analysis
    Returns: dict with category, summary, priority, root_cause, action_items
    """
    if not cerebras_llm:
        return {
            "category": "General Inquiry",
            "summary": issue.get("snippet", "No summary available"),
            "priority": "Medium",
            "root_cause": "Unable to determine (AI not configured)",
            "action_items": ["Manual review required"]
        }
    
    try:
        prompt = f"""You are an AI Maintenance Supervisor analyzing facility maintenance requests.

MAINTENANCE REQUEST:
Subject: {issue['subject']}
From: {issue['sender']}
Date: {issue['date']}
Content: {issue['snippet']}

TASK: Analyze this maintenance issue and provide a structured response in JSON format.

CATEGORIES (choose ONE):
- Electrical: Power outages, wiring issues, lighting problems, circuit breakers, electrical safety
- Plumbing: Leaks, clogs, water pressure, pipes, drains, toilets, faucets, water heaters
- IT Support: Computers, network issues, software problems, printers, access cards, security systems
- HVAC: Heating, cooling, air conditioning, ventilation, temperature control, air quality
- General Inquiry: Questions, requests that don't fit above, or multi-category issues

OUTPUT FORMAT (must be valid JSON):
{{
    "category": "<one of the 5 categories above>",
    "summary": "<2-3 sentence summary of the issue>",
    "priority": "<High/Medium/Low>",
    "root_cause": "<likely root cause analysis in 1-2 sentences>",
    "action_items": ["<specific action 1>", "<specific action 2>", "..."]
}}

PRIORITY GUIDELINES:
- High: Safety hazards, complete system failures, affecting multiple people
- Medium: Partial failures, inconvenience, single person affected
- Low: Minor issues, cosmetic problems, non-urgent requests

Respond ONLY with the JSON object, no additional text."""

        response = cerebras_llm.invoke(prompt)
        response_text = response.content.strip()
        
        # Extract JSON from response (handle cases where AI adds extra text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            analysis = json.loads(json_str)
            
            # Validate category
            if analysis.get("category") not in MAINTENANCE_CATEGORIES:
                analysis["category"] = "General Inquiry"
            
            # Ensure all required fields exist
            analysis.setdefault("summary", issue.get("snippet", "No summary"))
            analysis.setdefault("priority", "Medium")
            analysis.setdefault("root_cause", "To be determined")
            analysis.setdefault("action_items", ["Review and assess"])
            
            return analysis
        else:
            raise ValueError("No valid JSON found in response")
        
    except Exception as e:
        print(f"⚠️  AI classification failed: {e}")
        # Fallback classification
        return {
            "category": "General Inquiry",
            "summary": issue.get("snippet", "No summary available"),
            "priority": "Medium",
            "root_cause": "Classification failed - manual review needed",
            "action_items": ["Manual classification required", "Review email content"]
        }


# ----------------------------- #
# 3️⃣ ADD TO NOTION DATABASE (ENHANCED)
# ----------------------------- #
def add_to_notion(issue, analysis):
    """Add maintenance issue to Notion with classification"""
    if not notion:
        print(f"⏭️  Skipping Notion: {issue['subject']}")
        return
    
    try:
        # Prepare action items as bullet points
        action_items_text = "\n".join([f"• {item}" for item in analysis.get("action_items", [])])
        
        # Create Notion page with enhanced properties
        notion.pages.create(
            parent={"database_id": NOTION_DB_ID},
            properties={
                "Subject": {
                    "title": [{"text": {"content": issue["subject"][:2000]}}]
                },
                "Category": {
                    "select": {"name": analysis["category"]}
                },
                "Priority": {
                    "select": {"name": analysis["priority"]}
                },
                "Sender": {
                    "rich_text": [{"text": {"content": issue["sender"][:2000]}}]
                },
                "Date": {
                    "date": {"start": datetime.datetime.now().isoformat()}
                },
                "Status": {
                    "select": {"name": "Open"}
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "📋 Summary"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": analysis["summary"][:2000]}}]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "🔍 Root Cause Analysis"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": analysis["root_cause"][:2000]}}]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "✅ Action Items"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": action_items_text[:2000]}}]
                    }
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "📧 Original Email"}}]
                    }
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": issue["snippet"][:2000]}}]
                    }
                }
            ]
        )
        print(f"✅ Added to Notion: {issue['subject']} [{analysis['category']}]")
    except Exception as e:
        print(f"❌ Failed to add to Notion: {e}")


# ----------------------------- #
# 4️⃣ SEND SLACK NOTIFICATION (ENHANCED)
# ----------------------------- #
def send_slack_message(text, blocks=None):
    """Send message to Slack with optional rich formatting"""
    if not slack_client:
        print(f"⏭️  Skipping Slack notification")
        return
    
    try:
        if blocks:
            slack_client.chat_postMessage(
                channel=SLACK_CHANNEL, 
                text=text,
                blocks=blocks
            )
        else:
            slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=text)
        print(f"✅ Sent to Slack")
    except SlackApiError as e:
        print(f"❌ Slack Error: {e.response['error']}")


def format_maintenance_slack_message(issue, analysis):
    """Create rich Slack message for maintenance issue"""
    
    # Choose emoji based on category
    category_emojis = {
        "Electrical": "⚡",
        "Plumbing": "🚰",
        "IT Support": "💻",
        "HVAC": "🌡️",
        "General Inquiry": "📋"
    }
    
    priority_emojis = {
        "High": "🔴",
        "Medium": "🟡",
        "Low": "🟢"
    }
    
    category_emoji = category_emojis.get(analysis["category"], "📋")
    priority_emoji = priority_emojis.get(analysis["priority"], "🟡")
    
    # Format action items as bullet list
    action_items_text = "\n".join([f"• {item}" for item in analysis.get("action_items", [])])
    
    # Create rich blocks for better formatting
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{category_emoji} New Maintenance Request"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Category:*\n{category_emoji} {analysis['category']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Priority:*\n{priority_emoji} {analysis['priority']}"
                }
            ]
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*From:*\n{issue['sender']}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Date:*\n{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Subject:*\n{issue['subject']}"
            }
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 Summary:*\n{analysis['summary']}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🔍 Root Cause:*\n{analysis['root_cause']}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*✅ Action Items:*\n{action_items_text}"
            }
        }
    ]
    
    # Fallback text for notifications
    fallback_text = f"{category_emoji} {analysis['category']} - {analysis['priority']} Priority: {issue['subject']}"
    
    return fallback_text, blocks


# ----------------------------- #
# 5️⃣ GENERATE DAILY SUMMARY WITH CATEGORY BREAKDOWN
# ----------------------------- #
def generate_daily_summary_with_ai(issues_with_analysis):
    """Generate comprehensive daily summary with category breakdown"""
    if not issues_with_analysis:
        return "📅 *Daily Maintenance Report*\n\nNo issues processed today."
    
    # Count by category
    category_counts = {}
    priority_counts = {"High": 0, "Medium": 0, "Low": 0}
    
    for item in issues_with_analysis:
        analysis = item["analysis"]
        category = analysis["category"]
        priority = analysis["priority"]
        
        category_counts[category] = category_counts.get(category, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0)
    
    # Build summary
    total = len(issues_with_analysis)
    
    if cerebras_llm:
        try:
            # Prepare data for AI
            issues_summary = "\n".join([
                f"{idx}. [{item['analysis']['category']}] {item['analysis']['priority']} - "
                f"{item['issue']['subject']} (from {item['issue']['sender']})"
                for idx, item in enumerate(issues_with_analysis, 1)
            ])
            
            prompt = f"""Create a professional daily maintenance summary report.

STATISTICS:
Total Issues: {total}
By Category: {json.dumps(category_counts)}
By Priority: {json.dumps(priority_counts)}

ISSUES DETAILS:
{issues_summary}

Please provide:
1. Executive summary of the day's maintenance requests
2. Key trends or patterns by category
3. High priority items requiring immediate attention
4. Recommended resource allocation
5. Any systemic issues identified

Format professionally and concisely for management review."""

            response = cerebras_llm.invoke(prompt)
            ai_summary = response.content.strip()
            
            # Add statistics header
            header = f"""📅 *Daily Maintenance Report* - {datetime.datetime.now().strftime('%Y-%m-%d')}

📊 *Quick Stats:*
• Total Issues: {total}
• High Priority: {priority_counts['High']} | Medium: {priority_counts['Medium']} | Low: {priority_counts['Low']}

📂 *By Category:*
"""
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                emoji = {"Electrical": "⚡", "Plumbing": "🚰", "IT Support": "💻", 
                        "HVAC": "🌡️", "General Inquiry": "📋"}.get(cat, "📋")
                header += f"• {emoji} {cat}: {count}\n"
            
            return f"{header}\n{'='*50}\n\n{ai_summary}"
            
        except Exception as e:
            print(f"⚠️  AI daily summary failed: {e}")
    
    # Fallback summary
    summary = f"""📅 *Daily Maintenance Report* - {datetime.datetime.now().strftime('%Y-%m-%d')}

📊 *Summary:*
Total Issues Processed: {total}

📂 *By Category:*
"""
    for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        emoji = {"Electrical": "⚡", "Plumbing": "🚰", "IT Support": "💻", 
                "HVAC": "🌡️", "General Inquiry": "📋"}.get(cat, "📋")
        summary += f"• {emoji} {cat}: {count}\n"
    
    summary += f"""
🚨 *By Priority:*
• 🔴 High: {priority_counts['High']}
• 🟡 Medium: {priority_counts['Medium']}
• 🟢 Low: {priority_counts['Low']}

📋 *Top Issues:*
"""
    for idx, item in enumerate(issues_with_analysis[:5], 1):
        analysis = item["analysis"]
        summary += f"{idx}. [{analysis['category']}] {analysis['priority']}: {item['issue']['subject'][:60]}...\n"
    
    return summary


# ----------------------------- #
# 6️⃣ MAIN WORKFLOW
# ----------------------------- #
def main():
    print("\n" + "=" * 70)
    print("🔧 AI MAINTENANCE SUPERVISOR - Starting Analysis...")
    print("=" * 70 + "\n")
    
    issues = fetch_gmail_issues()
    
    if not issues:
        print("📭 No emails found.")
        return
    
    print(f"📬 Found {len(issues)} maintenance request(s)\n")
    
    issues_with_analysis = []
    
    # Process each email with classification
    for idx, issue in enumerate(issues, 1):
        print(f"\n[{idx}/{len(issues)}] Analyzing: {issue['subject'][:60]}...")
        print(f"   From: {issue['sender']}")
        
        # Classify and analyze the issue
        print("   🤖 Classifying maintenance issue...")
        analysis = classify_maintenance_issue(issue)
        print(f"   ✓ Category: {analysis['category']} | Priority: {analysis['priority']}")
        
        # Store for summary
        issues_with_analysis.append({
            "issue": issue,
            "analysis": analysis
        })
        
        # Add to Notion with classification
        add_to_notion(issue, analysis)
        
        # Send to Slack with rich formatting
        fallback_text, blocks = format_maintenance_slack_message(issue, analysis)
        send_slack_message(fallback_text, blocks)
    
    # Generate and send daily summary
    if slack_client and issues_with_analysis:
        print("\n📊 Generating daily maintenance summary...")
        daily_summary = generate_daily_summary_with_ai(issues_with_analysis)
        print("   ✓ Daily summary generated")
        send_slack_message(daily_summary)
    
    print("\n" + "=" * 70)
    print("✅ Maintenance analysis complete!")
    print(f"   Processed: {len(issues_with_analysis)} issues")
    print("=" * 70)


if __name__ == "__main__":
    main()