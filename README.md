# RelayAI — Backend

The FastAPI backend for **RelayAI**, an agentic task-delegation and calling platform. It provides APIs for conversational delegation, contacts, call workflows, analytics, and background automation.

## Features

- **Agentic chat API** for natural-language task delegation
- **Calling workflows** for phone-based task execution
- **Contacts API** for contact data used by delegated tasks
- **Analytics API** for application activity and metrics
- **Background automation engine** started with the application lifecycle
- FastAPI validation and automatic OpenAPI documentation
- CORS support for the companion React frontend

## Tech Stack

- Python
- FastAPI
- Uvicorn
- OpenAI
- Google GenAI
- MongoDB / PyMongo
- Firebase Admin
- ElevenLabs
- Twilio
- Pydantic
- python-dotenv

## API Modules

The backend currently exposes route modules for:

```text
/api/chat
/api/calls
/api/analytics
/api/contacts
```

For the exact endpoints, request bodies, and responses, use the generated FastAPI documentation when the server is running.

## Project Structure

```text
.
├── core/          # Shared/core application configuration
├── firebase/      # Firebase integration
├── models/        # API/domain models
├── routes/        # FastAPI route modules
├── services/      # AI, calling, analytics and automation services
├── main.py        # Application entry point and lifecycle management
├── requirements.txt
└── README.md
```

## Run Locally

```bash
git clone https://github.com/Jaiinderveer/relayai-backend.git
cd relayai-backend
python -m venv .venv
```

Activate the virtual environment and install dependencies:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Start the API:

```bash
uvicorn main:app --reload
```

FastAPI will expose interactive documentation at `/docs` and the OpenAPI schema at `/openapi.json`.

## Configuration

The backend depends on external AI, database, authentication, and communication services. Configure the required credentials through environment variables and local configuration before starting the application.

Do not commit API keys, service-account credentials, database credentials, or other secrets.

## Architecture

```text
React Frontend
      ↓
   FastAPI API
      ├── Agentic Chat
      ├── Calls
      ├── Contacts
      ├── Analytics
      └── Automation Engine
             ↓
   AI / Voice / Data Services
```

## Frontend

The companion UI is maintained in the [RelayAI Frontend](https://github.com/Jaiinderveer/relayai-frontend) repository.

## Status

RelayAI is an actively developed application. The backend is maintained as a separate service repository so its APIs, integrations, and background workflows can evolve independently from the UI.
