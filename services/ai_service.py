import json
from core.config import gemini_client
from services.task_service import (
    format_save_task, format_update_task, format_delete_task, 
    format_list_tasks, format_fetch_filtered_tasks, format_fetch_call_history,
    format_save_contact, format_update_contact, format_delete_contact,
    format_search_contacts,format_analyze_calls,format_analyze_contacts,format_analyze_tasks
)
from google.genai import types 
# Note: In Phase 4, we will add the remaining formatters (fetch_call_history, save_contact, etc.) to task_service.py

# Copied exactly from ai_agent.py
DEFAULT_TOOLS = [
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
        "description": """Retrieve individual call records and call logs.
                            Use ONLY when the user wants to VIEW, LIST, DISPLAY or SHOW call records.
                            Examples:
                            - Show failed calls
                            - Show today's calls
                            - Show Rahul's calls
                            - List call history
                            - Display completed calls
                            DO NOT use this tool for:
                            - How many...
                            - Count...
                            - Statistics...
                            - Success rate...
                            - Failure rate...
                            - Why did the last call fail?
                            - Analyze...
                            - Summarize...""",
        "parameters": {
            "type": "object",
            "properties": {
                "call_status_intent": {
                    "type": "string",
                    "enum": ["FAILED","COMPLETED","PENDING","ALL"]
                },
                "date_preset": {
                    "type": "string",
                    "enum": ["today","yesterday","this_week"]
                },
                "contact_name": {
                    "type": "string",
                    "description": "Optional. Filter calls belonging to one contact."
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
    # NEW ENTITY-CENTRIC ANALYTICS TOOLS
    
]

ANALYTICS_TOOLS = [
    {
            "type": "function",
            "name": "analyze_calls",
            "description": """
                    Analyze aggregated call statistics and operational performance.
    
                    Use ONLY when the user requests:
    
                    - counts
                    - totals
                    - percentages
                    - trends
                    - summaries
                    - analytics
                    - success rate
                    - failure rate
                    - performance metrics
    
                    Examples:
    
                    - How many calls failed today?
                    - How many completed calls do we have?
                    - What is our success rate?
                    - Summarize this week's calls.
                    - Analyze call performance.
                    - Which day had the most failed calls?
    
                    Do NOT use this tool to list or inspect individual call records.
                    """,
            "parameters": {
                "type": "object",
                "properties": {
                    "timeframe": {"type": "string", "enum": ["today", "yesterday", "this_week", "this_month", "all_time"]},
                    "status": {"type": "string", "enum": ["ALL", "COMPLETED", "FAILED", "PENDING"]},
                    "contact_name": {"type": "string", "description": "Optional name filter for a specific recipient"},
                    "action": {"type": "string", "description": "Optional action type filter"}
                }
            }
        },
        {
            "type": "function",
            "name": "analyze_tasks",
            "description": """
                Analyze task workload and completion statistics.
    
                Examples:
    
                - How many pending tasks do we have?
                - How many email tasks were completed?
                - Summarize task performance.
                - Show task completion rate.
    
                Do NOT use this tool to list individual tasks.
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "timeframe": {"type": "string", "enum": ["today", "yesterday", "this_week", "this_month", "all_time"]},
                    "status": {"type": "string", "enum": ["ALL", "PENDING", "COMPLETED", "FAILED"]},
                    "action": {"type": "string", "enum": ["ALL", "call", "email", "message", "other"]}
                }
            }
        },
        {
            "type": "function",
            "name": "analyze_contacts",
            "description": """
                Analyze contact engagement and communication statistics.
    
                Examples:
    
                - Who is our most contacted person?
                - Which contact has the highest success rate?
                - Show inactive contacts.
                - Which contacts receive the most calls?
    
                Do NOT use this tool to retrieve contact details.
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "metric_type": {"type": "string", "enum": ["most_contacted", "highest_success_rate", "lowest_success_rate", "uncontacted"]},
                    "timeframe": {"type": "string", "enum": ["today", "this_week", "this_month", "all_time"]}
                }
            }
        }
]

def explain_analytics(user_query: str, tool_result: dict) -> str:
    
    response = gemini_client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"""
User Question:
{user_query}

Analytics Result:
{json.dumps(tool_result, indent=2)}

You are RelayAI's Lead Data Analyst.

Answer the user's question using ONLY the supplied analytics.

Rules:
1. Never output JSON.
2. Never mention internal fields such as query, summary, details or metadata.
3. Answer directly using the numbers provided.
4. Mention trends only if they are visible in the data.
5. Provide ONE recommendation ONLY if it is directly supported by the analytics.
6. Never recommend external systems, CRM software, APIs, or infrastructure changes unless explicitly shown in the analytics.
7. If there is no meaningful recommendation, simply stop after answering.
"""
                    )
                ],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0,
        ),
    )

    return response.text
def agentic_save(input_list: list,mode: str = "default") -> str:
    user_query = next((item['content'] for item in reversed(input_list) if item['role'] == 'user'), "")
    
    if mode == "analytics":
        system_msg_content = """
    You are RelayAI's Executive Data Analyst.

You answer questions about analytics, trends, calls, tasks, contacts, and performance metrics.

If a user requests an operational action such as creating tasks, updating contacts, deleting records, or scheduling calls:

- Politely explain that this workspace is for analytics only.
- Ask them to use the Agentic Chat workspace for operational actions.
- Do not apologize unless an actual error occurred.
    """
    else:
        system_msg_content = """
    You are RelayAI, the AI assistant for a Workforce and Call Management platform.

Your responsibilities:
- Manage tasks (create, update, delete, list)
- Manage contacts (create, update, delete, search)
- Retrieve call history and call records
- Answer analytics questions using the available analytics tools

Rules:
1. Always use an available function whenever the user's request requires retrieving or modifying data.
2. Never invent tasks, contacts, calls, or analytics.
3. If multiple tools are available, choose the one that best matches the user's intent.
4. Ask for clarification only when the request is genuinely ambiguous.
5. Keep responses concise, professional, and user-focused.
6. Never expose internal implementation details, function names, database schemas, or JSON unless explicitly requested.
7. Never use Markdown tables unless the user asks for them.
8. Never use LaTeX.

You are the primary operational assistant for RelayAI.
    """

    system_msg = {"role": "system", "content": system_msg_content}

    if input_list and input_list[0].get("role") != "system":
        input_list.insert(0, system_msg)
    else:
        input_list[0] = system_msg

# Convert OpenAI tool schema to Gemini tool schema
    selected_tools = (
        ANALYTICS_TOOLS
        if mode == "analytics"
        else DEFAULT_TOOLS
    )

    function_declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters_json_schema=tool["parameters"],
        )
        for tool in selected_tools
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
            print("ARGS:", arguments)
            result = format_fetch_call_history(**arguments)
        elif function_name == "fetch_filtered_tasks":
            result = format_fetch_filtered_tasks(**arguments)
        elif function_name == "analyze_calls":
            # analyze_calls
            arguments.setdefault("timeframe", "all_time")
            arguments.setdefault("status", "ALL")

            result = explain_analytics(
                user_query,
                format_analyze_calls(**arguments)
            )

        elif function_name == "analyze_tasks":
            arguments.setdefault("timeframe", "all_time")
            arguments.setdefault("status", "ALL")

            result = explain_analytics(
                user_query,
                format_analyze_tasks(**arguments)
            )

        elif function_name == "analyze_contacts":
            # analyze_contacts
            arguments.setdefault("timeframe", "all_time")
            arguments.setdefault("metric_type", "most_contacted")

            result = explain_analytics(
                user_query,
                format_analyze_contacts(**arguments)
            )
    elif assistant_text:
        result = assistant_text
        
    return result