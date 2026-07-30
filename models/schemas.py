from pydantic import BaseModel
from typing import List

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    input_list: List[ChatMessage]

class ContactCreate(BaseModel):
    name: str
    phone: str

class ContactUpdate(BaseModel):
    phone: str