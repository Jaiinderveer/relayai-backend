import re
import string
from firebase.db_helper import DBHelper, get_tasks_query

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

# --- Advanced Natural Matching Engine ---
def normalize_text(text: str) -> str:
    if not text: return ""
    text = str(text).lower().translate(str.maketrans('', '', string.punctuation))
    return " ".join(text.split())

def resolve_entity(db_helper_instance: DBHelper, field_name: str, search_query: str):
    """Preserved fuzzy matching logic from ai_agent.py"""
    if not search_query or not search_query.strip(): return None, "No search query provided."
    search_norm = normalize_text(search_query)
    search_words = set(search_norm.split())
    if not search_words: return None, "Invalid search query."

    # Retrieve all documents to perform Python-side fuzzy matching
    candidates = db_helper_instance.retrieve()
    if not candidates: return None, f"No matching {field_name} found."

    exact_matches, subset_matches, fuzzy_matches = [], [], []

    for doc in candidates:
        target_raw = doc.get(field_name, "")
        target_norm = normalize_text(target_raw)
        if not target_norm: continue
        
        if search_norm == target_norm:
            exact_matches.append(target_raw)
            continue
            
        target_words = set(target_norm.split())
        if search_words.issubset(target_words):
            subset_matches.append(target_raw)
            continue
            
        if HAS_RAPIDFUZZ:
            score = fuzz.partial_ratio(search_norm, target_norm)
            if score >= 80: fuzzy_matches.append((target_raw, score))
        else:
            matcher = difflib.SequenceMatcher(None, search_norm, target_norm)
            if matcher.quick_ratio() >= 0.75: fuzzy_matches.append((target_raw, matcher.quick_ratio()))

    if len(exact_matches) == 1: return exact_matches[0], None
    if len(exact_matches) > 1: return None, f"Found multiple exact matches: **{', '.join(exact_matches)}**. Please clarify."
        
    if len(subset_matches) == 1: return subset_matches[0], None
    if len(subset_matches) > 1: return None, f"Found multiple partial matches: **{', '.join(subset_matches)}**. Please clarify."
        
    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
        best_score = fuzzy_matches[0][1]
        top_candidates = [m[0] for m in fuzzy_matches if m[1] >= best_score - 2]
        
        if len(top_candidates) == 1: return top_candidates[0], None
        else: return None, f"Found similar matches: **{', '.join(top_candidates)}**. Please clarify."
            
    return None, f"No matching {field_name} found."


# --- Formatting Wrappers ---
def format_save_task(task_args: dict) -> str:
    db = DBHelper('tasks')
    db.save_task(task_args)
    return (
        f"Task saved successfully as **pending** \n\n"
        f"**Action** {task_args.get('action')} \n\n"
        f"**Title** {task_args.get('title')} \n\n"
        f"**Contact Name** {task_args.get('contact_name')} \n\n"
        f"**Description** {task_args.get('description')} \n\n"
    )

def format_list_tasks() -> str:
    db = DBHelper('tasks')
    documents = db.get_tasks()
    if not documents: return "No tasks found."
    text = ""
    for i, task in enumerate(documents, start=1):
        text += (
            f"Task {i}\n\nTitle: {task.get('title')}\n\nDescription: {task.get('description')}\n\n"
            f"Action: {task.get('action')}\n\nContact: {task.get('contact_name')}\n\nStatus: {task.get('status')}\n\n"
            f"Created At: {task.get('created_at')}\n\n\n{'='*45}\n\n"
        )
    return text

def format_update_task(title: str, description=None, action=None, contact_name=None) -> str:
    db = DBHelper('tasks')
    real_title, error_msg = resolve_entity(db, "title", title)
    if error_msg: return error_msg

    updates = {}
    if description: updates["description"] = description
    if action: updates["action"] = action.lower()
    if contact_name: updates["contact_name"] = " ".join(contact_name.strip().split()).capitalize()

    res = db.update({'title': real_title}, updates)
    if res.matched_count == 0: return "Task not found."
    return f"Task **'{real_title}'** updated successfully."

def format_delete_task(title: str) -> str:
    db = DBHelper('tasks')
    real_title, error_msg = resolve_entity(db, "title", title)
    if error_msg: return error_msg

    res = db.delete({'title': real_title})
    if res.deleted_count == 0: return "Task not found."
    return f"Task **'{real_title}'** deleted successfully."
def format_fetch_filtered_tasks(status: str = None, date_preset: str = None) -> str:
    tasks = get_tasks_query(status=status, date_preset=date_preset)
    if not tasks: return "No tasks found matching criteria."
    text = ""
    for i, task in enumerate(tasks, start=1):
        text += (
            f"Task {i}\n\nTitle: {task.get('title')}\n\nDescription: {task.get('description')}\n\n"
            f"Action: {task.get('action')}\n\nContact: {task.get('contact_name')}\n\nStatus: {task.get('status')}\n\n"
            f"Created At: {task.get('created_at')}\n\n\n{'='*45}\n\n"
        )
    return text

# Call Domain
def format_fetch_call_history(call_status_intent: str = None, date_preset: str = None) -> str:
    db = DBHelper('tasks')
    calls = db.get_calls(intent_status=call_status_intent, date_preset=date_preset)
    if not calls: return "No call history found."
    text = ""
    for i, call in enumerate(calls, start=1):
        text += (
            f"Call {i}\n\nTitle: {call.get('title', 'N/A')}\n\nContact: {call.get('contact_name', 'N/A')}\n\n"
            f"Status: {call.get('status', 'N/A')}\n\nTwilio Status: {call.get('twilio_status', 'N/A')}\n\n"
            f"Created At: {call.get('created_at')}\n\n\n{'='*45}\n\n"
        )
    return text

# Contact Domain
def format_save_contact(name: str, phone: str) -> str:
    if(len(phone) < 13 or not phone[1:].isnumeric()):
        return "Invalid Number. Please Enter in the Format (+91<your_number>)"
    db = DBHelper('contacts')
    db.save_contact(name.capitalize(), phone)
    return f"Contact saved successfully.\n\n**Name:** {name.capitalize()}\n\n**Phone:** {phone}\n\n"

def format_update_contact(name: str, phone: str) -> str:
    db = DBHelper('contacts')
    real_name, error_msg = resolve_entity(db, "name", name)
    if error_msg: return error_msg

    res = db.update_contact(real_name, phone)
    if res.matched_count == 0: return "Contact not found."
    return f"Contact **'{real_name}'** updated successfully with new phone **{phone}**."

def format_delete_contact(name: str) -> str:
    db = DBHelper('contacts')
    real_name, error_msg = resolve_entity(db, "name", name)
    if error_msg: return error_msg

    res = db.delete_contact(real_name)
    if res.deleted_count == 0: return "Contact not found."
    return f"Contact **'{real_name}'** deleted successfully."

def format_search_contacts(name: str = None) -> str:
    db = DBHelper('contacts')
    if name and name.strip():
        real_name, error_msg = resolve_entity(db, "name", name)
        if error_msg: return error_msg
        contacts = db.get_contacts({'name': real_name})
    else:
        contacts = db.get_contacts()

    if not contacts: return "No contacts found."
    text = ""
    for i, contact in enumerate(contacts, start=1):
        text += f"Contact {i}\n\nName: {contact.get('name')}\n\nPhone: {contact.get('phone')}\n\n\n{'='*45}\n\n"
    return text