"""
AI Maintenance Supervisor - FastAPI Backend
FastAPI server for Gmail automation with AI classification
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import json
import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from notion_client import Client
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from langchain_cerebras import ChatCerebras

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(
    title="AI Maintenance Supervisor API",
    description="Automated maintenance issue tracking with AI classification",
    version="1.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAINTENANCE_CATEGORIES = ["Electrical", "Plumbing", "IT Support", "HVAC", "General Inquiry"]

# ==================== PYDANTIC MODELS ====================

class IssueAnalysis(BaseModel):
    category: str
    summary: str
    priority: str
    root_cause: str
    action_items: List[str]

class EmailIssue(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    snippet: str
    analysis: Optional[IssueAnalysis] = None

class ProcessEmailsRequest(BaseModel):
    max_results: Optional[int] = 10
    send_notifications: Optional[bool] = True

class CategoryStats(BaseModel):
    category: str
    count: int
    percentage: float

class DashboardStats(BaseModel):
    total_issues: int
    by_category: List[CategoryStats]
    by_priority: Dict[str, int]
    recent_issues: List[EmailIssue]

class ConfigurationStatus(BaseModel):
    gmail: bool
    notion: bool
    slack: bool
    cerebras: bool
    message: str

# ==================== GLOBAL SERVICES ====================

gmail_service = None
notion_client = None
slack_client = None
cerebras_llm = None

# ==================== INITIALIZATION ====================

def initialize_gmail():
    """Initialize Gmail service"""
    global gmail_service
    try:
        creds = None
        token_file = "gmail_token.json"
        
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("credentials.json"):
                    return False
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_file, "w") as token:
                token.write(creds.to_json())
        
        gmail_service = build("gmail", "v1", credentials=creds)
        return True
    except Exception as e:
        print(f"Gmail initialization failed: {e}")
        return False

def initialize_notion():
    """Initialize Notion client"""
    global notion_client
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_ID")
    
    if token and db_id:
        notion_client = Client(auth=token)
        return True
    return False

def initialize_slack():
    """Initialize Slack client"""
    global slack_client
    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL_ID")
    
    if token and channel:
        slack_client = WebClient(token=token)
        return True
    return False

def initialize_cerebras():
    """Initialize Cerebras LLM"""
    global cerebras_llm
    api_key = os.getenv("CEREBRAS_API_KEY")
    
    if api_key:
        try:
            cerebras_llm = ChatCerebras(
                api_key=api_key,
                model="llama-4-scout-17b-16e-instruct"
            )
            return True
        except Exception as e:
            print(f"Cerebras initialization failed: {e}")
    return False

# Initialize services on startup
@app.on_event("startup")
async def startup_event():
    """Initialize all services on startup"""
    print("🚀 Starting AI Maintenance Supervisor API...")
    initialize_gmail()
    initialize_notion()
    initialize_slack()
    initialize_cerebras()
    print("✅ Initialization complete")

# ==================== CORE FUNCTIONS ====================

def fetch_gmail_issues(max_results: int = 10) -> List[Dict]:
    """Fetch emails from Gmail"""
    if not gmail_service:
        raise HTTPException(status_code=503, detail="Gmail service not initialized")
    
    try:
        messages = gmail_service.users().messages().list(
            userId="me", 
            maxResults=max_results
        ).execute()
        
        issue_list = []
        for msg in messages.get("messages", []):
            msg_data = gmail_service.users().messages().get(
                userId="me", 
                id=msg["id"]
            ).execute()
            
            headers = msg_data["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown)")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")
            snippet = msg_data.get("snippet", "")
            
            issue_list.append({
                "id": msg["id"],
                "subject": subject,
                "sender": sender,
                "date": date,
                "snippet": snippet
            })
        
        return issue_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch emails: {str(e)}")

def classify_maintenance_issue(issue: Dict) -> Dict:
    """Classify maintenance issue using AI"""
    if not cerebras_llm:
        return {
            "category": "General Inquiry",
            "summary": issue.get("snippet", "No summary available"),
            "priority": "Medium",
            "root_cause": "AI not configured - manual review needed",
            "action_items": ["Manual classification required"]
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
- Electrical: Power outages, wiring issues, lighting problems, circuit breakers
- Plumbing: Leaks, clogs, water pressure, pipes, drains, toilets, faucets
- IT Support: Computers, network issues, software problems, printers, access cards
- HVAC: Heating, cooling, air conditioning, ventilation, temperature control
- General Inquiry: Questions, requests that don't fit above

OUTPUT FORMAT (must be valid JSON):
{{
    "category": "<one of the 5 categories above>",
    "summary": "<2-3 sentence summary>",
    "priority": "<High/Medium/Low>",
    "root_cause": "<likely root cause in 1-2 sentences>",
    "action_items": ["<action 1>", "<action 2>"]
}}

Respond ONLY with the JSON object."""

        response = cerebras_llm.invoke(prompt)
        response_text = response.content.strip()
        
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start != -1 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            analysis = json.loads(json_str)
            
            if analysis.get("category") not in MAINTENANCE_CATEGORIES:
                analysis["category"] = "General Inquiry"
            
            return analysis
        else:
            raise ValueError("Invalid JSON response")
            
    except Exception as e:
        print(f"Classification error: {e}")
        return {
            "category": "General Inquiry",
            "summary": issue.get("snippet", "No summary"),
            "priority": "Medium",
            "root_cause": "Classification failed",
            "action_items": ["Manual review required"]
        }

def add_to_notion(issue: Dict, analysis: Dict):
    """Add issue to Notion database"""
    if not notion_client:
        return
    
    try:
        action_items_text = "\n".join([f"• {item}" for item in analysis.get("action_items", [])])
        
        notion_client.pages.create(
            parent={"database_id": os.getenv("NOTION_DATABASE_ID")},
            properties={
                "Subject": {"title": [{"text": {"content": issue["subject"][:2000]}}]},
                "Category": {"select": {"name": analysis["category"]}},
                "Priority": {"select": {"name": analysis["priority"]}},
                "Sender": {"rich_text": [{"text": {"content": issue["sender"][:2000]}}]},
                "Date": {"date": {"start": datetime.datetime.now().isoformat()}},
                "Status": {"select": {"name": "Open"}}
            },
            children=[
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📋 Summary"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": analysis["summary"][:2000]}}]}
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🔍 Root Cause"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": analysis["root_cause"][:2000]}}]}
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": "✅ Action Items"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": action_items_text[:2000]}}]}
                }
            ]
        )
    except Exception as e:
        print(f"Notion error: {e}")

def send_slack_notification(issue: Dict, analysis: Dict):
    """Send Slack notification"""
    if not slack_client:
        return
    
    try:
        category_emojis = {
            "Electrical": "⚡", "Plumbing": "🚰", "IT Support": "💻",
            "HVAC": "🌡️", "General Inquiry": "📋"
        }
        priority_emojis = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        
        category_emoji = category_emojis.get(analysis["category"], "📋")
        priority_emoji = priority_emojis.get(analysis["priority"], "🟡")
        action_items = "\n".join([f"• {item}" for item in analysis.get("action_items", [])])
        
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{category_emoji} New Maintenance Request"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Category:*\n{category_emoji} {analysis['category']}"},
                    {"type": "mrkdwn", "text": f"*Priority:*\n{priority_emoji} {analysis['priority']}"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Subject:*\n{issue['subject']}"}
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*📋 Summary:*\n{analysis['summary']}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🔍 Root Cause:*\n{analysis['root_cause']}"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*✅ Action Items:*\n{action_items}"}
            }
        ]
        
        slack_client.chat_postMessage(
            channel=os.getenv("SLACK_CHANNEL_ID"),
            text=f"{category_emoji} {analysis['category']} - {issue['subject']}",
            blocks=blocks
        )
    except SlackApiError as e:
        print(f"Slack error: {e}")

# ==================== API ENDPOINTS ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Maintenance Supervisor API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/api/config/status", response_model=ConfigurationStatus)
async def get_config_status():
    """Get configuration status"""
    gmail_ok = gmail_service is not None
    notion_ok = notion_client is not None
    slack_ok = slack_client is not None
    cerebras_ok = cerebras_llm is not None
    
    all_configured = all([gmail_ok, notion_ok, slack_ok, cerebras_ok])
    
    return {
        "gmail": gmail_ok,
        "notion": notion_ok,
        "slack": slack_ok,
        "cerebras": cerebras_ok,
        "message": "All services configured" if all_configured else "Some services not configured"
    }

@app.get("/api/emails", response_model=List[EmailIssue])
async def get_emails(max_results: int = 10):
    """Fetch emails from Gmail"""
    try:
        issues = fetch_gmail_issues(max_results)
        return [EmailIssue(**issue) for issue in issues]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emails/{email_id}/classify", response_model=EmailIssue)
async def classify_email(email_id: str):
    """Classify a specific email"""
    try:
        # Fetch single email
        issues = fetch_gmail_issues(max_results=50)
        issue = next((i for i in issues if i["id"] == email_id), None)
        
        if not issue:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Classify
        analysis = classify_maintenance_issue(issue)
        issue["analysis"] = analysis
        
        return EmailIssue(**issue)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/emails/process")
async def process_emails(
    request: ProcessEmailsRequest,
    background_tasks: BackgroundTasks
):
    """Process emails: fetch, classify, and optionally send notifications"""
    try:
        # Fetch emails
        issues = fetch_gmail_issues(request.max_results)
        
        if not issues:
            return {
                "status": "success",
                "message": "No emails found",
                "processed": 0,
                "issues": []
            }
        
        processed_issues = []
        
        for issue in issues:
            # Classify
            analysis = classify_maintenance_issue(issue)
            issue["analysis"] = analysis
            processed_issues.append(issue)
            
            # Add to Notion (background)
            if notion_client:
                background_tasks.add_task(add_to_notion, issue, analysis)
            
            # Send Slack notification (background)
            if request.send_notifications and slack_client:
                background_tasks.add_task(send_slack_notification, issue, analysis)
        
        return {
            "status": "success",
            "message": f"Processed {len(processed_issues)} emails",
            "processed": len(processed_issues),
            "issues": processed_issues
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Fetch recent issues
        issues = fetch_gmail_issues(max_results=20)
        
        # Classify all for stats
        classified_issues = []
        for issue in issues:
            analysis = classify_maintenance_issue(issue)
            issue["analysis"] = analysis
            classified_issues.append(issue)
        
        # Calculate statistics
        category_counts = {}
        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        
        for issue in classified_issues:
            if issue.get("analysis"):
                cat = issue["analysis"]["category"]
                pri = issue["analysis"]["priority"]
                category_counts[cat] = category_counts.get(cat, 0) + 1
                priority_counts[pri] = priority_counts.get(pri, 0) + 1
        
        total = len(classified_issues)
        category_stats = [
            CategoryStats(
                category=cat,
                count=count,
                percentage=round((count / total) * 100, 1) if total > 0 else 0
            )
            for cat, count in category_counts.items()
        ]
        
        return DashboardStats(
            total_issues=total,
            by_category=category_stats,
            by_priority=priority_counts,
            recent_issues=[EmailIssue(**issue) for issue in classified_issues[:5]]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    """Get available maintenance categories"""
    return {
        "categories": MAINTENANCE_CATEGORIES,
        "emojis": {
            "Electrical": "⚡",
            "Plumbing": "🚰",
            "IT Support": "💻",
            "HVAC": "🌡️",
            "General Inquiry": "📋"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=True)