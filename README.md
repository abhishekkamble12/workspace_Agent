![WhatsApp Image 2025-10-16 at 17 11 49_e5736b35](https://github.com/user-attachments/assets/35167b8d-5ae0-4182-9144-a11aaa1127af)AI Maintenance Supervisor APIAn intelligent backend service that automates the tracking and processing of maintenance requests. This application fetches issues from Gmail, uses a Cerebras LLM to analyze and classify them, creates detailed tasks in a Notion database, and sends rich, real-time notifications to Slack.✨ Core Features📧 Gmail Integration: Fetches unread emails and treats them as new maintenance requests.🤖 AI-Powered Analysis: Uses a Cerebras LLM to analyze each email and determine its:Category: Electrical, Plumbing, IT Support, HVAC, or General Inquiry.Priority: High, Medium, or Low.Summary: A concise summary of the issue.Root Cause: A likely root cause of the problem.Action Items: A list of suggested next steps.📋 Notion Task Management: Automatically creates a new, detailed page in a Notion database for every classified issue.💬 Rich Slack Notifications: Sends formatted, actionable notifications to a designated Slack channel for immediate visibility.📊 Dashboard API: Provides endpoints to fetch statistics for a frontend dashboard (e.g., issues by category/priority).🚀 Built with FastAPI: A modern, fast, and fully-documented RESTful API.🛠️ Setup and Installation1. PrerequisitesPython 3.8+pip and virtualenvAccess to Google Cloud, Notion, Slack, and Cerebras API keys.2. Clone the RepositoryBashgit clone <your-repository-url>
cd <your-repository-name>
3. Set Up a Virtual EnvironmentBash# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate
4. Install DependenciesCreate a requirements.txt file with the following content:Plaintextfastapi
uvicorn[standard]
python-dotenv
google-api-python-client
google-auth-oauthlib
notion-client
slack-sdk
langchain-cerebras
Then, run the installation command:Bashpip install -r requirements.txt
5. Configure Environment VariablesCreate a file named .env in the root directory and populate it with your credentials.Ini, TOML# .env

# 
![WhatsApp Image 2025-10-16 at 17 11 49_e5736b35](https://github.com/user-attachments/assets/fbc2f9b9-1b86-4661-b9b7-5ccff82daa10)
<img width="772" height="349" alt="image" src="https://github.com/user-attachments/assets/ffdc3314-9861-43ef-b2e9-b688882090ab" />


# Notion API Credentials
NOTION_TOKEN="secret_..."
NOTION_DATABASE_ID="your_notion_database_id"

# Slack API Credentials
SLACK_BOT_TOKEN="xoxb-..."
SLACK_CHANNEL_ID="C123ABCDE"

# Cerebras API Key
CEREBRAS_API_KEY="your_cerebras_api_key"
6. Set Up Google API CredentialsGo to the Google Cloud Console.Create a new project or select an existing one.Enable the Gmail API for your project.Go to "Credentials," click "Create Credentials," and select "OAuth client ID."Choose "Desktop app" as the application type.Click "Download JSON" to download your credentials. Rename the file to credentials.json and place it in the root of your project directory.Note: The first time you run the application, it will open a browser window for you to authenticate with your Google account. This will create a gmail_token.json file to store your credentials for future runs.🚀 Running the ApplicationOnce the setup is complete, you can start the FastAPI server using Uvicorn.Bashuvicorn main:app --host 0.0.0.0 --port 5000 --reload

The API will be running at http://localhost:5000.📚 API EndpointsThe API provides interactive documentation (powered by Swagger UI) where you can test the endpoints directly from your browser.Interactive Docs: http://localhost:5000/docsAlternative Docs: http://localhost:5000/redocMethodEndpointDescriptionGET/api/healthChecks the health of the API.GET/api/config/statusVerifies the configuration status of all external services.GET/api/emailsFetches a list of recent emails from Gmail.POST/api/emails/{email_id}/classifyFetches and classifies a single email by its ID.POST/api/emails/processTriggers the main workflow: fetch, classify, and notify.GET/api/statsRetrieves aggregated statistics for a dashboard.GET/api/categoriesLists all available maintenance categorie
