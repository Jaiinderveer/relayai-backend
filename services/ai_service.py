import json
import re
from core.config import openai_client
from services.task_service import (
    format_save_task, format_update_task, format_delete_task, 
    format_list_tasks
)
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

    response = openai_client.responses.create(
        model="gpt-4o-mini",
        tools=tools,
        input=input_list,
    )  

    function_call = None
    assistant_text = ""

    for item in response.output:
        if item.type == "function_call":
            function_call = item
            break
        elif item.type == "message":
            for content in item.content:
                if content.type == "output_text":
                    assistant_text += content.text
                    
    result = "Sorry, I couldn't understand your request."
    
    if function_call:
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        if function_name == "save_task":
            arguments['user_original_text'] = user_query
            result = format_save_task(arguments)
        elif function_name == "update_task":
            result = format_update_task(**arguments)
        elif function_name == "delete_task":
            result = format_delete_task(arguments["title"])
        elif function_name == "list_tasks":
            result = format_list_tasks()
        elif function_name == "analyze_dashboard_data":
            summary_json = json.dumps(get_dashboard_metrics())
            tool_call_id = getattr(function_call, 'id', 'call_dash_001')
            
            assistant_msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": tool_call_id, "type": "function", "function": {"name": function_name, "arguments": function_call.arguments}}]
            }
            tool_msg = {"role": "tool", "tool_call_id": tool_call_id, "name": function_name, "content": summary_json}
            
            msg_list = input_list + [assistant_msg, tool_msg]
            follow_up_response = openai_client.chat.completions.create(model="gpt-4o-mini", messages=msg_list)
            result = follow_up_response.choices[0].message.content
        # Additional function routers will be wired here...
    elif assistant_text:
        result = assistant_text
        
    return result