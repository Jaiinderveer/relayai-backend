from pydantic import BaseModel
from typing import List, Literal

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    input_list: List[ChatMessage]
    mode: Literal["default", "analytics"] = "default"
    
class ContactCreate(BaseModel):
    name: str
    phone: str

class ContactUpdate(BaseModel):
    phone: str