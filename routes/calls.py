from fastapi import APIRouter, HTTPException
from typing import Optional
from backend.firebase.db_helper import DBHelper
from backend.core.config import elevenlabs_client

router = APIRouter(prefix="/api/calls", tags=["Calls"])

@router.get("/")
def get_call_history(intent_status: Optional[str] = None, date_preset: Optional[str] = None):
    try:
        db = DBHelper('tasks')
        calls = db.get_calls(intent_status=intent_status, date_preset=date_preset)
        return {"calls": calls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/transcript")
def get_transcript(conversation_id: str):
    if not conversation_id:
        raise HTTPException(status_code=400, detail="No conversation ID provided.")
    try:
        # Fetch directly using the global client from core.config
        response = elevenlabs_client.conversational_ai.conversations.get(conversation_id=conversation_id)
        
        # Dynamic object parsing to avoid SDK version breaks
        if hasattr(response, "model_dump"):
            conv_data = response.model_dump()
        elif hasattr(response, "dict"):
            conv_data = response.dict()
        elif isinstance(response, dict):
            conv_data = response
        else:
            conv_data = vars(response)
            
        transcript_data = conv_data.get("transcript", [])
        
        if not transcript_data:
            return {"transcript": [{"role": "assistant", "content": "*System Note: ElevenLabs conversation transcript is currently empty.*"}]}

        formatted_transcript = []
        for msg in transcript_data:
            if isinstance(msg, dict):
                raw_role = msg.get("role", "user").lower()
                content = msg.get("message", msg.get("text", "[No Content]"))
            else:
                raw_role = getattr(msg, "role", "user").lower()
                content = getattr(msg, "message", getattr(msg, "text", "[No Content]"))
                
            streamlit_role = "assistant" if raw_role in ["agent", "assistant", "system"] else "user"
            formatted_transcript.append({"role": streamlit_role, "content": content})
            
        return {"transcript": formatted_transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))