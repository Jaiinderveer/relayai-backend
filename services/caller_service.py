from datetime import timezone
import datetime
import re
from backend.firebase.db_helper import DBHelper
from backend.core.config import (
    elevenlabs_client, twilio_client, 
    ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID
)
from backend.services.task_service import normalize_text, HAS_RAPIDFUZZ

if HAS_RAPIDFUZZ:
    from rapidfuzz import fuzz
else:
    import difflib

# Default Retry Settings (Preserved exactly)
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_MINUTES = [2, 5, 15]
TWILIO_TERMINAL_STATUSES = [
    'completed', 'busy', 'no-answer', 'failed', 'canceled', 'invalid-number', 'rejected', 'declined'
]

def resolve_contact_for_call(contact_name_query: str):
    db = DBHelper('contacts')
    search_norm = normalize_text(contact_name_query)
    search_words = set(search_norm.split())
    if not search_words: return None

    # Retrieve all contacts for Python-side regex/fuzzy match
    candidates = db.retrieve()
    if not candidates: return None

    exact_matches, subset_matches, fuzzy_matches = [], [], []

    for doc in candidates:
        target_raw = doc.get("name", "")
        target_norm = normalize_text(target_raw)
        
        if search_norm == target_norm:
            exact_matches.append(doc)
            continue
            
        target_words = set(target_norm.split())
        if search_words.issubset(target_words):
            subset_matches.append(doc)
            continue
            
        if HAS_RAPIDFUZZ:
            score = fuzz.partial_ratio(search_norm, target_norm)
            if score >= 80: fuzzy_matches.append((doc, score))
        else:
            matcher = difflib.SequenceMatcher(None, search_norm, target_norm)
            if matcher.quick_ratio() >= 0.75: fuzzy_matches.append((doc, matcher.quick_ratio()))

    if exact_matches: return exact_matches[0]
    if subset_matches: return subset_matches[0]
    if fuzzy_matches:
        fuzzy_matches.sort(key=lambda x: x[1], reverse=True)
        return fuzzy_matches[0][0]
    return None

def execute_pending_calls():
    db = DBHelper('tasks')
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate the $or query for pending tasks
    all_pending = db.retrieve({"status": "PENDING", "action": "call"})
    
    for task in all_pending:
        retry_at = task.get('next_retry_at')
        if retry_at and retry_at > now:
            continue # Skip, not time yet

        contact = resolve_contact_for_call(task.get('contact_name', ''))
        
        if not contact:
            db.update_task(task['_id'], {'status': 'FAILED', 'error': 'CONTACT NOT FOUND'})
            print(f" [Automation Engine] Task '{task.get('title')}' FAILED permanently. Contact not found.")
            continue

        try:
            response = elevenlabs_client.conversational_ai.twilio.outbound_call(
                agent_id=ELEVENLABS_AGENT_ID,
                agent_phone_number_id=ELEVENLABS_PHONE_NUMBER_ID,
                to_number=contact['phone'],
                conversation_initiation_client_data={
                    'dynamic_variables': {
                        'contact_name': contact['name'],
                        'task_summary': task.get('description', '')
                    }
                }
            )
            
            call_sid = getattr(response, 'call_sid', getattr(response, 'conversation_id', None))
            
            db.update_task(task['_id'], {
                'status': 'CALLING',
                'called_at': now,
                'conversation_id': response.conversation_id,
                'twilio_call_sid': call_sid
            })
            print(f" [Automation Engine] DIALED: '{task.get('title')}' to {contact['name']} (Conv: {response.conversation_id})")
        except Exception as e:
            handle_call_failure(task, str(e), max_retries=1, backoff=[2])


def handle_call_failure(task, reason_str: str, is_permanent: bool = False, max_retries: int = DEFAULT_MAX_RETRIES, backoff: list = DEFAULT_BACKOFF_MINUTES):
    db = DBHelper('tasks')
    current_retries = task.get('retry_count', 0)
    
    if is_permanent or current_retries >= max_retries:
        db.update_task(task['_id'], {
            'status': 'FAILED', 
            'error': f"{reason_str} (Final Status reached)"
        })
        print(f" [Automation Engine] ❌ Task '{task.get('title')}' FAILED permanently. Reason: {reason_str}")
    else:
        backoff_index = min(current_retries, len(backoff) - 1)
        wait_minutes = backoff[backoff_index]
        next_retry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=wait_minutes)
        
        db.update_task(task['_id'], {
            'status': 'PENDING',
            'retry_count': current_retries + 1,
            'next_retry_at': next_retry,
            'last_error': reason_str
        })
        print(f" [Automation Engine] 🔄 Task '{task.get('title')}' ({reason_str}). Scheduled Retry {current_retries + 1}/{max_retries} at {next_retry.strftime('%H:%M:%S')}")


def fetch_conversation_status():
    db = DBHelper('tasks')
    active_calls = db.retrieve({'status': 'CALLING'})
    
    for task in active_calls:
        try:
            conversation_id = task.get('conversation_id')
            twilio_call_sid = task.get('twilio_call_sid')
            
            el_conv = elevenlabs_client.conversational_ai.conversations.get(conversation_id=conversation_id)
            el_status = getattr(el_conv, 'status', '').lower()
            
            tw_status = None
            if twilio_client and twilio_call_sid and twilio_call_sid.startswith("CA"):
                try:
                    twilio_call = twilio_client.calls(twilio_call_sid).fetch()
                    tw_status = twilio_call.status.lower()
                except Exception as e:
                    print(f" [Automation Engine] Twilio API fetch error: {e}")
                    tw_status = None
            
            final_status = tw_status if tw_status else el_status
            
            db.update_task(task['_id'], {
                'twilio_status': tw_status, 
                'elevenlabs_status': el_status,
                'last_polled_at': datetime.datetime.now(datetime.timezone.utc)
            })
            
            print(f" [Automation Engine] POLLING '{task.get('title')}' | Twilio: {tw_status or 'N/A'} | ElevenLabs: {el_status}")

            if final_status not in TWILIO_TERMINAL_STATUSES:
                continue
                
            if final_status == 'completed':
                db.update_task(task['_id'], {'status': 'COMPLETED'})
                print(f" [Automation Engine] ✅ Task '{task.get('title')}' COMPLETED successfully.")
                
            elif final_status == 'busy':
                handle_call_failure(task, "busy", max_retries=1, backoff=[2])
                
            elif final_status == 'no-answer':
                handle_call_failure(task, "no-answer", max_retries=3, backoff=[2, 5, 15])
                
            elif final_status == 'failed':
                handle_call_failure(task, "failed", max_retries=1, backoff=[5])
                
            elif final_status in ['canceled', 'invalid-number', 'rejected', 'declined']:
                handle_call_failure(task, final_status, is_permanent=True)

        except Exception as e:
            print(f" [Automation Engine] Error fetching status for '{task.get('title')}': {e}")