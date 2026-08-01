import string
import time
import datetime
from firebase.db_helper import DBHelper, build_canonical_call_filter, get_tasks_query
from datetime import timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

def format_datetime(dt):
    if dt is None:
        return "N/A"

    return (
        dt.astimezone(IST)
          .strftime("%d %b %Y, %I:%M:%S %p IST")
    )
# Helper function to compute datetime ranges from timeframe strings
def resolve_timeframe_range(timeframe: str = None):
    if not timeframe:
        return None, None
    
    tf = timeframe.lower().strip()
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if tf == "today":
        return today_start, today_start + datetime.timedelta(days=1)
    elif tf == "yesterday":
        start = today_start - datetime.timedelta(days=1)
        return start, today_start
    elif tf == "this_week":
        start = today_start - datetime.timedelta(days=today_start.weekday())
        return start, None
    elif tf == "this_month":
        start = today_start.replace(day=1)
        return start, None
    elif tf == "all_time":
        return None, None
    return None, None


# --- ANALYTICS ENGINE 1: ANALYZE CALLS ---
def format_analyze_calls(timeframe: str = None, status: str = None, contact_name: str = None, action: str = None) -> dict:
    start_time = time.time()
    db = DBHelper('tasks')
    
    # Retrieve all call tasks
    raw_calls = db.get_calls(intent_status=status, date_preset=None)
    
    start_date, end_date = resolve_timeframe_range(timeframe)
    filtered_calls = []

    for call in raw_calls:
        # Timeframe filter
        created_at = call.get('created_at')
        if start_date and isinstance(created_at, datetime.datetime):
            if created_at < start_date:
                continue
            if end_date and created_at >= end_date:
                continue
                
        # Contact filter (fuzzy / partial matching)
        if contact_name and contact_name.strip():
            c_target = call.get('contact_name', '')
            if normalize_text(contact_name) not in normalize_text(c_target):
                continue
                
        # Action filter
        if action and action.strip():
            if call.get('action', '').lower() != action.lower().strip():
                continue
                
        filtered_calls.append(call)

    # Compute Summaries
    total_count = len(filtered_calls)
    completed_count = sum(1 for c in filtered_calls if str(c.get('status', '')).upper() == 'COMPLETED')
    failed_count = sum(1 for c in filtered_calls if str(c.get('status', '')).upper() == 'FAILED')
    pending_count = sum(1 for c in filtered_calls if str(c.get('status', '')).upper() in ['PENDING', 'CALLING'])
    
    success_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0.0

    # Extract primary failure reason
    failure_reasons = {}
    for c in filtered_calls:
        if str(c.get('status', '')).upper() == 'FAILED':
            err = c.get('error') or c.get('last_error') or c.get('twilio_status') or 'unknown'
            failure_reasons[err] = failure_reasons.get(err, 0) + 1
            
    primary_failure_reason = max(failure_reasons, key=failure_reasons.get) if failure_reasons else "None"

    # Details (Top 5 samples)
    details = []
    for c in filtered_calls[:5]:
        details.append({
            "title": c.get('title', 'Untitled'),
            "contact": c.get('contact_name', 'Unknown'),
            "status": c.get('status', 'UNKNOWN'),
            "created_at": c.get('created_at').isoformat() if isinstance(c.get('created_at'), datetime.datetime) else str(c.get('created_at')),
            "error_detail": c.get('error') or c.get('last_error') or None
        })

    execution_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "query": {
            "timeframe": timeframe or "all_time",
            "status": status or "ALL",
            "contact_name": contact_name or None,
            "action": action or "call"
        },
        "summary": {
            "total_count": total_count,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "pending_count": pending_count,
            "success_rate_pct": success_rate,
            "primary_failure_reason": primary_failure_reason
        },
        "details": details,
        "metadata": {
            "execution_time_ms": execution_ms,
            "total_records_scanned": len(raw_calls),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    }


# --- ANALYTICS ENGINE 2: ANALYZE TASKS ---
def format_analyze_tasks(timeframe: str = None, status: str = None, action: str = None) -> dict:
    start_time = time.time()
    db = DBHelper('tasks')
    
    all_tasks = db.get_tasks()
    start_date, end_date = resolve_timeframe_range(timeframe)
    filtered_tasks = []

    for task in all_tasks:
        # Timeframe filter
        created_at = task.get('created_at')
        if start_date and isinstance(created_at, datetime.datetime):
            if created_at < start_date:
                continue
            if end_date and created_at >= end_date:
                continue
                
        # Status filter
        if status and status.strip() and status.upper() != "ALL":
            if str(task.get('status', '')).upper() != status.upper().strip():
                continue

        # Action filter
        if action and action.strip() and action.upper() != "ALL":
            if str(task.get('action', '')).lower() != action.lower().strip():
                continue

        filtered_tasks.append(task)

    total_count = len(filtered_tasks)
    completed_count = sum(1 for t in filtered_tasks if str(t.get('status', '')).upper() == 'COMPLETED')
    pending_count = sum(1 for t in filtered_tasks if str(t.get('status', '')).upper() == 'PENDING')
    failed_count = sum(1 for t in filtered_tasks if str(t.get('status', '')).upper() == 'FAILED')
    
    completion_rate = round((completed_count / total_count * 100), 1) if total_count > 0 else 0.0

    details = []
    for t in filtered_tasks[:5]:
        details.append({
            "title": t.get('title', 'Untitled'),
            "action": t.get('action', 'other'),
            "contact": t.get('contact_name', 'Unassigned'),
            "status": t.get('status', 'PENDING'),
            "created_at": t.get('created_at').isoformat() if isinstance(t.get('created_at'), datetime.datetime) else str(t.get('created_at'))
        })

    execution_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "query": {
            "timeframe": timeframe or "all_time",
            "status": status or "ALL",
            "action": action or "ALL"
        },
        "summary": {
            "total_count": total_count,
            "completed_count": completed_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "completion_rate_pct": completion_rate
        },
        "details": details,
        "metadata": {
            "execution_time_ms": execution_ms,
            "total_records_scanned": len(all_tasks),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    }


# --- ANALYTICS ENGINE 3: ANALYZE CONTACTS ---
def format_analyze_contacts(metric_type: str = None, timeframe: str = None) -> dict:
    start_time = time.time()
    db = DBHelper('tasks')
    db_contacts = DBHelper('contacts')
    
    all_calls = db.get_calls()
    all_contacts = db_contacts.get_contacts()
    
    start_date, end_date = resolve_timeframe_range(timeframe)
    
    contact_stats = {}
    for c in all_contacts:
        name = c.get('name', 'Unknown')
        contact_stats[name] = {'total_calls': 0, 'completed_calls': 0, 'failed_calls': 0, 'phone': c.get('phone')}

    for call in all_calls:
        created_at = call.get('created_at')
        if start_date and isinstance(created_at, datetime.datetime):
            if created_at < start_date or (end_date and created_at >= end_date):
                continue
                
        name = call.get('contact_name', 'Unknown')
        if name not in contact_stats:
            contact_stats[name] = {'total_calls': 0, 'completed_calls': 0, 'failed_calls': 0, 'phone': 'N/A'}
            
        contact_stats[name]['total_calls'] += 1
        st = str(call.get('status', '')).upper()
        if st == 'COMPLETED':
            contact_stats[name]['completed_calls'] += 1
        elif st == 'FAILED':
            contact_stats[name]['failed_calls'] += 1

    # Format list for metric calculation
    ranked_list = []
    for name, stats in contact_stats.items():
        calls_count = stats['total_calls']
        success_pct = round((stats['completed_calls'] / max(calls_count, 1)) * 100, 1) if calls_count > 0 else 0.0
        ranked_list.append({
            "contact_name": name,
            "phone": stats['phone'],
            "total_calls": calls_count,
            "completed_calls": stats['completed_calls'],
            "failed_calls": stats['failed_calls'],
            "success_rate_pct": success_pct
        })

    m_type = (metric_type or "most_contacted").lower().strip()
    
    if m_type == "highest_success_rate":
        ranked_list.sort(key=lambda x: (x['success_rate_pct'], x['total_calls']), reverse=True)
    elif m_type == "lowest_success_rate":
        ranked_list.sort(key=lambda x: (x['total_calls'] > 0, -x['success_rate_pct']), reverse=True)
    elif m_type == "uncontacted":
        ranked_list = [x for x in ranked_list if x['total_calls'] == 0]
    else:  # default: most_contacted
        ranked_list.sort(key=lambda x: x['total_calls'], reverse=True)

    top_leader = ranked_list[0] if ranked_list else {"contact_name": "None", "total_calls": 0, "success_rate_pct": 0.0}

    execution_ms = round((time.time() - start_time) * 1000, 2)

    return {
        "query": {
            "metric_type": m_type,
            "timeframe": timeframe or "all_time"
        },
        "summary": {
            "leader_contact": top_leader.get('contact_name'),
            "leader_total_calls": top_leader.get('total_calls'),
            "leader_success_rate_pct": top_leader.get('success_rate_pct'),
            "total_contacts_analyzed": len(contact_stats)
        },
        "details": ranked_list[:5],
        "metadata": {
            "execution_time_ms": execution_ms,
            "total_records_scanned": len(all_calls) + len(all_contacts),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    }

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
def format_fetch_call_history(
    call_status_intent=None,
    date_preset=None,
    contact_name=None
):
    db = DBHelper('tasks')
    calls = db.get_calls(intent_status=call_status_intent, date_preset=date_preset,contact_name=contact_name)
    if not calls: return "No call history found."
    text = ""
    for i, call in enumerate(calls, start=1):
        text += (
            f"Call {i}\n\nTitle: {call.get('title', 'N/A')}\n\nContact: {call.get('contact_name', 'N/A')}\n\n"
            f"Status: {call.get('status', 'N/A')}\n\n"
            f"Created At: {format_datetime(call.get('created_at'))}\n\n\n{'='*45}\n\n"
        )
    return text
def contact_exists(name: str) -> bool:
    db = DBHelper("contacts")

    real_name, error = resolve_entity(db, "name", name)

    return error is None
# Contact Domain
def format_save_contact(name: str, phone: str) -> str:
    if(len(phone) < 13 or not phone[1:].isnumeric()):
        return "Invalid Number. Please Enter in the Format (+91<your_number>)"
    if (contact_exists(name=name)):
        return "Name already exists in contacts. Kindly provide a unique name or update the existing contact!"
    db = DBHelper('contacts')
    db.save_contact(name.capitalize(), phone)
    return f"Contact saved successfully.\n\n**Name:** {name.capitalize()}\n\n**Phone:** {phone}\n\n"

def format_update_contact(name: str, phone: str) -> str:
    if(len(phone) < 13 or not phone[1:].isnumeric()):
        return "Invalid Number. Please Enter in the Format (+91<your_number>)"
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