# AI Maintenance Supervisor API

An intelligent backend service that automates the tracking and processing of maintenance requests. This application fetches issues from Gmail, uses the Cerebras `llama-4-scout-17b-16e-instruct` LLM to analyze and classify them, creates detailed tasks in a Notion database, and sends rich, real-time notifications to Slack.

✨ Core Features

📧 **Gmail Integration**: Fetches unread emails and treats them as new maintenance requests.
🤖 **AI-Powered Analysis**: Uses a Cerebras LLM (`llama-4-scout-17b-16e-instruct`) to analyze each email and determine its:
    *   **Category**: Electrical, Plumbing, IT Support, HVAC, or General Inquiry.
    *   **Priority**: High, Medium, or Low.
    *   **Summary**: A concise summary of the issue.
    *   **Root Cause**: A likely root cause of the problem.
    *   **Action Items**: A list of suggested next steps.
📋 **Notion Task Management**: Automatically creates a new, detailed page in a Notion database for every classified issue.
💬 **Rich Slack Notifications**: Sends formatted, actionable notifications to a designated Slack channel for immediate visibility.
📊 **Dashboard API**: Provides endpoints to fetch statistics for a frontend dashboard (e.g., issues by category/priority).
🚀 **Built with FastAPI**: A modern, fast, and fully-documented RESTful API.

🛠️ Setup and Installation

1.  **Prerequisites**
    *   Python 3.8+
    *   `pip` and `virtualenv`
    *   Access to Google Cloud, Notion, Slack, and Cerebras API keys.

2.  **Clone the Repository**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-name>
    ```

3.  **Set Up a Virtual Environment**
    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

4.  **Install Dependencies**
    Create a `requirements.txt` file with the following content:
    ```plaintext
    fastapi
    uvicorn[standard]
    python-dotenv
    google-api-python-client
    google-auth-oauthlib
    google-auth-httplib2
    notion-client
    slack-sdk
    slack-bolt
    flask
    langchain-cerebras
    ```
    Then, run the installation command:
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables**
    Create a file named `.env` in the root directory and populate it with your credentials.
    ```ini, TOML
    # .env

    # Notion API Credentials
    NOTION_TOKEN="secret_..."
    NOTION_DATABASE_ID="your_notion_database_id"

    # Slack API Credentials
    SLACK_BOT_TOKEN="xoxb-..."
    SLACK_CHANNEL_ID="C123ABCDE"
    SLACK_SIGNING_SECRET="your_slack_signing_secret"
    SLACK_BOT_USER_ID="your_slack_bot_user_id" # Can be obtained by running the bot once or using Slack API

    # Cerebras API Key
    CEREBRAS_API_KEY="your_cerebras_api_key"
    ```

6.  **Set Up Google API Credentials**
    Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Create a new project or select an existing one.
    *   Enable the Gmail API for your project.
    *   Go to "Credentials," click "Create Credentials," and select "OAuth client ID."
    *   Choose "Desktop app" as the application type.
    *   Click "Download JSON" to download your credentials. Rename the file to `credentials.json` and place it in the root of your project directory.
    *Note: The first time you run the application, it will open a browser window for you to authenticate with your Google account. This will create a `gmail_token.json` file to store your credentials for future runs.*

🚀 Running the Application

Once the setup is complete, you can start the FastAPI server using Uvicorn.
```bash
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```
The API will be running at `http://localhost:5000`.

📚 API Endpoints

The API provides interactive documentation (powered by Swagger UI) where you can test the endpoints directly from your browser.
*   **Interactive Docs**: `http://localhost:5000/docs`
*   **Alternative Docs**: `http://localhost:5000/redoc`

* 
<img width="1280" height="841" alt="image" src="https://github.com/user-attachments/assets/8abcc34f-a913-491e-a7e2-ae27dd52e1ab" />
<img width="772" height="349" alt="image" src="https://github.com/user-attachments/assets/0b48e0f5-741a-4745-8c5d-b5479bf04783" />

| Method | Endpoint                       | Description                                                 |
| :----- | :----------------------------- | :---------------------------------------------------------- |
| `GET`  | `/api/health`                  | Checks the health of the API.                               |
| `GET`  | `/api/config/status`           | Verifies the configuration status of all external services. |
| `GET`  | `/api/emails`                  | Fetches a list of recent emails from Gmail.                 |
| `POST` | `/api/emails/{email_id}/classify` | Fetches and classifies a single email by its ID.            |
| `POST` | `/api/emails/process`          | Triggers the main workflow: fetch, classify, and notify.    |
| `GET`  | `/api/stats`                   | Retrieves aggregated statistics for a dashboard.            |
| `GET`  | `/api/categories`              | Lists all available maintenance categories.                 |
