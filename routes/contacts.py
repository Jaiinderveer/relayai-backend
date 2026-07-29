from fastapi import APIRouter, HTTPException
from backend.firebase.db_helper import DBHelper
from backend.models.schemas import ContactCreate, ContactUpdate

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])

@router.get("/")
def list_contacts():
    db = DBHelper('contacts')
    return {"contacts": db.get_contacts()}

@router.post("/")
def create_contact(contact: ContactCreate):
    db = DBHelper('contacts')
    doc_id = db.save_contact(contact.name, contact.phone)
    return {"message": "Contact saved", "id": doc_id}

@router.put("/{name}")
def update_contact(name: str, contact: ContactUpdate):
    db = DBHelper('contacts')
    res = db.update_contact(name, contact.phone)
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact updated"}

@router.delete("/{name}")
def delete_contact(name: str):
    db = DBHelper('contacts')
    res = db.delete_contact(name)
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact deleted"}