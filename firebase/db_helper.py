import datetime
from datetime import timezone
import re
from typing import Dict, Any, List, Optional
from google.cloud.firestore_v1 import FieldFilter
from firebase.client import db

class UpdateResult:
    """Wrapper to mimic PyMongo UpdateResult signature."""
    def __init__(self, matched_count: int, modified_count: int = 1):
        self.matched_count = matched_count
        self.modified_count = modified_count

class DeleteResult:
    """Wrapper to mimic PyMongo DeleteResult signature."""
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class DBHelper:
    def __init__(self, collection_name: str = 'tasks'):
        self.db = db
        self.collection_name = collection_name
        self.collection = self.db.collection(collection_name)
        print(f' [DBHelper] Initialized with Firestore collection: {collection_name}')
        
    def select_collection(self, collection_name: str):
        self.collection_name = collection_name
        self.collection = self.db.collection(collection_name)
        print(f' [DBHelper] Collection Selected: {collection_name}')
        return self

    # =========================================================================
    # GENERIC COLLECTION METHODS (PyMongo Compatibility Layer)
    # =========================================================================

    def save(self, document: Dict[str, Any]) -> str:
        """Saves a document to the current collection."""
        doc_data = document.copy()
        if 'created_at' not in doc_data:
            doc_data['created_at'] = datetime.datetime.now(datetime.timezone.utc)
            
        doc_ref = self.collection.add(doc_data)
        doc_id = doc_ref[1].id
        print(f' [DBHelper] Document Saved in {self.collection_name}. ID: {doc_id}')
        return doc_id

    def save_many(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Saves multiple documents using Firestore Batch write."""
        batch = self.db.batch()
        inserted_ids = []
        for doc in documents:
            doc_data = doc.copy()
            if 'created_at' not in doc_data:
                doc_data['created_at'] = datetime.datetime.now(datetime.timezone.utc)
            doc_ref = self.collection.document()
            batch.set(doc_ref, doc_data)
            inserted_ids.append(doc_ref.id)
        batch.commit()
        print(f' [DBHelper] Batch Saved {len(inserted_ids)} documents in {self.collection_name}.')
        return inserted_ids

    def retrieve(self, condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieves documents matching basic equality or regex conditions."""
        if not condition:
            docs = self.collection.stream()
            results = []
            for doc in docs:
                d = doc.to_dict()
                d['_id'] = doc.id
                results.append(d)
            return results

        # In-memory filtering for complex/regex/or queries to ensure full parity
        all_docs = self.retrieve()
        filtered = []
        for doc in all_docs:
            if self._matches_condition(doc, condition):
                filtered.append(doc)
        return filtered

    def update(self, condition: Dict[str, Any], document_to_update: Dict[str, Any]) -> UpdateResult:
        """Updates documents matching the condition."""
        target_docs = self.retrieve(condition)
        if not target_docs:
            return UpdateResult(matched_count=0)

        batch = self.db.batch()
        for doc in target_docs:
            doc_ref = self.collection.document(doc['_id'])
            batch.update(doc_ref, document_to_update)
        batch.commit()
        
        return UpdateResult(matched_count=len(target_docs))

    def delete(self, condition: Dict[str, Any]) -> DeleteResult:
        """Deletes documents matching the condition."""
        target_docs = self.retrieve(condition)
        if not target_docs:
            return DeleteResult(deleted_count=0)

        batch = self.db.batch()
        for doc in target_docs:
            doc_ref = self.collection.document(doc['_id'])
            batch.delete(doc_ref)
        batch.commit()
        
        return DeleteResult(deleted_count=len(target_docs))

    def _matches_condition(self, doc: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """Evaluates MongoDB-style query filters in Python for complete query compatibility."""
        for key, val in condition.items():
            if key == '$or':
                if not any(self._matches_condition(doc, sub_cond) for sub_cond in val):
                    return False
                continue

            doc_val = doc.get(key)

            if isinstance(val, dict):
                if '$regex' in val:
                    pattern = val['$regex']
                    flags = re.IGNORECASE if val.get('$options') == 'i' else 0
                    if not doc_val or not re.search(pattern, str(doc_val), flags):
                        return False
                if '$in' in val:
                    if doc_val not in val['$in']:
                        return False
                if '$ne' in val:
                    if doc_val == val['$ne']:
                        return False
                if '$exists' in val:
                    exists = key in doc and doc[key] is not None
                    if exists != val['$exists']:
                        return False
                if '$gte' in val and (doc_val is None or doc_val < val['$gte']):
                    return False
                if '$lt' in val and (doc_val is None or doc_val >= val['$lt']):
                    return False
                if '$lte' in val and (doc_val is None or doc_val > val['$lte']):
                    return False
            else:
                if doc_val != val:
                    return False
        return True

    # =========================================================================
    # DOMAIN SPECIFIC METHODS
    # =========================================================================

    # --- Task Domain ---
    def save_task(self, task_data: Dict[str, Any]) -> str:
        self.select_collection('tasks')
        task = task_data.copy()
        task['status'] = task.get('status', 'PENDING')
        task['created_at'] = task.get('created_at', datetime.datetime.now(datetime.timezone.utc))
        task['title'] = " ".join(task.get('title', '').strip().split())
        task['contact_name'] = " ".join(task.get('contact_name', '').strip().split())
        return self.save(task)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        self.select_collection('tasks')
        doc = self.collection.document(task_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['_id'] = doc.id
            return data
        return None

    def get_tasks(self, condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.select_collection('tasks')
        return self.retrieve(condition)

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> UpdateResult:
        self.select_collection('tasks')
        return self.update({'_id': task_id}, updates)

    def delete_task(self, task_id: str) -> DeleteResult:
        self.select_collection('tasks')
        return self.delete({'_id': task_id})

    # --- Contact Domain ---
    def save_contact(self, name: str, phone: str) -> str:
        self.select_collection('contacts')
        clean_name = " ".join(name.strip().split())
        return self.save({'name': clean_name, 'phone': phone.strip()})

    def get_contacts(self, condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.select_collection('contacts')
        return self.retrieve(condition)

    def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        self.select_collection('contacts')
        doc = self.collection.document(contact_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['_id'] = doc.id
            return data
        return None

    def update_contact(self, name: str, new_phone: str) -> UpdateResult:
        self.select_collection('contacts')
        return self.update({'name': name}, {'phone': new_phone.strip()})

    def delete_contact(self, name: str) -> DeleteResult:
        self.select_collection('contacts')
        return self.delete({'name': name})

    # --- Call Domain ---
    def save_call(self, call_data: Dict[str, Any]) -> str:
        self.select_collection('tasks')
        call = call_data.copy()
        call['action'] = 'call'
        return self.save(call)

    def update_call(self, call_id: str, updates: Dict[str, Any]) -> UpdateResult:
        self.select_collection('tasks')
        return self.update({'_id': call_id}, updates)

    def get_calls(self, intent_status: Optional[str] = None, date_preset: Optional[str] = None) -> List[Dict[str, Any]]:
        self.select_collection('tasks')
        filter_cond = build_canonical_call_filter(intent_status, date_preset)
        results = self.retrieve(filter_cond)
        
        # Sort descending by created_at
        results.sort(key=lambda x: x.get('created_at', datetime.datetime.min), reverse=True)
        
        # Smart Fallback if date filter returned 0
        if not results and date_preset:
            fallback_cond = build_canonical_call_filter(intent_status, date_preset=None)
            results = self.retrieve(fallback_cond)
            results.sort(key=lambda x: x.get('created_at', datetime.datetime.min), reverse=True)
            
        return results


# ==============================================================================
# CANONICAL ANALYTICS LAYER (FIRESTORE ADAPTATION)
# ==============================================================================

def build_canonical_call_filter(intent_status: Optional[str] = None, date_preset: Optional[str] = None) -> Dict[str, Any]:
    condition: Dict[str, Any] = {"action": "call"}

    if intent_status:
        intent_upper = str(intent_status).upper().strip()
        
        if intent_upper == "FAILED":
            condition["$or"] = [
                {"status": {"$regex": "^FAILED$", "$options": "i"}},
                {"twilio_status": {"$in": ["failed", "no-answer", "busy", "canceled", "rejected", "declined"]}},
                {"error": {"$exists": True, "$ne": None}},
                {"last_error": {"$exists": True, "$ne": None}}
            ]
        elif intent_upper == "COMPLETED":
            condition["status"] = {"$regex": "^COMPLETED$", "$options": "i"}
            condition["twilio_status"] = {"$ne": "failed"}
        elif intent_upper == "PENDING":
            condition["status"] = {"$in": ["PENDING", "CALLING"]}

    if date_preset:
        now = datetime.datetime.now(datetime.timezone.utc)
        if date_preset == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
            condition["created_at"] = {"$gte": start, "$lt": end}
        elif date_preset == "yesterday":
            start = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
            condition["created_at"] = {"$gte": start, "$lt": end}
        elif date_preset == "this_week":
            start = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            condition["created_at"] = {"$gte": start}

    return condition


def get_dashboard_metrics() -> dict:
    """Calculates all dashboard cards deterministically in Python. Defensive against malformed docs."""
    db_h = DBHelper('tasks')
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Safely retrieve collections
    all_tasks = db_h.select_collection('tasks').retrieve() or []
    all_contacts = db_h.select_collection('contacts').retrieve() or []

    total_tasks = len(all_tasks)
    total_contacts = len(all_contacts)

    calls = db_h.select_collection('tasks').retrieve(build_canonical_call_filter()) or []
    failed_calls = db_h.select_collection('tasks').retrieve(build_canonical_call_filter(intent_status="FAILED")) or []
    completed_calls = db_h.select_collection('tasks').retrieve(build_canonical_call_filter(intent_status="COMPLETED")) or []
    pending_calls = db_h.select_collection('tasks').retrieve(build_canonical_call_filter(intent_status="PENDING")) or []
    
    today_completed_filter = {**build_canonical_call_filter(intent_status="COMPLETED"), "created_at": {"$gte": today_start}}
    today_completed = len(db_h.select_collection('tasks').retrieve(today_completed_filter) or [])

    # DEFENSIVE: Retry Metrics (skip missing or non-numeric retry counts)
    total_retries = 0
    today_retries = 0
    for doc in all_tasks:
        retry_val = doc.get('retry_count', 0)
        if isinstance(retry_val, (int, float)):
            total_retries += retry_val
            created_val = doc.get('created_at')
            if isinstance(created_val, datetime.datetime) and created_val >= today_start:
                today_retries += retry_val

    # DEFENSIVE: Contact Call Stats & Success Rates (handle missing names and statuses safely)
    contact_stats = {}
    for task in calls:
        c_name = task.get('contact_name')
        if not isinstance(c_name, str) or not c_name.strip():
            c_name = "Unknown"

        if c_name not in contact_stats:
            contact_stats[c_name] = {'call_count': 0, 'success_count': 0}
        
        contact_stats[c_name]['call_count'] += 1
        
        status = task.get('status')
        if isinstance(status, str) and status.upper() == 'COMPLETED':
            contact_stats[c_name]['success_count'] += 1

    sorted_by_calls = sorted(contact_stats.items(), key=lambda x: x[1]['call_count'], reverse=True)
    most_called = sorted_by_calls[0][0] if sorted_by_calls else "N/A"

    sorted_by_success = sorted(
        contact_stats.items(), 
        key=lambda x: x[1]['success_count'] / max(x[1]['call_count'], 1), 
        reverse=True
    )
    highest_success_contact = sorted_by_success[0][0] if sorted_by_success else "N/A"

    # DEFENSIVE: Discrepancies
    task_contacts_raw = {doc.get("contact_name") for doc in all_tasks if isinstance(doc.get("contact_name"), str)}
    db_contacts_raw = {doc.get("name") for doc in all_contacts if isinstance(doc.get("name"), str)}

    task_c_lower = {c.lower(): c for c in task_contacts_raw}
    db_c_lower = {c.lower(): c for c in db_contacts_raw}

    unassigned_lower = set(db_c_lower.keys()) - set(task_c_lower.keys())
    deleted_lower = set(task_c_lower.keys()) - set(db_c_lower.keys())

    unassigned_contacts = [db_c_lower[k] for k in unassigned_lower]
    deleted_contacts_raw = [task_c_lower[k] for k in deleted_lower]
    
    calls_to_deleted = len([
        t for t in calls if isinstance(t.get("contact_name"), str) and t.get("contact_name") in deleted_contacts_raw
    ])

    return {
        "Total_Tasks_All_Time": total_tasks,
        "Total_Calls_All_Time": len(calls),
        "Failed_Calls_All_Time": len(failed_calls),
        "Pending_Calls_Current": len(pending_calls),
        "Completed_Calls_All_Time": len(completed_calls),
        "Total_Contacts": total_contacts,
        "Total_Retries_All_Time": total_retries,
        "Retries_Today": today_retries,
        "Most_Called_Contact_All_Time": most_called,
        "Contact_With_Highest_Success_Rate": highest_success_contact,
        "Contacts_With_No_Tasks_Assigned": unassigned_contacts,
        "Number_Of_Calls_To_Deleted_Contacts": calls_to_deleted,
        "Todays_Completed_Tasks_Count": today_completed
    }

def get_calls_query(intent_status: Optional[str] = None, date_preset: Optional[str] = None) -> List[Dict[str, Any]]:
    db_h = DBHelper('tasks')
    return db_h.get_calls(intent_status=intent_status, date_preset=date_preset)


def get_tasks_query(status: Optional[str] = None, date_preset: Optional[str] = None, action: Optional[str] = None) -> List[Dict[str, Any]]:
    db_h = DBHelper('tasks')
    condition: Dict[str, Any] = {}
    if status and status.strip():
        condition["status"] = {"$regex": f"^{re.escape(status.strip())}$", "$options": "i"}
    
    if action and action.strip():
        condition["action"] = {"$regex": f"^{re.escape(action.strip())}$", "$options": "i"}
    else:
        condition["action"] = {"$ne": "call"}
        
    if date_preset:
        now = datetime.datetime.now(datetime.timezone.utc)
        if date_preset == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
            condition["created_at"] = {"$gte": start, "$lt": end}
        elif date_preset == "yesterday":
            start = (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + datetime.timedelta(days=1)
            condition["created_at"] = {"$gte": start, "$lt": end}

    results = db_h.retrieve(condition)
    results.sort(key=lambda x: x.get('created_at', datetime.datetime.min), reverse=True)
    return results