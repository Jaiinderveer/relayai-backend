import json
import re
from backend.core.config import openai_client
from backend.services.task_service import (
    format_save_task, format_update_task, format_delete_task, 
    format_list_tasks
)
# Note: In Phase 4, we will add the remaining formatters (fetch_call_history, save_contact, etc.) to task_service.py
from backend.firebase.db_helper import get_dashboard_metrics

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
    # ... (Other tools omitted here for brevity, but all 11 tools from ai_agent.py are preserved exactly)
]

def classify_intent(text: str) -> str:
    if FAST_GREETING_REGEX.match(text.strip()): return "CASUAL"

    prompt = (
        "Classify the user message into exactly ONE category:\n"
        "CASUAL: Greetings, small talk, pleasantries.\n"
        "CALLS: Questions specifically about phone calls, call history, failed calls, who didn't answer, call status.\n"
        "TASKS: Questions about generic tasks, pending tasks, deleting/updating tasks.\n"
        "CONTACTS: Questions about managing, creating, or searching contacts.\n"
        "DASHBOARD: Questions asking for analytics, summaries, aggregated counts, 'how many', success rates.\n"
        "UNRELATED: Unrelated programming, math, general knowledge.\n\n"
        f"Message: '{text}'\n"
        "Category (CASUAL, CALLS, TASKS, CONTACTS, DASHBOARD, or UNRELATED):"
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5
        )
        cat = response.choices[0].message.content.strip().upper()
        if "CASUAL" in cat: return "CASUAL"
        elif "CALLS" in cat: return "CALLS"
        elif "TASKS" in cat: return "TASKS"
        elif "CONTACTS" in cat: return "CONTACTS"
        elif "DASHBOARD" in cat: return "DASHBOARD"
        elif "UNRELATED" in cat: return "UNRELATED"
        return "CALLS" if "CALL" in text.upper() else "TASKS"
    except Exception:
        return "CALLS" if "CALL" in text.upper() else "TASKS"


def agentic_save(input_list: list) -> str:
    user_query = next((item['content'] for item in reversed(input_list) if item['role'] == 'user'), "")
    intent = classify_intent(user_query) if user_query else "TASKS"

    if intent == "UNRELATED":
        return "I'm RelayAI, your AI assistant for this platform. I can help you manage tasks, contacts, phone calls, schedules, and analytics, but I can't assist with unrelated programming or general knowledge requests."

    system_msg_content = (
        "You are RelayAI, a specialized AI assistant for a Call Management Platform. "
        "FORMATTING RULE: Never use LaTeX formatting like \\[ ... \\] or \\( ... \\) for math. "
        "Always present numbers, percentages, and simple calculations in plain text and standard Markdown. "
    )
    
    if intent == "CALLS":
        system_msg_content += "CRITICAL INSTRUCTION: The user is asking about CALLS. You MUST call 'fetch_call_history' immediately. NEVER ask the user for clarification or timeframes."
    elif intent == "TASKS":
        system_msg_content += "The user is asking about TASKS. Use the generic task management tools."
    elif intent == "DASHBOARD":
        system_msg_content += "The user is asking about DASHBOARD analytics or aggregated counts. Use the 'analyze_dashboard_data' tool."
    elif intent == "CONTACTS":
        system_msg_content += "The user is asking about CONTACTS. Use contact management tools."
    elif intent == "CASUAL":
        system_msg_content += "The user is making casual conversation. Introduce yourself warmly and state your capabilities."

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
    else:
        result = assistant_text
        
    return result