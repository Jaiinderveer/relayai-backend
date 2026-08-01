import json
import re
from core.config import gemini_client
from services.task_service import (
    format_save_task, format_update_task, format_delete_task, 
    format_list_tasks, format_fetch_filtered_tasks, format_fetch_call_history,
    format_save_contact, format_update_contact, format_delete_contact,
    format_search_contacts
)
from google.genai import types 
# Note: In Phase 4, we will add the remaining formatters (fetch_call_history, save_contact, etc.) to task_service.py
from firebase.db_helper import get_dashboard_metrics

# Rebranded Greeting Regex
FAST_GREETING_REGEX = re.compile(
    r"^(hi|hello|hey|good morning|good evening|good afternoon|thanks|thank you|bye|how are you\??|who are you\??|what can you do\??|help|nice to meet you)[\s!.]*$",
    re.IGNORECASE
)

# Copied exactly from ai_agent.py
tools = [
    {
        "type": "function",
        "name": "save_task",
        "description": "Save a new task.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "contact_name": {"type": "string"},
                "action": {"type": "string", "enum": ["call","email","message","other"]},
            },
            "required": ["title", "description", "action", "contact_name"],
        },
    },
    {
        "type": "function",
        "name": "list_tasks",
        "description": "Retrieve and display ALL tasks stored in database without filtering.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "type": "function",
        "name": "delete_task",
        "description": "Delete a task by title.",
        "parameters": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"]
        }
    },
    {
        "type": "function",
        "name": "update_task",
        "description": "Update an existing task.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "action": {"type": "string"},
                "contact_name": {"type": "string"}
            },
            "required": ["title"]
        }
    },
    {
        "type": "function",
        "name": "fetch_filtered_tasks",
        "description": "Fetch generic TASKS. Do NOT use this tool for calls.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["PENDING", "COMPLETED", "FAILED"]},
                "date_preset": {"type": "string", "enum": ["today", "yesterday"]}
            }
        }
    },
    {
        "type": "function",
        "name": "fetch_call_history",
        "description": "Fetch CALLS specifically (e.g. 'which call failed', 'show failed calls', 'call history'). ALWAYS execute immediately without asking for clarification.",
        "parameters": {
            "type": "object",
            "properties": {
                "call_status_intent": {
                    "type": "string", 
                    "enum": ["FAILED", "COMPLETED", "PENDING", "ALL"],
                    "description": "High level intent: FAILED for failed calls, COMPLETED for completed calls, PENDING for pending/calling calls, ALL for all calls."
                },
                "date_preset": {
                    "type": "string", 
                    "enum": ["today", "yesterday", "this_week"],
                    "description": "ONLY pass if user explicitly typed 'today', 'yesterday', or 'this_week' in their input."
                }
            }
        }
    },
    {
        "type": "function",
        "name": "save_contact",
        "description": "Save a new contact.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "phone": {"type": "string"}},
            "required": ["name", "phone"]
        }
    },
    {
        "type": "function",
        "name": "update_contact",
        "description": "Update an existing contact.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "phone": {"type": "string"}},
            "required": ["name", "phone"]
        }
    },
    {
        "type": "function",
        "name": "delete_contact",
        "description": "Delete a contact.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        }
    },
    {
        "type": "function",
        "name": "search_contacts",
        "description": "Search for a specific contact.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}}
        }
    },
    {
        "type": "function",
        "name": "analyze_dashboard_data",
        "description": "Fetch aggregated dashboard analytics and numbers (counts, totals, success rates). Use this ONLY when asked 'how many', 'summarize', or for broad statistics.",
        "parameters": {"type": "object", "properties": {}}
    }
]
def agentic_save(input_list: list) -> str:
    user_query = next((item['content'] for item in reversed(input_list) if item['role'] == 'user'), "")
    
    system_msg_content = """
        You are RelayAI, an AI assistant for a Workforce and Call Management platform.

        Use the provided functions whenever the user's request requires data retrieval or modification.

        Never invent task, contact, or call information.

        If a suitable function exists, call it.

        Only answer directly when no function is needed.

        Never use LaTeX.
        """

    system_msg = {"role": "system", "content": system_msg_content}

    if input_list and input_list[0].get("role") != "system":
        input_list.insert(0, system_msg)
    else:
        input_list[0] = system_msg

# Convert OpenAI tool schema to Gemini tool schema
    function_declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters_json_schema=tool["parameters"],
        )
        for tool in tools
    ]

    gemini_tools = [
        types.Tool(function_declarations=function_declarations)
    ]

    # Convert OpenAI messages to Gemini contents
    contents = []

    for msg in input_list:
        if msg["role"] == "system":
            continue

        role = "model" if msg["role"] == "assistant" else "user"

        contents.append(
            types.Content(
                role=role,
                parts=[types.Part(text=msg["content"])]
            )
        )

    response = gemini_client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_msg_content,
            tools=gemini_tools,
            temperature=0
        )
    )
    
    function_call = None
    assistant_text = ""

    if response.function_calls:
        function_call = response.function_calls[0]

    if response.text:
        assistant_text = response.text
                    
    result = "Sorry, I couldn't understand your request."
    
    if function_call:
        function_name = function_call.name
        arguments = function_call.args

        if function_name == "save_task":
            arguments['user_original_text'] = user_query
            result = format_save_task(arguments)
        elif function_name == "update_task":
            result = format_update_task(**arguments)
        elif function_name == "delete_task":
            result = format_delete_task(arguments["title"])
        elif function_name == "list_tasks":
            result = format_list_tasks()
        elif function_name == "save_contact":
            result = format_save_contact(**arguments)

        elif function_name == "update_contact":
            result = format_update_contact(**arguments)

        elif function_name == "delete_contact":
            result = format_delete_contact(**arguments)

        elif function_name == "search_contacts":
            result = format_search_contacts(**arguments)
        elif function_name == "fetch_call_history":
            result = format_fetch_call_history(**arguments)
        elif function_name == "fetch_filtered_tasks":
            result = format_fetch_filtered_tasks(**arguments)
        elif function_name == "analyze_dashboard_data":
            result = json.dumps(get_dashboard_metrics(), indent=2)
        # Additional function routers will be wired here...
    elif assistant_text:
        result = assistant_text
        
    return result